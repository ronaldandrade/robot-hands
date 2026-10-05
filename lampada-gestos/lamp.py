"""Drivers da lâmpada: Tuya/Smart Life (rede local) e uma lâmpada simulada.

Os comandos de rede da Tuya levam de 100 a 500 ms. Para o vídeo não engasgar,
eles rodam numa thread separada. Se vários comandos de brilho chegam enquanto
a lâmpada ainda responde, só o mais recente é enviado.
"""

import json
import threading
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "lamp_config.json"


class LampState:
    """Estado que o app acredita que a lâmpada tem (usado no desenho da tela)."""

    def __init__(self):
        self.on = False
        self.brightness = 100       # 1-100 %
        self.mode = "white"         # "white" ou "colour"
        self.colourtemp = 50        # 0 = quente, 100 = fria
        self.rgb = (255, 255, 255)


class Lamp:
    """Interface comum. As subclasses implementam _apply()."""

    def __init__(self):
        self.state = LampState()
        self.error = ""
        self._pending = {}
        self._cond = threading.Condition()
        threading.Thread(target=self._worker, daemon=True).start()

    # --- API usada pelo app (não bloqueia) ---

    def turn_on(self):
        self.state.on = True
        self._queue("power", True)

    def turn_off(self):
        self.state.on = False
        self._queue("power", False)

    def set_brightness(self, pct):
        pct = int(max(1, min(100, pct)))
        self.state.brightness = pct
        self._queue("brightness", pct)

    def set_white(self, colourtemp, brightness=None):
        if brightness is not None:
            self.state.brightness = int(brightness)
        self.state.mode = "white"
        self.state.colourtemp = int(colourtemp)
        self._queue("white", (self.state.brightness, self.state.colourtemp))

    def set_colour(self, rgb):
        self.state.mode = "colour"
        self.state.rgb = tuple(rgb)
        self._queue("colour", self.state.rgb)

    # --- fila / thread ---

    def _queue(self, kind, value):
        """Fila em ordem de chegada; um comando novo substitui o pendente do
        mesmo tipo e vai para o fim da fila."""
        with self._cond:
            if kind in ("white", "colour"):
                # cor e branco se anulam
                self._pending.pop("white", None)
                self._pending.pop("colour", None)
            self._pending.pop(kind, None)
            self._pending[kind] = value
            self._cond.notify()

    def _worker(self):
        while True:
            with self._cond:
                while not self._pending:
                    self._cond.wait()
                kind = next(iter(self._pending))  # o mais antigo
                value = self._pending.pop(kind)
            try:
                self._apply(kind, value)
                self.error = ""
            except Exception as e:  # rede caiu, lâmpada fora do ar etc.
                self.error = str(e)[:60]
                print(f"[lamp] erro em {kind}={value}: {e}")

    def _apply(self, kind, value):
        raise NotImplementedError


class FakeLamp(Lamp):
    """Lâmpada simulada: só aparece na tela. Para testar sem hardware."""

    def _apply(self, kind, value):
        print(f"[lamp simulada] {kind} = {value}")


class TuyaLamp(Lamp):
    """Lâmpada Tuya / Smart Life controlada pela rede local com tinytuya."""

    def __init__(self, dev_id, ip, local_key, version=3.3):
        import tinytuya

        self.dev = tinytuya.BulbDevice(dev_id, ip, local_key, version=float(version))
        self.dev.set_socketPersistent(True)  # mantém a conexão aberta: bem mais rápido
        self.dev.set_socketTimeout(2)
        super().__init__()
        self._read_initial_state()

    def _read_initial_state(self):
        try:
            st = self.dev.state()
        except Exception as e:
            st = {"Error": str(e)}
        if "Error" in st:
            self.error = str(st["Error"])[:60]
            print(f"[lamp] não consegui ler o estado da lâmpada: {st['Error']}")
            return
        self.state.on = bool(st.get("is_on"))
        self.state.mode = "colour" if st.get("mode") == "colour" else "white"
        self.state.brightness = max(1, round(self.dev.get_brightness_percentage()))
        print(f"[lamp] conectado: ligada={self.state.on} brilho={self.state.brightness}%")

    def _check(self, result):
        if isinstance(result, dict) and "Error" in result:
            raise RuntimeError(result["Error"])

    def _apply(self, kind, value):
        d = self.dev
        if kind == "power":
            self._check(d.turn_on() if value else d.turn_off())
        elif kind == "brightness":
            self._check(d.set_brightness_percentage(value))
        elif kind == "white":
            brightness, temp = value
            self._check(d.set_white_percentage(brightness, temp))
        elif kind == "colour":
            self._check(d.set_colour(*value))


def load_lamp(fake=False):
    """Cria a lâmpada a partir do lamp_config.json (ou a simulada)."""
    if fake:
        return FakeLamp()
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"{CONFIG_PATH.name} não encontrado.\n"
            "Copie lamp_config.exemplo.json para lamp_config.json e preencha\n"
            "com os dados da sua lâmpada (veja o README), ou rode com --fake."
        )
    cfg = json.loads(CONFIG_PATH.read_text())
    return TuyaLamp(cfg["id"], cfg["ip"], cfg["key"], cfg.get("version", 3.3))
