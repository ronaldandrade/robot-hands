"""Controle de mão robótica 3D por gestos usando visão computacional.

Lê a webcam, rastreia até duas mãos com MediaPipe, calcula o ângulo de cada
dedo e envia para o visualizador 3D no navegador via WebSocket.

Uso:
    python main.py              # câmera 0
    python main.py --camera 1   # outra câmera
    python main.py --no-browser # não abre o navegador automaticamente
    python main.py --swap-hands # se esquerda/direita saírem trocadas
"""

import argparse
import time
import webbrowser
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    HandLandmarksConnections,
    RunningMode,
)

from hand_angles import FINGERS, Smoother, detect_gesture, finger_angles
from server import HandBroadcaster, start_http

MODEL_PATH = Path(__file__).parent / "models" / "hand_landmarker.task"
HTTP_PORT = 8000
WS_PORT = 8765
SEND_FPS = 30

MAGENTA = (255, 0, 255)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
SIDES = ("left", "right")
SIDE_LABEL = {"left": "ESQ", "right": "DIR"}


def assign_sides(result, swap=False):
    """Devolve {"left": i, "right": j} com o índice de cada mão detectada.

    O MediaPipe assume imagem espelhada (selfie), que é o nosso caso após o
    flip. Se as duas mãos vierem com o mesmo rótulo (acontece quando elas se
    cruzam), decide pela posição na tela: a mais à esquerda é a esquerda.
    """
    labels = []
    for i, cats in enumerate(result.handedness):
        side = cats[0].category_name.lower()
        if swap:
            side = "left" if side == "right" else "right"
        labels.append(side)

    if len(labels) == 2 and labels[0] == labels[1]:
        by_x = sorted(range(2), key=lambda i: result.hand_landmarks[i][0].x)
        return {"left": by_x[0], "right": by_x[1]}
    return {side: i for i, side in enumerate(labels)}


def draw_hand(img, landmarks, label=""):
    h, w = img.shape[:2]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    for c in HandLandmarksConnections.HAND_CONNECTIONS:
        cv2.line(img, pts[c.start], pts[c.end], WHITE, 1, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, 3, MAGENTA, cv2.FILLED)

    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = 20
    cv2.rectangle(img, (min(xs) - pad, min(ys) - pad), (max(xs) + pad, max(ys) + pad), MAGENTA, 2)
    cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    cv2.circle(img, (cx, cy), 6, GREEN, cv2.FILLED)
    if label:
        cv2.putText(img, label, (min(xs) - pad, min(ys) - pad - 10),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, MAGENTA, 2)


def draw_hud(img, hands, fps):
    """Ângulos da mão esquerda no canto esquerdo e da direita no direito."""
    h, w = img.shape[:2]
    cv2.putText(img, f"FPS {fps:.0f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2)
    for side, x in (("left", 10), ("right", w - 170)):
        hand = hands[side]
        if not hand:
            continue
        for i, f in enumerate(FINGERS):
            cv2.putText(img, f"{f:>6}: {hand['angles'][f]:3d}", (x, 55 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 2)
        if hand["gesture"]:
            cv2.putText(img, hand["gesture"], (x, h - 20), cv2.FONT_HERSHEY_DUPLEX, 1.0, MAGENTA, 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--swap-hands", action="store_true",
                        help="inverte esquerda/direita caso saiam trocadas")
    args = parser.parse_args()

    if not MODEL_PATH.exists():
        raise SystemExit(
            f"Modelo não encontrado em {MODEL_PATH}.\n"
            "Baixe com:\n  curl -L -o models/hand_landmarker.task "
            "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
            "hand_landmarker/float16/latest/hand_landmarker.task"
        )

    start_http(HTTP_PORT)
    ws = HandBroadcaster(WS_PORT)
    url = f"http://localhost:{HTTP_PORT}"
    print(f"Visualizador: {url}  |  WebSocket: ws://localhost:{WS_PORT}")
    if not args.no_browser:
        webbrowser.open(url)

    landmarker = HandLandmarker.create_from_options(HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    ))

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"Não foi possível abrir a câmera {args.camera}")

    smoothers = {side: Smoother(alpha=0.4) for side in SIDES}
    t0 = time.monotonic()
    last_send = 0.0
    prev_frame = time.monotonic()
    fps = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao ler a câmera") 
            break
        frame = cv2.flip(frame, 1)  # efeito espelho

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(image, int((time.monotonic() - t0) * 1000))

        hands = {"left": None, "right": None}
        sides = assign_sides(result, args.swap_hands)
        for side in SIDES:
            if side not in sides:
                smoothers[side].reset()
                continue
            i = sides[side]
            draw_hand(frame, result.hand_landmarks[i], SIDE_LABEL[side])
            world = result.hand_world_landmarks[i]
            angles = smoothers[side](finger_angles(world))
            hands[side] = {"angles": angles, "gesture": detect_gesture(angles, world)}

        now = time.monotonic()
        if now - last_send >= 1 / SEND_FPS:
            ws.send({"hands": hands})
            last_send = now

        fps = 0.9 * fps + 0.1 / max(now - prev_frame, 1e-6)
        prev_frame = now
        draw_hud(frame, hands, fps)

        cv2.imshow("Webcam", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty("Webcam", cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()


if __name__ == "__main__":
    main()
