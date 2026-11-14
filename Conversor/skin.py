"""Descobre quais arquivos de um WAD pertencem a uma skin (ex.: Zed skin 0 ou 13)."""
import re
import xxhash
from binlib import ler_bin, EMBED, PONTEIRO, LISTA, LISTA2, OPCAO, MAPA

STRING, ARQUIVO = 16, 18
PADRAO_CAMINHO = re.compile(rb"[A-Za-z0-9_/\-. ]+\.(?:tex|dds|bin)", re.IGNORECASE)
PADRAO_PERSONAGEM = re.compile(rb"[Cc]haracters/([A-Za-z0-9_]+)/")

def hash_caminho(caminho):
    return xxhash.xxh64(caminho.lower().encode()).intdigest()

def referencias(dados):
    """Caminhos (texto) e hashes de arquivo citados dentro de um .bin."""
    caminhos = {m.decode() for m in PADRAO_CAMINHO.findall(dados)}
    hashes = set()

    def valor(tipo, v):
        if tipo == ARQUIVO:
            hashes.add(v)
        elif tipo == STRING:
            caminhos.add(v)
        elif tipo in (EMBED, PONTEIRO) and v["classe"] != 0:
            for c in v["campos"]:
                if not c.get("especial"):
                    valor(c["tipo"], c["valor"])
        elif tipo in (LISTA, LISTA2):
            for item in v["itens"]:
                valor(v["tipo_item"], item)
        elif tipo == OPCAO and v["valor"] is not None:
            valor(v["tipo_item"], v["valor"])
        elif tipo == MAPA:
            for k, x in v["pares"]:
                valor(v["tipo_chave"], k)
                valor(v["tipo_valor"], x)

    try:
        for e in ler_bin(dados)["entradas"]:
            for c in e["campos"]:
                if not c.get("especial"):
                    valor(c["tipo"], c["valor"])
    except Exception:
        pass        # se o .bin não abrir por completo, ficamos só com o que o regex achou
    return caminhos, hashes

def personagens(wad):
    """Nomes de personagens citados nos .bin do WAD (ex.: Zed, ZedShadow)."""
    nomes = set()
    for h in wad.hashes():
        e = wad.por_hash[h]
        if e["size"] > 20_000_000:          # .bin nunca é tão grande; pula modelos/animações
            continue
        dados = wad.get(h)
        if dados and dados[:4] in (b"PROP", b"PTCH"):
            nomes.update(m.decode().lower() for m in PADRAO_PERSONAGEM.findall(dados))
        wad._cache.pop(h, None)             # não guarda na memória o que não vamos usar
    return nomes

def arquivos_da_skin(wad, campeao, numero):
    """
    Devolve {"raizes": [...], "hashes": set(...), "nomes": {hash: caminho}, "compartilhados": n}.
    raizes = os skinN.bin encontrados (do campeão e dos 'ajudantes', como a sombra do Zed).
    """
    candidatos = personagens(wad) | {campeao.lower()}
    raizes = []
    for nome in sorted(candidatos):
        caminho = f"data/characters/{nome}/skins/skin{numero}.bin"
        if hash_caminho(caminho) in wad:
            raizes.append(caminho)

    nomes = {hash_caminho(r): r for r in raizes}
    pendentes = [hash_caminho(r) for r in raizes]
    selecionados = set()
    while pendentes:
        h = pendentes.pop()
        if h in selecionados or h not in wad:
            continue
        selecionados.add(h)
        dados = wad.get(h)
        if not dados or dados[:4] not in (b"PROP", b"PTCH"):
            continue
        caminhos, hashes = referencias(dados)
        for c in caminhos:
            hc = hash_caminho(c)
            nomes.setdefault(hc, c)
            if c.lower().endswith(".bin") and _eh_bin_do_campeao(c):
                continue            # dados de jogo do campeão: não é aparência, não mexe
            pendentes.append(hc)
        pendentes.extend(hashes)

    pasta_skin = f"/skins/skin{numero}/"
    compartilhados = sum(1 for h in selecionados
                         if h in nomes and nomes[h].lower().endswith((".tex", ".dds"))
                         and pasta_skin not in nomes[h].lower())
    return {"raizes": raizes, "hashes": selecionados, "nomes": nomes, "compartilhados": compartilhados}

def _eh_bin_do_campeao(caminho):
    """'data/characters/zed/zed.bin' e animações: dados de jogo, não de aparência."""
    partes = caminho.lower().split("/")
    if "animations" in partes:
        return True
    return len(partes) == 4 and partes[0] == "data" and partes[1] == "characters" and partes[3] == partes[2] + ".bin"