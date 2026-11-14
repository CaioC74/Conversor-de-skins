from pathlib import Path
import numpy as np
from PIL import Image
from paletas import ler_cor, criar_paleta, detectar_faixa, aplicar_imagem, aplicar_cor

pasta = Path(__file__).parent
saida = pasta / "teste_paletas"
saida.mkdir(exist_ok=True)

# 1) formatos de cor aceitos
for texto in ["#33cc55", "33CC55", "120", "verde", "#a0c8a0"]:
    h, s = ler_cor(texto)
    print(f"ler_cor({texto!r:10}) -> matiz {h:6.1f}°, saturação {s:.2f}")

# 2) um "céu" de azuis (imitando uma skin de gelo) para testar a detecção
H = np.tile(np.linspace(185 / 360 * 255, 225 / 360 * 255, 300), (100, 1))
V = np.repeat(np.linspace(255, 40, 100)[:, None], 300, axis=1)
S = np.full_like(H, 190)
gelo = Image.fromarray(np.stack([H, S, V], axis=-1).astype(np.uint8), "HSV").convert("RGBA")

de, ate, pico = detectar_faixa([gelo])
print(f"\ncor detectada: pico {pico}°, faixa {de}° até {ate}°")

# 3) aplicar várias cores escolhidas pelo usuário
for cor in ["verde", "#ff3300", "roxo", "#d4af37", "#a0c8a0"]:
    cfg = criar_paleta(cor, de, ate)
    nova, trocados = aplicar_imagem(gelo, cfg)
    quadro = Image.new("RGBA", (300, 210), (20, 20, 20, 255))
    quadro.alpha_composite(gelo, (0, 0))
    quadro.alpha_composite(nova, (0, 110))
    nome = cor.strip("#")
    quadro.save(saida / f"{nome}.png")
    exemplo = tuple(round(c, 2) for c in aplicar_cor(0.5, 0.91, 1.0, 1.0, cfg)[:3])
    print(f"{cor:9s} -> {trocados} pixels trocados | azul-gelo (0.5, 0.91, 1.0) vira {exemplo}")

print("\nvermelho fora da faixa (não muda):", aplicar_cor(1.0, 0.0, 0.0, 1.0, criar_paleta("verde", de, ate)))