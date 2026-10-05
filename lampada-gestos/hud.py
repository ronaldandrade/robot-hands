"""Desenhos na tela: lâmpada virtual, anel de progresso, barra de brilho."""

import cv2
import numpy as np

from controller import GESTURE_LABEL

MAGENTA = (255, 0, 255)
GREEN = (0, 255, 0)
WHITE = (255, 255, 255)
RED = (0, 0, 255)
FONT = cv2.FONT_HERSHEY_DUPLEX


def _centered_text(img, text, cx, y, scale, colour, thickness):
    (tw, _), _ = cv2.getTextSize(text, FONT, scale, thickness)
    cv2.putText(img, text, (cx - tw // 2, y), FONT, scale, colour, thickness, cv2.LINE_AA)


def light_colour(state):
    """Cor aproximada da luz da lâmpada (BGR)."""
    if state.mode == "colour":
        r, g, b = state.rgb
        return (b, g, r)
    warm, cold = np.array([80, 180, 255]), np.array([255, 240, 220])
    return tuple(int(v) for v in warm + (cold - warm) * state.colourtemp / 100)


def draw_lamp(img, lamp):
    """Lâmpada virtual no canto superior direito, com brilho proporcional."""
    h, w = img.shape[:2]
    cx, cy, r = w - 80, 80, 45
    st = lamp.state
    if st.on:
        k = 0.25 + 0.75 * st.brightness / 100
        colour = tuple(int(c * k) for c in light_colour(st))
        glow = img.copy()
        cv2.circle(glow, (cx, cy), int(r * (1.4 + k)), colour, cv2.FILLED)
        cv2.addWeighted(glow, 0.35 * k, img, 1 - 0.35 * k, 0, img)
        cv2.circle(img, (cx, cy), r, colour, cv2.FILLED)
    else:
        cv2.circle(img, (cx, cy), r, (60, 60, 60), cv2.FILLED)
    cv2.circle(img, (cx, cy), r, WHITE, 2, cv2.LINE_AA)
    cv2.rectangle(img, (cx - 18, cy + r - 2), (cx + 18, cy + r + 18), (150, 150, 150), cv2.FILLED)
    _centered_text(img, f"{st.brightness}%" if st.on else "OFF", cx, cy + r + 45, 0.7, WHITE, 2)

    if lamp.error:
        cv2.putText(img, f"erro: {lamp.error}", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, RED, 1)


def draw_controls(img, ctrl, landmarks, now):
    h, w = img.shape[:2]

    if landmarks is not None and ctrl.current in GESTURE_LABEL:
        # Anel de progresso em volta do pulso
        x, y = int(landmarks[0].x * w), int(landmarks[0].y * h)
        colour = GREEN if ctrl.fired else MAGENTA
        cv2.ellipse(img, (x, y), (35, 35), -90, 0, 360 * ctrl.progress(now), colour, 5, cv2.LINE_AA)
        _centered_text(img, GESTURE_LABEL[ctrl.current], x, y + 65, 0.8, WHITE, 2)

    if ctrl.dimmer:
        if landmarks is not None:
            # Linha da pinça
            a = (int(landmarks[4].x * w), int(landmarks[4].y * h))
            b = (int(landmarks[8].x * w), int(landmarks[8].y * h))
            cv2.line(img, a, b, GREEN, 3, cv2.LINE_AA)
            cv2.circle(img, ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2), 8, GREEN, cv2.FILLED)
        # Barra de brilho
        pct = ctrl.lamp.state.brightness
        x0, y0, y1 = 40, 150, h - 150
        cv2.rectangle(img, (x0, y0), (x0 + 30, y1), WHITE, 2)
        cv2.rectangle(img, (x0, int(y1 - (y1 - y0) * pct / 100)), (x0 + 30, y1), GREEN, cv2.FILLED)
        _centered_text(img, f"{pct}%", x0 + 15, y1 + 35, 0.8, WHITE, 2)

    msg, t = ctrl.toast
    if msg and now - t < 1.5:
        _centered_text(img, msg, w // 2, 70, 1.4, GREEN, 3)


def draw_fps(img, fps):
    cv2.putText(img, f"FPS {fps:.0f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREEN, 2)
