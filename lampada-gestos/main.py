"""Controle da lâmpada inteligente com gestos da mão.

Gestos (segure por meio segundo até o anel de progresso fechar):
    Mão aberta                  -> liga
    Punho fechado               -> desliga
    Joinha                      -> modo foco (branco frio, 100%)
    Paz e amor (V)              -> troca a temperatura do branco
    Rock (indicador + mindinho) -> troca a cor
    Pinça (polegar + indicador, outros dedos fechados) -> regula o brilho

Uso:
    python main.py              # usa a lâmpada do lamp_config.json
    python main.py --fake       # lâmpada simulada, só na tela
    python main.py --camera 1   # outra câmera
"""

import argparse
import time

import cv2

from controller import GestureController
from hand_tracking import HandTracker, Smoother, detect_gesture, draw_hand, finger_angles
from hud import draw_controls, draw_fps, draw_lamp
from lamp import load_lamp

WINDOW = "Lampada por gestos"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--fake", action="store_true", help="usa uma lâmpada simulada")
    args = parser.parse_args()

    lamp = load_lamp(fake=args.fake)
    ctrl = GestureController(lamp)
    tracker = HandTracker()
    smoother = Smoother(alpha=0.5)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"Não foi possível abrir a câmera {args.camera}")

    t0 = prev = time.monotonic()
    fps = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Falha ao ler a câmera")
            break
        frame = cv2.flip(frame, 1)  # efeito espelho
        now = time.monotonic()

        hand = tracker.detect(frame, int((now - t0) * 1000))
        landmarks = None
        if hand:
            landmarks, world = hand
            angles = smoother(finger_angles(world))
            ctrl.update(detect_gesture(angles), angles, world, now)
            draw_hand(frame, landmarks)
        else:
            smoother.reset()
            ctrl.update("", None, None, now)

        fps = 0.9 * fps + 0.1 / max(now - prev, 1e-6)
        prev = now
        draw_lamp(frame, lamp)
        draw_controls(frame, ctrl, landmarks, now)
        draw_fps(frame, fps)

        cv2.imshow(WINDOW, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()
    tracker.close()


if __name__ == "__main__":
    main()
