import struct

# Tipos de tamanho fixo: código do tipo -> formato do struct
FIXOS = {
    1: "?",  2: "b",  3: "B",  4: "h",  5: "H",  6: "i",  7: "I",
    8: "q",  9: "Q", 10: "f", 11: "2f", 12: "3f", 13: "4f", 14: "16f",
    15: "4B", 17: "I", 18: "Q", 0x84: "I", 0x87: "?",
}
STRING, LISTA, LISTA2, PONTEIRO, EMBED, OPCAO, MAPA = 16, 0x80, 0x81, 0x82, 0x83, 0x85, 0x86
HASH_NAME = 0x8D39BDE6   # fnv1a("name"): caso especial, ver ler_campo

def fnv1a(texto):
    h = 0x811C9DC5
    for byte in texto.lower().encode():
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

class Leitor:
    def __init__(self, dados):
        self.dados = dados
        self.pos = 0
    def ler(self, fmt):
        valores = struct.unpack_from("<" + fmt, self.dados, self.pos)
        self.pos += struct.calcsize("<" + fmt)
        return valores

def ler_valor(r, tipo):
    if tipo in FIXOS:
        v = r.ler(FIXOS[tipo])
        return v[0] if len(v) == 1 else v
    if tipo == STRING:
        (n,) = r.ler("H")
        texto = r.dados[r.pos:r.pos + n].decode("utf-8")
        r.pos += n
        return texto
    if tipo in (LISTA, LISTA2):
        tipo_item, _tamanho, qtd = r.ler("BII")
        return {"tipo_item": tipo_item, "itens": [ler_valor(r, tipo_item) for _ in range(qtd)]}
    if tipo in (PONTEIRO, EMBED):
        (classe,) = r.ler("I")
        if classe == 0:
            return {"classe": 0, "campos": []}
        _tamanho, qtd = r.ler("IH")
        return {"classe": classe, "campos": [ler_campo(r) for _ in range(qtd)]}
    if tipo == OPCAO:
        tipo_item, tem = r.ler("BB")
        return {"tipo_item": tipo_item, "valor": ler_valor(r, tipo_item) if tem else None}
    if tipo == MAPA:
        tipo_chave, tipo_valor, _tamanho, qtd = r.ler("BBII")
        pares = [(ler_valor(r, tipo_chave), ler_valor(r, tipo_valor)) for _ in range(qtd)]
        return {"tipo_chave": tipo_chave, "tipo_valor": tipo_valor, "pares": pares}
    raise ValueError(f"tipo desconhecido 0x{tipo:x} na posição {r.pos}")

def ler_campo(r):
    nome, tipo = r.ler("IB")
    if nome == HASH_NAME and tipo == 17:      # neste arquivo, 'name' de material ocupa 8 bytes
        (v,) = r.ler("Q")
        return {"nome": nome, "tipo": tipo, "valor": v, "especial": True}
    return {"nome": nome, "tipo": tipo, "valor": ler_valor(r, tipo)}

def ler_bin(dados):
    r = Leitor(dados)
    magic, versao, n_links = r.ler("4sII")
    assert magic == b"PROP", "não é um .bin"
    links = []
    for _ in range(n_links):
        (n,) = r.ler("H")
        links.append(r.dados[r.pos:r.pos + n].decode("utf-8"))
        r.pos += n
    (n_entradas,) = r.ler("I")
    classes = r.ler(f"{n_entradas}I") if n_entradas else ()
    entradas = []
    for classe in classes:
        _tamanho, caminho, qtd = r.ler("IIH")
        entradas.append({"classe": classe, "caminho": caminho,
                         "campos": [ler_campo(r) for _ in range(qtd)]})
    assert r.pos == len(dados), "sobrou coisa no fim do arquivo"
    return {"versao": versao, "links": links, "entradas": entradas}

# ----------------------------- escrita -----------------------------

def escrever_valor(tipo, v):
    if tipo in FIXOS:
        return struct.pack("<" + FIXOS[tipo], *(v if isinstance(v, tuple) else (v,)))
    if tipo == STRING:
        b = v.encode("utf-8")
        return struct.pack("<H", len(b)) + b
    if tipo in (LISTA, LISTA2):
        corpo = struct.pack("<I", len(v["itens"])) + b"".join(escrever_valor(v["tipo_item"], x) for x in v["itens"])
        return struct.pack("<BI", v["tipo_item"], len(corpo)) + corpo
    if tipo in (PONTEIRO, EMBED):
        if v["classe"] == 0:
            return struct.pack("<I", 0)
        corpo = struct.pack("<H", len(v["campos"])) + b"".join(escrever_campo(c) for c in v["campos"])
        return struct.pack("<II", v["classe"], len(corpo)) + corpo
    if tipo == OPCAO:
        tem = v["valor"] is not None
        return struct.pack("<BB", v["tipo_item"], tem) + (escrever_valor(v["tipo_item"], v["valor"]) if tem else b"")
    if tipo == MAPA:
        corpo = struct.pack("<I", len(v["pares"])) + b"".join(
            escrever_valor(v["tipo_chave"], k) + escrever_valor(v["tipo_valor"], x) for k, x in v["pares"])
        return struct.pack("<BBI", v["tipo_chave"], v["tipo_valor"], len(corpo)) + corpo
    raise ValueError(f"tipo desconhecido 0x{tipo:x}")

def escrever_campo(c):
    if c.get("especial"):
        return struct.pack("<IBQ", c["nome"], c["tipo"], c["valor"])
    return struct.pack("<IB", c["nome"], c["tipo"]) + escrever_valor(c["tipo"], c["valor"])

def escrever_bin(b):
    out = struct.pack("<4sII", b"PROP", b["versao"], len(b["links"]))
    for link in b["links"]:
        lb = link.encode("utf-8")
        out += struct.pack("<H", len(lb)) + lb
    out += struct.pack("<I", len(b["entradas"]))
    out += b"".join(struct.pack("<I", e["classe"]) for e in b["entradas"])
    for e in b["entradas"]:
        corpo = struct.pack("<IH", e["caminho"], len(e["campos"])) + b"".join(escrever_campo(c) for c in e["campos"])
        out += struct.pack("<I", len(corpo)) + corpo
    return out