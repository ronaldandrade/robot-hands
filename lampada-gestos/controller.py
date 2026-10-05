"""Transforma os gestos da mão em comandos para a lâmpada."""

from collections import deque

import numpy as np

from hand_tracking import EXTENDED_THRESHOLD, pinch_ratio

HOLD_TIME = 0.5        # segundos segurando o gesto para disparar
DIMMER_ENTER = 0.3     # segundos na posição de pinça para entrar no modo brilho
DIMMER_SEND_HZ = 5     # comandos de brilho por segundo (a Tuya não aguenta muito mais)
DIMMER_UNDO = 0.35     # ao sair do modo, volta ao brilho de X segundos atrás
# Distância polegar-indicador / tamanho da palma que vale 1% e 100% de brilho
PINCH_MIN = 0.25
PINCH_MAX = 1.20

WHITE_PRESETS = [("QUENTE", 0), ("NEUTRO", 50), ("FRIO", 100)]
COLOUR_PRESETS = [
    ("VERMELHO", (255, 0, 0)),
    ("LARANJA", (255, 100, 0)),
    ("VERDE", (0, 255, 0)),
    ("AZUL", (0, 60, 255)),
    ("ROXO", (160, 0, 255)),
    ("ROSA", (255, 0, 140)),
]

# Gestos que disparam uma ação, com o texto mostrado na tela
GESTURE_LABEL = {
    "OPEN": "LIGAR",
    "FIST": "DESLIGAR",
    "THUMBS UP": "MODO FOCO",
    "PEACE": "TEMPERATURA",
    "ROCK": "COR",
}


def is_pinch_pose(angles):
    """Médio, anelar e mindinho fechados; indicador livre para fazer a pinça."""
    folded = all(angles[f] > EXTENDED_THRESHOLD for f in ("middle", "ring", "pinky"))
    return folded and angles["index"] < 110


class GestureController:
    """Um gesto só dispara depois de ficar estável por HOLD_TIME, e não dispara
    de novo até você trocar de gesto (ou tirar a mão da câmera)."""

    def __init__(self, lamp):
        self.lamp = lamp
        self.current = ""
        self.since = 0.0
        self.fired = False
        self.white_idx = 1
        self.colour_idx = -1
        self.dimmer = False
        self.dimmer_history = deque()
        self.last_dim_send = 0.0
        self.toast = ("", 0.0)  # (mensagem na tela, horário)

    def progress(self, now):
        """0-1: quanto falta para o gesto atual disparar."""
        if self.fired:
            return 1.0
        if self.current not in GESTURE_LABEL:
            return 0.0
        return min(1.0, (now - self.since) / HOLD_TIME)

    def update(self, gesture, angles, world, now):
        """Chamar a cada frame. Sem mão na câmera: gesture="" e angles=None."""
        pose = "PINCH" if angles and is_pinch_pose(angles) else gesture
        if pose != self.current:
            self._leave_dimmer(now)
            self.current, self.since, self.fired = pose, now, False

        if pose == "PINCH":
            if now - self.since >= DIMMER_ENTER:
                self._dim(world, now)
        elif pose in GESTURE_LABEL and not self.fired and now - self.since >= HOLD_TIME:
            self.fired = True
            self.toast = (self._fire(pose), now)

    def _fire(self, gesture):
        lamp = self.lamp
        if gesture == "OPEN":
            lamp.turn_on()
            return "LIGADA"
        if gesture == "FIST":
            lamp.turn_off()
            return "DESLIGADA"
        if gesture == "THUMBS UP":
            lamp.turn_on()
            lamp.set_white(100, brightness=100)
            return "MODO FOCO"
        if gesture == "PEACE":
            self.white_idx = (self.white_idx + 1) % len(WHITE_PRESETS)
            name, temp = WHITE_PRESETS[self.white_idx]
            lamp.turn_on()
            lamp.set_white(temp)
            return f"BRANCO {name}"
        if gesture == "ROCK":
            self.colour_idx = (self.colour_idx + 1) % len(COLOUR_PRESETS)
            name, rgb = COLOUR_PRESETS[self.colour_idx]
            lamp.turn_on()
            lamp.set_colour(rgb)
            return name
        return ""

    def _dim(self, world, now):
        pct = float(np.interp(pinch_ratio(world), [PINCH_MIN, PINCH_MAX], [1, 100]))
        self.dimmer = True
        self.dimmer_history.append((now, pct))
        while now - self.dimmer_history[0][0] > 2.0:
            self.dimmer_history.popleft()
        self.lamp.state.brightness = int(pct)  # a tela responde na hora
        if now - self.last_dim_send >= 1 / DIMMER_SEND_HZ:
            if not self.lamp.state.on:
                self.lamp.turn_on()
            self.lamp.set_brightness(pct)
            self.last_dim_send = now

    def _leave_dimmer(self, now):
        """Ao desfazer a pinça os dedos se mexem e o brilho pularia.
        Por isso volta ao valor de DIMMER_UNDO segundos antes de sair."""
        if not self.dimmer:
            return
        self.dimmer = False
        target = None
        for t, pct in self.dimmer_history:
            if now - t >= DIMMER_UNDO:
                target = pct
        self.dimmer_history.clear()
        if target is not None:
            self.lamp.set_brightness(target)
            self.toast = (f"BRILHO {int(target)}%", now)
