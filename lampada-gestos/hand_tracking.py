"""Rastreamento da mão com MediaPipe: pontos, abertura dos dedos e gestos.

Convenção dos ângulos dos dedos:
    0°   = dedo totalmente esticado
    180° = dedo totalmente fechado
"""

import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    HandLandmarksConnections,
    RunningMode,
)

MODEL_PATH = Path(__file__).parent / "models" / "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)

FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
FINGER_JOINTS = {  # índices dos landmarks de cada dedo (base -> ponta)
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}

# Calibração: soma de flexão (graus) do dedo fechado e do dedo esticado
MAX_FINGER_BEND = 210.0
FINGER_REST_BEND = 30.0
MAX_THUMB_BEND = 110.0
# Abaixo deste ângulo o dedo conta como esticado
EXTENDED_THRESHOLD = 70

GESTURES = {  # (polegar, indicador, médio, anelar, mindinho) esticados?
    (True, True, True, True, True): "OPEN",
    (False, False, False, False, False): "FIST",
    (True, False, False, False, False): "THUMBS UP",
    (True, True, True, False, False): "PEACE",
    (False, True, False, False, True): "ROCK",
}

MAGENTA = (255, 0, 255)
WHITE = (255, 255, 255)


def ensure_model():
    """Baixa o modelo do MediaPipe (~7 MB) na primeira execução."""
    if MODEL_PATH.exists():
        return
    MODEL_PATH.parent.mkdir(exist_ok=True)
    print("Baixando o modelo de mãos do MediaPipe...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


class HandTracker:
    """Detecta uma mão por frame e devolve (landmarks, world_landmarks) ou None."""

    def __init__(self):
        ensure_model()
        self.landmarker = HandLandmarker.create_from_options(HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        ))

    def detect(self, frame_bgr, timestamp_ms):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, timestamp_ms)
        if not result.hand_landmarks:
            return None
        return result.hand_landmarks[0], result.hand_world_landmarks[0]

    def close(self):
        self.landmarker.close()


def _points(world_landmarks):
    return np.array([[lm.x, lm.y, lm.z] for lm in world_landmarks])


def _bend(a, b, c):
    """Ângulo de flexão na articulação b (0 = segmentos alinhados)."""
    v1, v2 = b - a, c - b
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def finger_angles(world_landmarks):
    """Recebe os 21 hand_world_landmarks (3D, em metros) e devolve {dedo: 0-180}.

    Por usar coordenadas 3D, o resultado não depende da distância nem da
    rotação da mão em relação à câmera.
    """
    pts = _points(world_landmarks)
    wrist = pts[0]
    angles = {}
    for name, (j0, j1, j2, j3) in FINGER_JOINTS.items():
        if name == "thumb":
            # Flexão das articulações + quanto a ponta se aproxima da base do
            # mindinho (o polegar "cruza" a palma ao fechar).
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


def detect_gesture(angles):
    """Nome do gesto (ver GESTURES) ou "" se não for nenhum deles."""
    key = tuple(angles[f] < EXTENDED_THRESHOLD for f in FINGERS)
    return GESTURES.get(key, "")


def pinch_ratio(world_landmarks):
    """Distância polegar-indicador dividida pelo tamanho da palma."""
    pts = _points(world_landmarks)
    palm = np.linalg.norm(pts[9] - pts[0])
    return float(np.linalg.norm(pts[4] - pts[8]) / (palm + 1e-9))


class Smoother:
    """Média móvel exponencial para tirar a tremedeira dos ângulos."""

    def __init__(self, alpha=0.5):
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


def draw_hand(img, landmarks):
    h, w = img.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for c in HandLandmarksConnections.HAND_CONNECTIONS:
        cv2.line(img, pts[c.start], pts[c.end], WHITE, 1, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, 3, MAGENTA, cv2.FILLED)
