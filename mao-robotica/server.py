"""Servidores em segundo plano:
- HTTP  (porta 8000): entrega a página do visualizador 3D (pasta viewer/)
- WebSocket (porta 8765): envia os ângulos dos dedos para o navegador
"""

import asyncio
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from websockets.asyncio.server import broadcast, serve

VIEWER_DIR = Path(__file__).parent / "viewer"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_http(port=8000):
    handler = partial(_QuietHandler, directory=str(VIEWER_DIR))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class HandBroadcaster:
    """Servidor WebSocket que roda num thread próprio com seu event loop."""

    def __init__(self, port=8765):
        self.port = port
        self.clients = set()
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        async with serve(self._handler, "0.0.0.0", self.port):
            self._ready.set()
            await asyncio.Future()  # roda para sempre

    async def _handler(self, ws):
        self.clients.add(ws)
        print(f"Viewer connected ({len(self.clients)})")
        try:
            await ws.wait_closed()
        finally:
            self.clients.discard(ws)
            print(f"Viewer disconnected ({len(self.clients)})")

    def send(self, data):
        """Pode ser chamado de qualquer thread."""
        if self.clients:
            msg = json.dumps(data)
            self.loop.call_soon_threadsafe(broadcast, set(self.clients), msg)
