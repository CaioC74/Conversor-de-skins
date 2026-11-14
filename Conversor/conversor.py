"""
Conversor genérico de skins por cor.

Funciona com:
  - um .fantome (skin custom feita por fã)
  - o WAD do próprio jogo (ex.: Zed.wad.client), escolhendo a skin pelo número

Exemplos:
  python conversor.py "Minha Skin.fantome" --cor verde
  python conversor.py "Zed.wad.client" --skin 0 --cor "#33cc55"            (skin base)
  python conversor.py "Zed.wad.client" --skin 13 --cor roxo --variacao 60  (outra skin)
"""
import argparse, io, json, re, sys, zipfile
from collections import Counter
from pathlib import Path
from PIL import Image

from wad import Wad, escrever_wad, tipo, NOMES_TIPO
from tex import eh_textura, ler_textura, gravar_textura, FormatoNaoSuportado
from paletas import PADRAO, ler_cor, criar_paleta, detectar_faixa, aplicar_imagem
from recolor_bin import recolorir_bin
from skin import arquivos_da_skin, referencias, hash_caminho

# Pasta onde as skins geradas são salvas (criada automaticamente se não existir).
# Por padrão fica ao lado deste script; troque o nome/caminho se preferir.
PASTA_SAIDA = Path(__file__).parent / "Skin Custom"

# ---------------------------------------------------------------- parâmetros

def ler_parametros():
    p = argparse.ArgumentParser(description="Recolore uma skin (.fantome ou WAD do jogo) com a cor escolhida.")
    p.add_argument("entrada", help="arquivo .fantome OU o .wad.client do campeão (copiado da pasta do jogo)")
    p.add_argument("--cor", required=True, help="cor nova: #RRGGBB, graus 0-360 ou nome (verde, roxo...)")
    p.add_argument("--skin", type=int, default=0,
                   help="só para WAD do jogo: número da skin (0 = skin base). Padrão: 0")
    p.add_argument("--nome", help="nome do mod gerado")
    p.add_argument("--autor", default="custom", help="autor do mod (só para WAD do jogo)")
    p.add_argument("--saida", help="arquivo .fantome de saída (padrão: dentro da pasta 'Skin Custom')")
    p.add_argument("--variacao", type=float, default=PADRAO["variacao"],
                   help=f"degradê em graus entre escuro e claro (padrão {PADRAO['variacao']})")
    p.add_argument("--reforco", type=float, default=PADRAO["reforco_saturacao"],
                   help=f"multiplicador de saturação (padrão {PADRAO['reforco_saturacao']})")
    p.add_argument("--saturacao-minima", type=float, default=PADRAO["saturacao_minima"],
                   help=f"abaixo disso é cinza e não muda (padrão {PADRAO['saturacao_minima']})")
    p.add_argument("--origem-de", type=float, help="força o início da faixa de cores a trocar (pula a detecção)")
    p.add_argument("--origem-ate", type=float, help="força o fim da faixa de cores a trocar")
    return p.parse_args()

# ---------------------------------------------------------------- carregar a entrada

def carregar_fantome(caminho):
    """Todos os WADs do .fantome; todos os arquivos são processados."""
    z = zipfile.ZipFile(caminho)
    fontes = {}
    for nome in z.namelist():
        if nome.lower().endswith(".wad.client"):
            wad = Wad(z.read(nome))
            nomes = {}
            for h in wad.hashes():
                dados = wad.get(h)
                if dados and dados[:4] == b"PROP":
                    for c in referencias(dados)[0]:
                        nomes[hash_caminho(c)] = c
            fontes[nome] = {"wad": wad, "selecao": set(wad.hashes()), "nomes": nomes}
    if not fontes:
        sys.exit("nenhum .wad.client dentro do .fantome")
    return z, fontes

def carregar_wad_do_jogo(caminho, numero):
    """O WAD do campeão; só os arquivos da skin escolhida são processados."""
    campeao = caminho.name.split(".")[0]
    print(f"abrindo {caminho.name} (campeão: {campeao}) e procurando a skin {numero}...")
    wad = Wad(caminho.read_bytes())
    info = arquivos_da_skin(wad, campeao, numero)
    if not info["raizes"]:
        sys.exit(f"skin {numero} não encontrada neste WAD "
                 f"(procurei data/characters/<personagem>/skins/skin{numero}.bin)")
    print("  definições encontradas:", ", ".join(info["raizes"]))
    print(f"  arquivos ligados à skin: {len(info['hashes'])}")
    if info["compartilhados"]:
        print(f"  aviso: {info['compartilhados']} texturas ficam fora da pasta da skin "
              f"(compartilhadas); recolorir pode afetar outras skins também")
    fontes = {f"WAD/{caminho.name}": {"wad": wad, "selecao": info["hashes"], "nomes": info["nomes"]}}
    return campeao, fontes

# ---------------------------------------------------------------- principal

def main():
    args = ler_parametros()
    try:
        ler_cor(args.cor)
    except ValueError as erro:
        sys.exit(str(erro))
    entrada = Path(args.entrada)
    if not entrada.exists():
        sys.exit(f"arquivo não encontrado: {entrada}")

    nome_arquivo = entrada.name.lower()
    if nome_arquivo.endswith((".fantome", ".zip")):
        modo_jogo = False
        z, fontes = carregar_fantome(entrada)
    elif nome_arquivo.endswith(".wad.client"):
        modo_jogo = True
        campeao, fontes = carregar_wad_do_jogo(entrada, args.skin)
    else:
        sys.exit("entrada precisa ser .fantome ou .wad.client")

    # 1) ler as texturas selecionadas (servem pra detectar a cor e pra recolorir)
    relatorio = {nome: Counter() for nome in fontes}
    problemas = []
    imagens = {}
    for nome, f in fontes.items():
        wad = f["wad"]
        relatorio[nome].update(NOMES_TIPO.get(tipo(wad.por_hash[h]), "?") for h in f["selecao"])
        for h in f["selecao"]:
            dados = wad.get(h)
            if dados is not None and eh_textura(dados):
                try:
                    imagens[(nome, h)] = ler_textura(dados)
                except FormatoNaoSuportado as erro:
                    problemas.append(f"{f['nomes'].get(h, f'{h:016x}')}: {erro} (mantida original)")
    if not imagens:
        sys.exit("nenhuma textura legível encontrada")

    # 2) decidir quais cores serão trocadas
    if args.origem_de is not None and args.origem_ate is not None:
        de, ate = args.origem_de, args.origem_ate
        print(f"faixa de origem informada: {de:.0f}° a {ate:.0f}°")
    else:
        de, ate, pico = detectar_faixa(imagens.values())
        print(f"cor principal detectada: {pico}°  ->  faixa trocada: {de}° a {ate}°")

    cfg = criar_paleta(args.cor, de, ate, variacao=args.variacao,
                       reforco_saturacao=args.reforco, saturacao_minima=args.saturacao_minima)

    # 3) recolorir
    novos_wads = {}
    for nome, f in fontes.items():
        wad, alterados, r = f["wad"], {}, relatorio[nome]
        for h in f["selecao"]:
            dados = wad.get(h)
            if dados is None:
                continue
            rotulo = f["nomes"].get(h, f"{h:016x}")
            try:
                if (nome, h) in imagens:
                    nova, trocados = aplicar_imagem(imagens[(nome, h)], cfg)
                    if trocados == 0:
                        r["texturas sem a cor (mantidas)"] += 1
                        continue
                    alterados[h] = gravar_textura(nova, dados)
                    r["texturas recoloridas"] += 1
                elif dados[:4] == b"PROP":
                    novo, cores, params = recolorir_bin(dados, cfg)
                    r[".bin lidos"] += 1
                    r["cores de efeito trocadas"] += cores
                    r["parâmetros de material trocados"] += params
                    if cores or params:
                        alterados[h] = novo
                elif dados[:4] == b"PTCH":
                    problemas.append(f"{rotulo}: .bin de patch (PTCH) ainda não suportado (mantido original)")
            except Exception as erro:
                problemas.append(f"{rotulo}: {type(erro).__name__}: {erro} (mantido original)")
        novos_wads[nome] = escrever_wad(wad.cabecalho, wad.entradas, alterados, so_alterados=modo_jogo)
        r["arquivos alterados"] = len(alterados)
        if not alterados:
            problemas.append(f"{nome}: nada foi alterado (a cor escolhida não encontrou o que trocar?)")

    # 4) META
    if modo_jogo:
        info = {
            "Name": args.nome or f"{campeao} skin {args.skin} ({args.cor})",
            "Author": args.autor,
            "Version": "1.0",
            "Description": f"Recolor ({args.cor}) da skin {args.skin} de {campeao}. Uso pessoal.",
        }
    else:
        info = {}
        if "META/info.json" in z.namelist():
            info = json.loads(z.read("META/info.json").decode("utf-8-sig"))
        nome_original = info.get("Name", entrada.stem)
        autor_original = info.get("Author", "desconhecido")
        info["Name"] = args.nome or f"{nome_original} ({args.cor})"
        info["Description"] = (f"Recolor ({args.cor}) de '{nome_original}' por {autor_original}. "
                               f"Créditos aos autores originais. | Original: {info.get('Description', '')}")

    if args.saida:
        saida = Path(args.saida)
    else:
        nome_seguro = re.sub(r'[<>:"/\\|?*]', "-", info["Name"])
        saida = PASTA_SAIDA / f"{nome_seguro}.fantome"
    saida.parent.mkdir(parents=True, exist_ok=True)
    if saida.resolve() == entrada.resolve():
        sys.exit("a saída não pode ser o próprio arquivo de entrada")

    # 5) empacotar
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("META/info.json", json.dumps(info, indent=2, ensure_ascii=False))
        for nome, dados in novos_wads.items():
            out.writestr(nome, dados)
        if not modo_jogo:
            for item in z.namelist():
                if item in novos_wads or item == "META/info.json":
                    continue
                if item.lower() == "meta/image.png":
                    capa = Image.open(io.BytesIO(z.read(item))).convert("RGBA")
                    buf = io.BytesIO()
                    aplicar_imagem(capa, cfg)[0].save(buf, "PNG")
                    out.writestr(item, buf.getvalue())
                else:
                    out.writestr(item, z.read(item))

    # 6) relatório
    print()
    for nome, r in relatorio.items():
        print(f"=== {nome} ===")
        for chave, valor in r.items():
            print(f"  {chave}: {valor}")
    print("\nproblemas:" if problemas else "\nproblemas: nenhum")
    for p in problemas:
        print("  -", p)
    print(f"\npronto: {saida}")

if __name__ == "__main__":
    main()