# Lâmpada por Gestos (Tuya / Smart Life)

Controle a lâmpada inteligente do escritório com a mão. A webcam rastreia a mão
com MediaPipe, o Python reconhece o gesto e manda o comando para a lâmpada
pela **rede local**, sem passar pela nuvem.

```
Webcam ─► MediaPipe ─► gesto ─► GestureController ─► tinytuya (thread) ─► lâmpada Wi-Fi
```

| Gesto (segure ~0,5 s) | Ação |
|---|---|
| ✋ Mão aberta | Liga |
| ✊ Punho fechado | Desliga |
| 👍 Joinha | Modo foco: branco frio, 100% |
| ✌️ Paz e amor | Troca o branco: quente → neutro → frio |
| 🤘 Rock | Troca a cor: vermelho, laranja, verde, azul, roxo, rosa |
| 🤏 Pinça (médio, anelar e mindinho fechados) | Regula o brilho pela distância polegar–indicador |

Um anel em volta do pulso mostra o progresso do gesto, e o mesmo gesto só
dispara de novo depois que você troca de gesto. No canto da tela aparece uma
lâmpada virtual com o estado atual.

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
python main.py --fake       # lâmpada simulada, para testar sem hardware
python main.py              # lâmpada de verdade (precisa do lamp_config.json)
python main.py --camera 1   # outra câmera
```

Pressione `q` ou `Esc` para sair.

## Configurar a lâmpada Tuya

O controle local precisa do **Device ID**, do **IP** e da **Local Key** da
lâmpada. Isso é feito uma vez só. Rode os comandos **dentro desta pasta**,
porque o tinytuya salva os arquivos onde ele é executado.

1. Crie uma conta em <https://platform.tuya.com> e vá em **Cloud → Development
   → Create Cloud Project** (*Smart Home*, data center **Western America**).
2. Na aba **Devices → Link App Account**, escaneie o QR code com o app Smart Life
   (Eu → ícone de scanner). A lâmpada aparece na lista.
3. Na aba **Overview**, copie o **Access ID** (API Key) e o **Access Secret**.
   Se der o erro *"your ip don't have access to this API"*, desative a
   **IP Allowlist** do projeto.
4. Rode o assistente e cole os dados (região `us`):
   ```bash
   python -m tinytuya wizard
   ```
   Ele gera o `devices.json` com o `id` e a `key` da lâmpada.
5. Descubra o IP da lâmpada na sua rede (não use o IP que a nuvem mostra, que é
   o da sua internet):
   ```bash
   python -m tinytuya scan
   ```
6. Copie `lamp_config.exemplo.json` para `lamp_config.json` e preencha com
   `id`, `key`, o IP `192.168.x.x` e a `version` mostrada no scan.

Dicas:
- Reserve um IP fixo para a lâmpada no roteador (reserva DHCP).
- Se você parear a lâmpada de novo no app, a Local Key muda e é preciso
  rodar o wizard outra vez.
- `lamp_config.json`, `devices.json`, `tinytuya.json`, `snapshot.json` e
  `tuya-raw.json` têm suas chaves e estão no `.gitignore`.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `main.py` | Loop da webcam: junta tudo |
| `hand_tracking.py` | MediaPipe, abertura de cada dedo, gestos e pinça |
| `controller.py` | Regras: segurar o gesto, dimmer, presets de cor |
| `lamp.py` | Lâmpada Tuya (rede local, em thread) e a simulada |
| `hud.py` | Lâmpada virtual, anel de progresso e barra de brilho |

## Ajustes

Em `controller.py`:
- `HOLD_TIME`: quanto tempo segurar o gesto.
- `PINCH_MIN` / `PINCH_MAX`: abertura da pinça para 1% e 100% de brilho.
- `DIMMER_SEND_HZ`: comandos de brilho por segundo (a Tuya engasga acima de ~5).
- `WHITE_PRESETS` / `COLOUR_PRESETS`: as cores de cada gesto.

Em `hand_tracking.py`:
- `EXTENDED_THRESHOLD`: limite para considerar o dedo esticado.
- `GESTURES`: quais combinações de dedos viram qual gesto.
