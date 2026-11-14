"""Leitura e escrita genérica de arquivos .wad.client (versão 3)."""
import struct, io, gzip
import zstandard, xxhash

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
NOMES_TIPO = {0: "sem compressão", 1: "gzip", 2: "link", 3: "zstd", 4: "zstd em pedaços"}

def ler_wad(wad):
    """Recebe os bytes do WAD. Devolve (cabeçalho, lista de entradas)."""
    if wad[:2] != b"RW":
        raise ValueError("não é um WAD (falta 'RW')")
    versao = (wad[2], wad[3])
    if versao[0] != 3:
        raise ValueError(f"WAD versão {versao[0]}.{versao[1]} não suportado (só versão 3)")

    count = struct.unpack_from("<I", wad, 268)[0]
    entradas = []
    for i in range(count):
        h, off, csize, size, tipo_byte, dup, sub_idx, checksum = struct.unpack_from("<QIIIBBHQ", wad, 272 + i * 32)
        entradas.append({
            "hash": h, "offset": off, "csize": csize, "size": size,
            "tipo_byte": tipo_byte, "dup": dup, "sub_idx": sub_idx, "checksum": checksum,
            "bruto": wad[off:off + csize],
        })
    return wad[:268], entradas

def tipo(entrada):
    """Os 4 bits de baixo dizem a compressão (os 4 de cima, a qtd de pedaços)."""
    return entrada["tipo_byte"] & 0x0F

def descomprimir(entrada):
    """Devolve os bytes originais do arquivo, ou None se for um 'link'."""
    t, bruto, size = tipo(entrada), entrada["bruto"], entrada["size"]

    if t == 0:
        dados = bruto
    elif t == 1:
        dados = gzip.decompress(bruto)
    elif t == 2:
        return None
    elif t == 3:
        dados = zstandard.ZstdDecompressor().decompress(bruto, max_output_size=size)
    elif t == 4:
        inicio = bruto.find(ZSTD_MAGIC)
        if inicio < 0:
            dados = bruto
        else:
            partes = [bruto[:inicio]]
            leitor = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(bruto[inicio:]), read_across_frames=True)
            while True:
                pedaco = leitor.read(1 << 20)
                if not pedaco:
                    break
                partes.append(pedaco)
            dados = b"".join(partes)
    else:
        raise ValueError(f"compressão tipo {t} desconhecida (hash {entrada['hash']:016x})")

    if len(dados) != size:
        raise ValueError(f"{entrada['hash']:016x}: esperava {size} bytes, veio {len(dados)} (tipo {t})")
    return dados

def escrever_wad(cabecalho, entradas, alterados, so_alterados=False):
    """
    Monta um WAD novo e devolve os bytes.
    - entradas:     lista vinda de ler_wad
    - alterados:    {hash: bytes novos} só dos arquivos que mudaram
    - so_alterados: True = o WAD novo leva SÓ os arquivos alterados
                    (é o que se quer quando a origem é o WAD do jogo)
    Arquivos que não mudaram são copiados comprimidos, exatamente como estavam.
    """
    cctx = zstandard.ZstdCompressor(level=19)
    if so_alterados:
        entradas = [e for e in entradas if e["hash"] in alterados]
    ordenadas = sorted(entradas, key=lambda e: e["hash"])
    inicio_dados = 272 + 32 * len(ordenadas)

    tabela = bytearray()
    blob = bytearray()
    ja_gravado = {}          # offset original -> offset novo (arquivos duplicados)

    for e in ordenadas:
        h = e["hash"]
        if h in alterados:
            novo = alterados[h]
            comp = cctx.compress(novo)
            offset = inicio_dados + len(blob)
            blob += comp
            tabela += struct.pack("<QIIIBBHQ", h, offset, len(comp), len(novo),
                                  3, 0, 0, xxhash.xxh3_64(comp).intdigest())
        else:
            if e["offset"] in ja_gravado:
                offset = ja_gravado[e["offset"]]
            else:
                offset = inicio_dados + len(blob)
                blob += e["bruto"]
                ja_gravado[e["offset"]] = offset
            tabela += struct.pack("<QIIIBBHQ", h, offset, e["csize"], e["size"],
                                  e["tipo_byte"], e["dup"], e["sub_idx"], e["checksum"])

    return bytes(cabecalho[:268]) + struct.pack("<I", len(ordenadas)) + bytes(tabela) + bytes(blob)


class Wad:
    """Um WAD aberto, que só descomprime cada arquivo quando alguém pede."""

    def __init__(self, bytes_wad):
        self.cabecalho, self.entradas = ler_wad(bytes_wad)
        self.por_hash = {e["hash"]: e for e in self.entradas}
        self._cache = {}

    def __contains__(self, h):
        return h in self.por_hash

    def get(self, h):
        """Bytes descomprimidos do arquivo (None se for link ou não existir)."""
        if h not in self.por_hash:
            return None
        if h not in self._cache:
            self._cache[h] = descomprimir(self.por_hash[h])
        return self._cache[h]

    def hashes(self):
        return list(self.por_hash)