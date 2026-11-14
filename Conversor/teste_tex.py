from pathlib import Path
from collections import Counter
import zipfile, sys
from wad import ler_wad, descomprimir
from tex import eh_textura, info_textura, ler_textura, gravar_textura, FormatoNaoSuportado
from paletas import detectar_faixa

if len(sys.argv) < 2:
    sys.exit("uso: python teste_tex.py <arquivo.fantome>")
z = zipfile.ZipFile(sys.argv[1])

formatos = Counter()
problemas = []
imagens = []
for nome in [n for n in z.namelist() if n.lower().endswith(".wad.client")]:
    _, entradas = ler_wad(z.read(nome))
    for e in entradas:
        dados = descomprimir(e)
        if dados is None or not eh_textura(dados):
            continue
        try:
            i = info_textura(dados)
            img = ler_textura(dados)
            novo = gravar_textura(img, dados)
        except FormatoNaoSuportado as erro:
            problemas.append(f"{e['hash']:016x}: {erro}")
            continue
        formatos[f"{i['tipo']} {i['fmt']} ({'com' if i['mips'] > 1 else 'sem'} mipmaps)"] += 1
        if len(novo) != len(dados):
            problemas.append(f"{e['hash']:016x}: tamanho {len(novo)} != {len(dados)}")
        ler_textura(novo)
        imagens.append(img)

print("texturas por formato:")
for f, n in formatos.most_common():
    print(f"  {n:4d}  {f}")
print("problemas:", problemas or "nenhum")

de, ate, pico = detectar_faixa(imagens)
print(f"cor principal da skin: {pico}° (faixa {de}° a {ate}°)")