# Robot Hands: projetos de visão computacional com as mãos

Projetos que usam a webcam e o MediaPipe para rastrear a mão e transformar
gestos em ação. Cada pasta é independente, com seu próprio README e
`requirements.txt`.

| Pasta | Projeto |
|---|---|
| [`mao-robotica/`](mao-robotica/) | Duas mãos robóticas 3D no navegador que copiam os seus dedos |
| [`lampada-gestos/`](lampada-gestos/) | Controle da lâmpada inteligente (Tuya / Smart Life) com gestos |

## Começo rápido

Um único ambiente virtual na raiz serve para os dois:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mao-robotica/requirements.txt -r lampada-gestos/requirements.txt

# a partir da raiz, rode um dos dois:
(cd mao-robotica && python main.py)           # mão robótica
(cd lampada-gestos && python main.py --fake)  # lâmpada (simulada)
```
