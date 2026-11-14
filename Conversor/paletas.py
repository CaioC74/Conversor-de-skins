"""
Paletas de cor do conversor.

A pessoa escolhe UMA cor (hex, nome ou matiz em graus) e o conversor
troca as cores principais da skin por ela, mantendo luz e sombra.

Matiz (H) em graus, no círculo de cores:
    0 = vermelho   30 = laranja   60 = amarelo   90 = verde-limão
  120 = verde     180 = ciano    240 = azul     280 = roxo     330 = rosa
"""
import colorsys
import numpy as np
from PIL import Image

# ============================================================
# VALORES PADRÃO: mude aqui para alterar o comportamento geral
# ============================================================
PADRAO = {
    # Degradê pelo brilho, em graus de matiz.
    # As partes escuras vão para (cor + variacao/2) e as claras para (cor - variacao/2).
    # Ex.: verde 110 com variação 60 -> escuras 140 (floresta), claras 80 (limão).
    # Use negativo para inverter (laranja 20 com -40 -> escuras 0 vermelhas, claras 40 douradas).
    # 0 = a cor inteira fica com uma matiz só.
    "variacao": 30,

    # Saturação nova = saturação antiga * reforco + extra (limitada a 1).
    # Maiores deixam a cor mais viva; reforco 1 e extra 0 = mantém a da skin.
    "reforco_saturacao": 1.2,
    "saturacao_extra": 0.1,

    # Pixels com saturação abaixo disso são considerados cinza e NÃO mudam.
    # Aumente (ex.: 0.15) para trocar só as partes bem coloridas.
    "saturacao_minima": 0.08,

    # Detecção automática da cor original da skin (ver detectar_faixa):
    "deteccao_limiar": 0.03,   # quão "fraca" uma matiz pode ser para ainda contar (3% do pico)
    "deteccao_margem": 15,     # graus extras de folga em cada lado da faixa detectada
}

# Nomes aceitos em --cor
NOMES = {
    "vermelho": 0, "laranja": 25, "dourado": 45, "amarelo": 55, "limao": 85,
    "verde": 120, "esmeralda": 145, "ciano": 185, "azul": 225, "anil": 250,
    "roxo": 275, "magenta": 305, "rosa": 330,
}

def ler_cor(texto):
    """'#33cc55', '33cc55', '120' ou 'verde'  ->  (matiz em graus, saturação 0..1)."""
    t = str(texto).strip().lower()
    if t in NOMES:
        return float(NOMES[t]), 1.0
    try:
        return float(t) % 360, 1.0
    except ValueError:
        pass
    t = t.lstrip("#")
    if len(t) == 6:
        r, g, b = (int(t[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, s, _v = colorsys.rgb_to_hsv(r, g, b)
        return h * 360, s
    raise ValueError(f"cor inválida: {texto!r} (use #RRGGBB, graus 0-360 ou um nome: {', '.join(NOMES)})")

def criar_paleta(cor, origem_de, origem_ate, **ajustes):
    """Monta a configuração da paleta. 'ajustes' sobrescreve qualquer valor de PADRAO."""
    cfg = {**PADRAO, **ajustes}
    matiz, saturacao = ler_cor(cor)
    cfg["origem_de"] = origem_de
    cfg["origem_ate"] = origem_ate
    cfg["cor_escura"] = matiz + cfg["variacao"] / 2
    cfg["cor_clara"] = matiz - cfg["variacao"] / 2
    # Cor escolhida bem viva (saturação >= 0.6) não reduz nada;
    # cor acinzentada/pastel deixa o resultado proporcionalmente mais suave.
    cfg["fator_saturacao"] = min(1.0, saturacao / 0.6)
    return cfg

# ============================================================
# Daqui para baixo é o "motor": não precisa mexer para mudar cores.
# ============================================================

def _hsv(img):
    hsv = np.array(img.convert("RGB").convert("HSV"), dtype=float) / 255
    return hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]

def detectar_faixa(imagens, cfg=PADRAO):
    """
    Descobre a cor principal de um conjunto de imagens.
    Devolve (origem_de, origem_ate, pico) em graus.
    """
    hist = np.zeros(360)
    for img in imagens:
        H, S, V = _hsv(img)
        A = np.array(img.getchannel("A"), dtype=float) / 255
        colorido = S > 0.15
        peso = (S * V * A)[colorido]
        np.add.at(hist, H[colorido].astype(int) % 360, peso)
    if hist.sum() == 0:
        raise ValueError("nenhuma cor encontrada (imagens só em tons de cinza?)")

    janela = np.ones(15) / 15
    suave = np.convolve(np.concatenate([hist[-7:], hist, hist[:7]]), janela, "valid")
    pico = int(suave.argmax())
    limite = suave[pico] * cfg["deteccao_limiar"]

    esq = pico
    while suave[(esq - 1) % 360] > limite and pico - esq < 170:
        esq -= 1
    dir_ = pico
    while suave[(dir_ + 1) % 360] > limite and dir_ - pico < 170:
        dir_ += 1

    m = cfg["deteccao_margem"]
    return (esq - m) % 360, (dir_ + m) % 360, pico

def aplicar_imagem(img, cfg):
    """Aplica a paleta numa imagem RGBA. Devolve (imagem nova, pixels trocados)."""
    alpha = img.getchannel("A")
    H, S, V = _hsv(img)

    de, ate = cfg["origem_de"], cfg["origem_ate"]
    if de <= ate:
        na_faixa = (H >= de) & (H <= ate)
    else:
        na_faixa = (H >= de) | (H <= ate)
    trocar = na_faixa & (S > cfg["saturacao_minima"])

    novo_H = (cfg["cor_escura"] + (cfg["cor_clara"] - cfg["cor_escura"]) * V) % 360
    novo_S = np.clip(S * cfg["reforco_saturacao"] + cfg["saturacao_extra"], 0, 1) * cfg["fator_saturacao"]

    H = np.where(trocar, novo_H, H)
    S = np.where(trocar, novo_S, S)

    hsv = np.stack([H / 360, S, V], axis=-1)
    nova = Image.fromarray((hsv * 255).round().astype(np.uint8), "HSV").convert("RGB")
    nova.putalpha(alpha)
    return nova, int(trocar.sum())

def aplicar_cor(r, g, b, a, cfg):
    """Aplica a paleta numa cor do .bin (floats, podem passar de 1)."""
    pico = max(r, g, b, 1.0)
    px = tuple(round(min(1.0, max(0.0, c / pico)) * 255) for c in (r, g, b))
    pixel = Image.new("RGBA", (1, 1), px + (255,))
    nova, trocados = aplicar_imagem(pixel, cfg)
    if trocados == 0:
        return (r, g, b, a)
    nr, ng, nb, _ = nova.getpixel((0, 0))
    return (nr / 255 * pico, ng / 255 * pico, nb / 255 * pico, a)