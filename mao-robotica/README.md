# Robot Hands — Controle de Mão Robótica 3D por Gestos

Recriação do projeto do Murtaza's Workshop: a webcam rastreia suas mãos (até
duas), o Python calcula o ângulo de cada dedo e duas mãos robóticas 3D no navegador copiam seus movimentos em tempo real.

```
Webcam ─► OpenCV + MediaPipe ─► ângulos 0–180° ─► WebSocket ─► Three.js (navegador)
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

O modelo de mãos do MediaPipe (~7 MB) é baixado sozinho para `models/` na
primeira execução.

## Uso

```bash
python main.py              # abre a webcam e o visualizador em http://localhost:8000
python main.py --camera 1   # usar outra câmera
python main.py --swap-hands # se a mão esquerda mexer o robô da direita
```

A tela funciona como um espelho: sua mão direita controla o robô da direita.
Se na sua câmera sair invertido, use `--swap-hands`.

Pressione `q` ou `Esc` na janela da webcam para sair. O botão **Demo** no
visualizador anima as duas mãos sem precisar da câmera.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `main.py` | Loop da webcam, rastreamento das mãos (esquerda/direita), desenho e envio dos dados |
| `hand_angles.py` | Converte os 21 pontos da mão em ângulos de servo e detecta gestos |
| `server.py` | Servidor HTTP (página) e WebSocket (dados) em segundo plano |
| `viewer/index.html` | Duas mãos robóticas 3D (Three.js), painel de ângulos e gesto de cada mão |

Mensagem enviada pelo WebSocket (a mão ausente vem como `null`):

```json
{"hands": {"left": null, "right": {"angles": {"thumb": 117, "index": 14, "middle": 19, "ring": 170, "pinky": 172}, "gesture": "PEACE"}}}
```

## Ajustes

Em `hand_angles.py`:
- `MAX_FINGER_BEND` / `FINGER_REST_BEND` — calibração de dedo fechado/esticado.
- `EXTENDED_THRESHOLD` — limite para considerar o dedo esticado nos gestos.

Gestos reconhecidos: OPEN, FIST, PEACE, POINT, THUMBS UP, ROCK, LOVE, CALL ME, GUN, THREE, FOUR, OK.

## Próximo passo: mão física

Os ângulos já estão na escala de servo (0° esticado, 180° fechado). Para uma mão
real, basta enviar `angles` por serial (pyserial) para um Arduino com 5 servos.
