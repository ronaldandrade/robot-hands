"""Converte os landmarks da mão (MediaPipe) em ângulos de servo e gestos.

Convenção dos ângulos (igual a um servo da mão robótica):
    0°   = dedo totalmente esticado
    180° = dedo totalmente fechado
"""

import numpy as np

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]

# Índices dos landmarks de cada dedo (base -> ponta)
FINGER_JOINTS = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}

# Soma de flexão (graus) considerada "dedo totalmente fechado".
# Ajuste se a sua mão não chegar a 180° ao fechar.
# FINGER_REST_BEND é a curvatura natural da palma com o dedo esticado.
MAX_FINGER_BEND = 210.0
FINGER_REST_BEND = 30.0
MAX_THUMB_BEND = 110.0

# Abaixo deste ângulo o dedo é considerado esticado (para os gestos)
EXTENDED_THRESHOLD = 70


def _bend(a, b, c):
    """Ângulo de flexão na articulação b (0 = segmentos alinhados)."""
    v1, v2 = b - a, c - b
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def finger_angles(world_landmarks):
    """Recebe os 21 hand_world_landmarks e devolve {dedo: ângulo 0-180}.

    Usa coordenadas 3D em metros, então o resultado não depende da distância
    ou da rotação da mão em relação à câmera.
    """
    pts = np.array([[lm.x, lm.y, lm.z] for lm in world_landmarks])
    wrist = pts[0]
    angles = {}

    for name, (j0, j1, j2, j3) in FINGER_JOINTS.items():
        if name == "thumb":
            # Flexão das articulações do polegar + quanto a ponta se aproxima
            # da base do mindinho (o polegar "cruza" a palma ao fechar).
            bend = _bend(pts[j0], pts[j1], pts[j2]) + _bend(pts[j1], pts[j2], pts[j3])
            palm = np.linalg.norm(pts[9] - wrist)
            reach = np.linalg.norm(pts[4] - pts[17]) / (palm + 1e-9)
            closeness = np.clip((1.4 - reach) / 0.9, 0, 1) * 180
            value = 0.5 * np.clip(bend / MAX_THUMB_BEND, 0, 1) * 180 + 0.5 * closeness
        else:
            bend = (
                _bend(wrist, pts[j0], pts[j1])
                + _bend(pts[j0], pts[j1], pts[j2])
                + _bend(pts[j1], pts[j2], pts[j3])
            )
            value = np.clip((bend - FINGER_REST_BEND) / (MAX_FINGER_BEND - FINGER_REST_BEND), 0, 1) * 180
        angles[name] = float(value)

    return angles


def detect_gesture(angles, world_landmarks=None):
    """Classifica o gesto a partir dos ângulos dos dedos."""
    ext = {f: angles[f] < EXTENDED_THRESHOLD for f in FINGERS}
    t, i, m, r, p = (ext[f] for f in FINGERS)

    if world_landmarks is not None and m and r and p:
        tip_t, tip_i = world_landmarks[4], world_landmarks[8]
        dist = np.linalg.norm([tip_t.x - tip_i.x, tip_t.y - tip_i.y, tip_t.z - tip_i.z])
        if dist < 0.025:  # 2,5 cm
            return "OK"

    patterns = {
        (True, True, True, True, True): "OPEN",
        (False, False, False, False, False): "FIST",
        (True, False, False, False, False): "THUMBS UP",
        (False, True, True, False, False): "TWO",
        (True, True, True, False, False): "PEACE",
        (False, True, False, False, False): "POINT",
        (True, True, False, False, False): "GUN",
        (False, True, False, False, True): "ROCK",
        (True, True, False, False, True): "LOVE",
        (True, False, False, False, True): "CALL ME",
        (False, True, True, True, False): "THREE",
        (False, True, True, True, True): "FOUR",
    }
    return patterns.get((t, i, m, r, p), "")


class Smoother:
    """Média móvel exponencial para tirar a tremedeira dos ângulos."""

    def __init__(self, alpha=0.4):
        self.alpha = alpha
        self.state = None

    def __call__(self, angles):
        if self.state is None:
            self.state = dict(angles)
        else:
            for k, v in angles.items():
                self.state[k] += self.alpha * (v - self.state[k])
        return {k: round(v) for k, v in self.state.items()}

    def reset(self):
        self.state = None
