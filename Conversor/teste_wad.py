from pathlib import Path
from collections import Counter
import zipfile, sys
from wad import ler_wad, escrever_wad, descomprimir, tipo, NOMES_TIPO

if len(sys.argv) < 2:
    pasta = Path(__file__).parent
    achados = list(pasta.glob("*.fantome")) + list(pasta.parent.glob("*.fantome"))
    print("uso: python teste_wad.py <arquivo.fantome>")
    print("arquivos .fantome encontrados aqui perto:")
    for a in achados:
        print("  ", a)
    sys.exit(1)

FANTOME = Path(sys.argv[1])
if not FANTOME.exists():
    sys.exit(f"arquivo não encontrado: {FANTOME}")

z = zipfile.ZipFile(FANTOME)
wads = [n for n in z.namelist() if n.lower().endswith(".wad.client")]
print("WADs encontrados:", wads)

for nome in wads:
    print(f"\n=== {nome} ===")
    cab, entradas = ler_wad(z.read(nome))
    tipos = Counter(NOMES_TIPO.get(tipo(e), f"tipo {tipo(e)}") for e in entradas)
    print("arquivos:", len(entradas), "| compressões:", dict(tipos))
    originais = {e["hash"]: descomprimir(e) for e in entradas}
    print("todos descomprimidos sem erro")

    novo = escrever_wad(cab, entradas, {})
    _, releitura = ler_wad(novo)
    ok = all(descomprimir(e) == originais[e["hash"]] for e in releitura)
    print("teste 1 (sem mudanças) conteúdo igual:", ok, "| tamanho", len(novo), "vs", len(z.read(nome)))

    algum = next(h for h, d in originais.items() if d is not None)
    novo2 = escrever_wad(cab, entradas, {algum: originais[algum]})
    _, releitura2 = ler_wad(novo2)
    ok2 = all(descomprimir(e) == originais[e["hash"]] for e in releitura2)
    print("teste 2 (1 arquivo recomprimido) conteúdo igual:", ok2)