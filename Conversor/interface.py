"""
Interface gráfica do conversor (Tkinter, que já vem com o Python).
Rode com:  python interface.py
"""
import os, queue, sys, threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import ImageTk

from conversor import converter, ErroConversao, PASTA_SAIDA
from paletas import PADRAO, ler_cor
import colorsys

TAMANHO_PREVIA = 220   # lado (em pixels) de cada imagem da prévia


class App:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title("Conversor de Skins - LoL")
        raiz.minsize(720, 640)

        self.mensagens = queue.Queue()    # a conversão (outra thread) manda texto pra cá
        self.previas = []                 # guarda as imagens pro Tkinter não apagá-las

        quadro = ttk.Frame(raiz, padding=12)
        quadro.pack(fill="both", expand=True)
        quadro.columnconfigure(1, weight=1)

        # --- arquivo de entrada ---
        ttk.Label(quadro, text="Arquivo:").grid(row=0, column=0, sticky="w")
        self.var_arquivo = tk.StringVar()
        self.var_arquivo.trace_add("write", lambda *_: self.atualizar_skin())
        ttk.Entry(quadro, textvariable=self.var_arquivo).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(quadro, text="Escolher...", command=self.escolher_arquivo).grid(row=0, column=2)

        # --- número da skin (só para WAD do jogo) ---
        ttk.Label(quadro, text="Skin nº:").grid(row=1, column=0, sticky="w", pady=6)
        self.var_skin = tk.IntVar(value=0)
        self.campo_skin = ttk.Spinbox(quadro, from_=0, to=99, width=6, textvariable=self.var_skin)
        self.campo_skin.grid(row=1, column=1, sticky="w", padx=6)
        self.dica_skin = ttk.Label(quadro, text="(0 = skin base; só vale para .wad.client do jogo)",
                                   foreground="gray")
        self.dica_skin.grid(row=1, column=1, sticky="w", padx=80)

        # --- cor ---
        ttk.Label(quadro, text="Cor:").grid(row=2, column=0, sticky="w")
        linha_cor = ttk.Frame(quadro)
        linha_cor.grid(row=2, column=1, sticky="w", padx=6)
        self.var_cor = tk.StringVar(value="#33cc55")
        self.var_cor.trace_add("write", lambda *_: self.atualizar_amostra_cor())
        ttk.Entry(linha_cor, textvariable=self.var_cor, width=12).pack(side="left")
        self.amostra_cor = tk.Label(linha_cor, width=4, relief="sunken")
        self.amostra_cor.pack(side="left", padx=6)
        ttk.Button(linha_cor, text="Escolher cor...", command=self.escolher_cor).pack(side="left")
        ttk.Label(linha_cor, text="  (#hex, graus 0-360 ou nome: verde, roxo...)",
                  foreground="gray").pack(side="left")

        # --- ajustes finos ---
        self.var_variacao = tk.DoubleVar(value=PADRAO["variacao"])
        self.var_reforco = tk.DoubleVar(value=PADRAO["reforco_saturacao"])
        self.criar_slider(quadro, 3, "Variação (degradê):", self.var_variacao, -90, 90, "{:.0f}°")
        self.criar_slider(quadro, 4, "Intensidade da cor:", self.var_reforco, 0.5, 2.0, "{:.2f}x")

        # --- nome do mod ---
        ttk.Label(quadro, text="Nome do mod:").grid(row=5, column=0, sticky="w", pady=6)
        self.var_nome = tk.StringVar()
        ttk.Entry(quadro, textvariable=self.var_nome).grid(row=5, column=1, sticky="ew", padx=6)
        ttk.Label(quadro, text="(opcional)", foreground="gray").grid(row=5, column=2)

        # --- botões ---
        botoes = ttk.Frame(quadro)
        botoes.grid(row=6, column=0, columnspan=3, pady=8)
        self.botao_gerar = ttk.Button(botoes, text="Gerar skin", command=self.gerar)
        self.botao_gerar.pack(side="left", padx=4)
        ttk.Button(botoes, text="Abrir pasta Skin Custom", command=self.abrir_pasta).pack(side="left", padx=4)

        # --- prévia antes/depois ---
        previa = ttk.Frame(quadro)
        previa.grid(row=7, column=0, columnspan=3)
        self.rotulo_antes = ttk.Label(previa, text="Antes", compound="top")
        self.rotulo_antes.pack(side="left", padx=8)
        self.rotulo_depois = ttk.Label(previa, text="Depois", compound="top")
        self.rotulo_depois.pack(side="left", padx=8)

        # --- registro (log) ---
        self.log = tk.Text(quadro, height=12, state="disabled", wrap="word")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        quadro.rowconfigure(8, weight=1)

        self.atualizar_skin()
        self.atualizar_amostra_cor()
        self.raiz.after(100, self.ler_mensagens)

    # ---------------------------------------------------------- montagem

    def criar_slider(self, quadro, linha, texto, variavel, minimo, maximo, formato):
        ttk.Label(quadro, text=texto).grid(row=linha, column=0, sticky="w")
        valor = ttk.Label(quadro, width=7)
        valor.grid(row=linha, column=2)
        def mostrar(*_):
            valor.config(text=formato.format(variavel.get()))
        ttk.Scale(quadro, from_=minimo, to=maximo, variable=variavel,
                  command=lambda *_: mostrar()).grid(row=linha, column=1, sticky="ew", padx=6)
        mostrar()

    # ---------------------------------------------------------- ações

    def escolher_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Escolha a skin",
            filetypes=[("Skins", "*.fantome *.wad.client"), ("Mod .fantome", "*.fantome"),
                       ("WAD do jogo", "*.wad.client"), ("Todos", "*.*")])
        if caminho:
            self.var_arquivo.set(caminho)

    def atualizar_skin(self):
        eh_wad = self.var_arquivo.get().lower().endswith(".wad.client")
        self.campo_skin.config(state="normal" if eh_wad else "disabled")

    def escolher_cor(self):
        _rgb, hexa = colorchooser.askcolor(title="Escolha a cor", initialcolor=self.cor_em_hex())
        if hexa:
            self.var_cor.set(hexa)

    def cor_em_hex(self):
        """Converte o que estiver no campo (hex, graus ou nome) em #rrggbb pra mostrar."""
        try:
            h, s = ler_cor(self.var_cor.get())
        except ValueError:
            return None
        r, g, b = colorsys.hsv_to_rgb(h / 360, s, 1.0)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def atualizar_amostra_cor(self):
        hexa = self.cor_em_hex()
        self.amostra_cor.config(bg=hexa or "gray", text="" if hexa else "?")

    def abrir_pasta(self):
        PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(PASTA_SAIDA)
        else:
            messagebox.showinfo("Pasta", str(PASTA_SAIDA))

    def gerar(self):
        if not self.var_arquivo.get():
            messagebox.showwarning("Falta o arquivo", "Escolha um .fantome ou .wad.client primeiro.")
            return
        if self.cor_em_hex() is None:
            messagebox.showwarning("Cor inválida", "Use #RRGGBB, graus de 0 a 360 ou um nome (verde, roxo...).")
            return
        self.botao_gerar.config(state="disabled", text="Gerando...")
        self.limpar_log()
        parametros = dict(
            entrada=self.var_arquivo.get(),
            cor=self.var_cor.get(),
            skin=self.var_skin.get(),
            nome=self.var_nome.get().strip() or None,
            variacao=self.var_variacao.get(),
            reforco=self.var_reforco.get(),
        )
        threading.Thread(target=self.trabalho, args=(parametros,), daemon=True).start()

    def trabalho(self, parametros):
        """Roda em OUTRA thread: a janela continua respondendo enquanto converte."""
        try:
            resultado = converter(**parametros, log=lambda texto: self.mensagens.put(("log", texto)))
            self.mensagens.put(("fim", resultado))
        except ErroConversao as erro:
            self.mensagens.put(("erro", str(erro)))
        except Exception as erro:
            self.mensagens.put(("erro", f"{type(erro).__name__}: {erro}"))

    # ---------------------------------------------------------- comunicação entre threads

    def ler_mensagens(self):
        """Chamada a cada 100 ms pela própria janela: pega o que a conversão mandou."""
        try:
            while True:
                tipo, conteudo = self.mensagens.get_nowait()
                if tipo == "log":
                    self.escrever_log(conteudo)
                elif tipo == "erro":
                    self.escrever_log("ERRO: " + conteudo)
                    messagebox.showerror("Erro", conteudo)
                    self.botao_gerar.config(state="normal", text="Gerar skin")
                elif tipo == "fim":
                    self.mostrar_previa(conteudo["amostra"])
                    self.botao_gerar.config(state="normal", text="Gerar skin")
        except queue.Empty:
            pass
        self.raiz.after(100, self.ler_mensagens)

    def mostrar_previa(self, amostra):
        if not amostra:
            return
        self.previas = []
        for imagem, rotulo, texto in zip(amostra, (self.rotulo_antes, self.rotulo_depois), ("Antes", "Depois")):
            copia = imagem.copy()
            copia.thumbnail((TAMANHO_PREVIA, TAMANHO_PREVIA))
            foto = ImageTk.PhotoImage(copia)
            self.previas.append(foto)
            rotulo.config(image=foto, text=texto)

    def escrever_log(self, texto):
        self.log.config(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def limpar_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()