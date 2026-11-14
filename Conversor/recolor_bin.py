"""Troca as cores dentro de arquivos .bin usando uma paleta."""
from binlib import ler_bin, escrever_bin, fnv1a, EMBED, PONTEIRO, LISTA, LISTA2, OPCAO, MAPA
from paletas import aplicar_cor

VALUE_COLOR = fnv1a("ValueColor")
ANIM_COLOR  = fnv1a("VfxAnimatedColorVariableData")
PARAM       = fnv1a("StaticMaterialShaderParamDef")
NAME, VALUE = fnv1a("name"), fnv1a("value")
VEC4 = 13

def recolorir_bin(dados, cfg):
    """Devolve (bytes novos, cores trocadas, parâmetros de material trocados)."""
    cont = {"cores": 0, "params": 0}

    def trocar(c):
        nova = aplicar_cor(*c, cfg)
        if nova != tuple(c):
            cont["cores"] += 1
        return nova

    def objeto(obj):
        classe = obj["classe"]
        for campo in obj["campos"]:
            if campo.get("especial"):
                continue
            tipo, valor = campo["tipo"], campo["valor"]
            if classe == VALUE_COLOR and tipo == VEC4:
                campo["valor"] = trocar(valor)
            elif classe == ANIM_COLOR and tipo in (LISTA, LISTA2) and valor["tipo_item"] == VEC4:
                valor["itens"] = [trocar(c) for c in valor["itens"]]
            else:
                valor_qualquer(tipo, valor)
        if classe == PARAM:
            campos = {c["nome"]: c for c in obj["campos"]}
            nome, val = campos.get(NAME), campos.get(VALUE)
            if nome and val and val["tipo"] == VEC4 and isinstance(nome["valor"], str):
                n = nome["valor"].lower()
                if "color" in n or "tint" in n:
                    novo = aplicar_cor(*val["valor"], cfg)
                    if novo != tuple(val["valor"]):
                        val["valor"] = novo
                        cont["params"] += 1

    def valor_qualquer(tipo, valor):
        if tipo in (EMBED, PONTEIRO) and valor["classe"] != 0:
            objeto(valor)
        elif tipo in (LISTA, LISTA2):
            for item in valor["itens"]:
                valor_qualquer(valor["tipo_item"], item)
        elif tipo == OPCAO and valor["valor"] is not None:
            valor_qualquer(valor["tipo_item"], valor["valor"])
        elif tipo == MAPA:
            for _chave, item in valor["pares"]:
                valor_qualquer(valor["tipo_valor"], item)

    b = ler_bin(dados)
    for entrada in b["entradas"]:
        objeto(entrada)
    novo = escrever_bin(b)
    ler_bin(novo)                      # prova: o arquivo novo ainda é legível
    return novo, cont["cores"], cont["params"]