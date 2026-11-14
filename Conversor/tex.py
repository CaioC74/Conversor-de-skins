"""Leitura e escrita de texturas do LoL: .tex (formato da Riot) e .dds."""
import struct, io
from PIL import Image

class FormatoNaoSuportado(Exception):
    """Textura num formato que este código não sabe ler/gravar."""

FORMATOS_TEX = {10: "DXT1", 12: "DXT5", 20: "BGRA8"}

def eh_textura(dados):
    return dados[:4] in (b"TEX\x00", b"DDS ")

# ---------------- utilidades comuns ----------------

def _tamanho_nivel(w, h, fmt):
    if fmt == "BGRA8":
        return w * h * 4
    blocos = max(1, (w + 3) // 4) * max(1, (h + 3) // 4)
    return blocos * (8 if fmt == "DXT1" else 16)

def _niveis(w, h, qtd=None):
    """Tamanhos dos mipmaps do maior pro menor. qtd=None -> até 1x1."""
    lista = [(w, h)]
    while (w, h) != (1, 1) and (qtd is None or len(lista) < qtd):
        w, h = max(1, w // 2), max(1, h // 2)
        lista.append((w, h))
    return lista

def _cabecalho_dds(w, h, fmt):
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    struct.pack_into("<IIIIIII", hdr, 4, 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, 0, 0, 0)
    struct.pack_into("<II4s", hdr, 76, 32, 0x4, fmt.encode())
    struct.pack_into("<I", hdr, 108, 0x1000)
    return bytes(hdr)

def _decodificar(pixels, w, h, fmt):
    if fmt == "BGRA8":
        return Image.frombytes("RGBA", (w, h), pixels, "raw", "BGRA")
    return Image.open(io.BytesIO(_cabecalho_dds(w, h, fmt) + pixels)).convert("RGBA")

def _codificar(img, fmt):
    if fmt == "BGRA8":
        return img.tobytes("raw", "BGRA")
    buf = io.BytesIO()
    img.save(buf, "DDS", pixel_format=fmt)
    return buf.getvalue()[128:]

def _codificar_niveis(img, fmt, niveis):
    """Uma lista de bytes, um item por mipmap, na mesma ordem de 'niveis'."""
    partes = []
    for (a, b) in niveis:
        nivel = img if (a, b) == img.size else img.resize((a, b), Image.LANCZOS)
        partes.append(_codificar(nivel, fmt)[:_tamanho_nivel(a, b, fmt)])
    return partes

# ---------------- leitura de informações ----------------

def info_textura(dados):
    """Lê só o cabeçalho: tipo, largura, altura, formato e quantidade de mipmaps."""
    if dados[:4] == b"TEX\x00":
        w, h, _, codigo, _, flags = struct.unpack_from("<HHBBBB", dados, 4)
        if codigo not in FORMATOS_TEX:
            raise FormatoNaoSuportado(f".tex com formato {codigo}")
        mips = len(_niveis(w, h)) if flags & 1 else 1
        return {"tipo": "tex", "w": w, "h": h, "fmt": FORMATOS_TEX[codigo], "mips": mips}

    if dados[:4] == b"DDS ":
        flags, h, w = struct.unpack_from("<III", dados, 8)
        (mips,) = struct.unpack_from("<I", dados, 28)
        fourcc = dados[84:88]
        if fourcc not in (b"DXT1", b"DXT5"):
            raise FormatoNaoSuportado(f".dds com formato {fourcc!r}")
        mips = mips if (flags & 0x20000 and mips > 1) else 1
        return {"tipo": "dds", "w": w, "h": h, "fmt": fourcc.decode(), "mips": mips}

    raise FormatoNaoSuportado("não é textura")

# ---------------- ler e gravar ----------------

def ler_textura(dados):
    """Bytes de .tex/.dds -> imagem RGBA (o maior mipmap)."""
    i = info_textura(dados)
    tam = _tamanho_nivel(i["w"], i["h"], i["fmt"])
    if i["tipo"] == "tex":
        corpo = dados[12:]
        pixels = corpo[-tam:] if i["mips"] > 1 else corpo[:tam]   # .tex: maior no FIM
    else:
        pixels = dados[128:128 + tam]                              # .dds: maior no COMEÇO
    return _decodificar(pixels, i["w"], i["h"], i["fmt"])

def gravar_textura(img, original):
    """Imagem -> bytes no MESMO formato/tamanho/mipmaps do arquivo original."""
    i = info_textura(original)
    img = img.convert("RGBA")
    if img.size != (i["w"], i["h"]):
        raise ValueError(f"tamanho mudou: {img.size} != {(i['w'], i['h'])}")

    niveis = _niveis(i["w"], i["h"], i["mips"])
    partes = _codificar_niveis(img, i["fmt"], niveis)

    if i["tipo"] == "tex":
        return original[:12] + b"".join(reversed(partes))   # menor -> maior
    return original[:128] + b"".join(partes)                # maior -> menor