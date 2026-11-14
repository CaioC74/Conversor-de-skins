"""
Versão web (local) do conversor.
Rode com:  python app.py   -> abre http://127.0.0.1:5000 no navegador.
Só funciona na sua máquina (127.0.0.1); ninguém de fora acessa.
"""
import base64, io, tempfile, threading, webbrowser
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from conversor import converter, ErroConversao, PASTA_SAIDA
from paletas import PADRAO

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024**3      # aceita arquivos de até 2 GB (o WAD do jogo é grande)
PORTA = 5000

def imagem_base64(img, lado=260):
    """Imagem do Pillow -> texto base64 de um PNG, pra mostrar direto na página."""
    copia = img.copy()
    copia.thumbnail((lado, lado))
    buf = io.BytesIO()
    copia.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

@app.get("/")
def inicio():
    return render_template("index.html", padrao=PADRAO)

@app.post("/converter")
def converter_rota():
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return jsonify(ok=False, erro="Escolha um arquivo .fantome ou .wad.client"), 400

    mensagens = []
    with tempfile.TemporaryDirectory() as pasta_temp:
        # o nome original importa: a extensão decide o modo e o nome do WAD diz o campeão
        nome = secure_filename(arquivo.filename)
        if not nome:   # nome só com acentos/símbolos: secure_filename devolve vazio
            nome = "entrada.wad.client" if arquivo.filename.lower().endswith(".wad.client") else "entrada.fantome"
        caminho = Path(pasta_temp) / nome
        arquivo.save(caminho)
        try:
            resultado = converter(
                caminho,
                cor=request.form.get("cor", "verde"),
                skin=int(request.form.get("skin") or 0),
                nome=request.form.get("nome", "").strip() or None,
                variacao=float(request.form.get("variacao", PADRAO["variacao"])),
                reforco=float(request.form.get("reforco", PADRAO["reforco_saturacao"])),
                log=mensagens.append,
            )
        except ErroConversao as erro:
            return jsonify(ok=False, erro=str(erro), log="\n".join(mensagens)), 400
        except Exception as erro:
            return jsonify(ok=False, erro=f"{type(erro).__name__}: {erro}", log="\n".join(mensagens)), 500

    resposta = {"ok": True, "log": "\n".join(mensagens), "arquivo": resultado["saida"].name,
                "problemas": resultado["problemas"]}
    if resultado["amostra"]:
        antes, depois = resultado["amostra"]
        resposta["antes"] = imagem_base64(antes)
        resposta["depois"] = imagem_base64(depois)
    return jsonify(resposta)

@app.get("/baixar/<path:nome>")
def baixar(nome):
    return send_from_directory(PASTA_SAIDA, nome, as_attachment=True)

if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}")).start()
    app.run(host="127.0.0.1", port=PORTA, debug=False)