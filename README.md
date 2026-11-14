# Conversor de Skins - League of Legends

Recolore skins do LoL trocando a cor principal por uma cor escolhida,
mantendo luz, sombra e o desenho original. Projeto de estudo em Python.

Funciona com:
- skins custom em `.fantome` (feitas pela comunidade)
- o WAD do próprio jogo (ex.: `Zed.wad.client`), escolhendo a skin pelo número (0 = skin base)

O resultado é um `.fantome` para carregar no CSLoL Manager.

## Instalação

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

### Interface
```
python interface.py
```

### Terminal
```
python conversor.py "Minha Skin.fantome" --cor verde
python conversor.py "Zed.wad.client" --skin 0 --cor "#33cc55"
python conversor.py "Zed.wad.client" --skin 13 --cor roxo --variacao 60
python conversor.py --help
```
No PowerShell, cores em hex precisam de aspas (`"#33cc55"`), porque `#` inicia um comentário.

As skins geradas ficam na pasta `Skin Custom`.

## Como funciona

| Arquivo | O que faz |
|---|---|
| `wad.py` | lê e grava arquivos `.wad.client` (zstd, gzip, links) |
| `tex.py` | lê e grava texturas `.tex` e `.dds` (DXT1, DXT5, BGRA8, com mipmaps) |
| `binlib.py` | lê e grava os `.bin` (definições de efeitos e materiais) |
| `paletas.py` | regra de cor: detecção automática da cor original e troca pela nova |
| `recolor_bin.py` | troca as cores dentro dos `.bin` |
| `skin.py` | descobre quais arquivos do WAD do jogo pertencem a uma skin |
| `conversor.py` | junta tudo (terminal) |
| `interface.py` | janela gráfica (Tkinter) |

## Riscos e banimento

**Use por sua conta e risco.** Os Termos de Serviço da Riot não permitem modificar
arquivos do jogo, e isso inclui skins custom. Na prática, a Riot já disse que skins
custom ficam numa zona de "use por sua conta e risco": não costumam render ban, mas
**não existe garantia**, e já houve relatos de contas punidas.

O que se sabe pelos relatos da comunidade:

| Prática | Risco |
|---|---|
| Skin custom (arte nova ou recolor) carregada pelo CSLoL Manager, que só troca arquivos antes do jogo abrir | Baixo, mas não zero |
| Usar mod para liberar **skins pagas que você não tem** | Alto: é tratado como pirataria e é o que mais dá ban |
| "Skin changers" que **injetam código na memória** do jogo durante a partida | Alto: o Vanguard (anti-cheat) detecta |
| Usar qualquer ferramenta de terceiros no **servidor coreano** | Alto: há relatos de ban por qualquer ferramenta |
| Distribuir ou vender skins modificadas | Aumenta a chance de a conta ser analisada |

Este projeto fica na primeira linha: ele só **recolore skins que você já tem**
(ou a skin base) e o resultado é carregado pelo CSLoL Manager. As skins só
aparecem para você; os outros jogadores continuam vendo a skin original.

Para reduzir o risco: mantenha o CSLoL Manager atualizado, use só para skins que
você possui e, se quiser risco zero, teste numa conta secundária.

## Avisos

- Não suba para o repositório arquivos do jogo (`.wad.client`) nem skins de outros
  autores (`.fantome`). O `.gitignore` já bloqueia esses arquivos.
- Ao recolorir uma skin custom de outra pessoa, mantenha os créditos (o conversor
  já preserva o autor original na descrição) e não redistribua sem permissão.