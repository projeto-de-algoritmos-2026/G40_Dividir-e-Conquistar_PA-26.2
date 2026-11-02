import queue
import signal
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageOps, ImageTk, UnidentifiedImageError
from filtro import ProcessamentoCancelado, aplicar_filtro
from processamento import (
    abrir_imagem,
    adicionar_ruido_sal_pimenta,
    calcular_psnr,
    salvar_imagem,
)

TAMANHO_PAINEL = 310
DIRETORIO_IMAGENS = Path(__file__).resolve().parent.parent / "images"


def processar(original, com_ruido=True, callback_progresso=None, cancelado=None):
    if com_ruido:
        entrada = adicionar_ruido_sal_pimenta(original)
    else:
        entrada = original

    inicio = time.perf_counter()
    filtrada = aplicar_filtro(
        entrada,
        callback_progresso=callback_progresso,
        cancelado=cancelado,
    )
    tempo = time.perf_counter() - inicio

    resultado = {"filtrada": filtrada, "tempo": tempo, "ruidosa": None}
    if com_ruido:
        resultado["ruidosa"] = entrada
        resultado["psnr_ruidosa"] = calcular_psnr(original, entrada)
        resultado["psnr_filtrada"] = calcular_psnr(original, filtrada)
    return resultado


class Aplicacao:
    def __init__(self, janela):
        self.janela = janela
        self.janela.title("Filtro de Mediana das Medianas")
        self.janela.geometry("1080x720")
        self.janela.minsize(920, 620)
        self.janela.protocol("WM_DELETE_WINDOW", self.fechar)
        self.janela.bind("<Control-c>", self.fechar)
        self.janela.bind("<Control-C>", self.fechar)
        self.janela.bind("<Control-o>", lambda _evento: self.selecionar_imagem())
        self.janela.bind("<Control-s>", lambda _evento: self.salvar_filtrada())
        self.janela.bind("<Control-q>", self.fechar)

        self.original = None
        self.resultado = None
        self.thread = None
        self.fila_processamento = queue.Queue()
        self.progresso_atual = (0, 1)
        self.cancelamento = threading.Event()
        self.encerrando = False
        self.fotos = {}
        self.foto_detalhe = None

        self.com_ruido = tk.BooleanVar(value=True)
        self.progresso = tk.DoubleVar(value=0)
        self.texto_progresso = tk.StringVar(value="0%")
        self.texto_status = tk.StringVar(value="Selecione uma imagem para começar.")
        self.texto_imagem = tk.StringVar(value="Nenhuma imagem carregada")
        self.texto_metricas = tk.StringVar(value="PSNR e tempo aparecerão após o processamento")
        self.zoom = tk.DoubleVar(value=100)
        self.divisor = tk.DoubleVar(value=50)

        self.configurar_estilos()
        self.criar_menu()
        self.criar_barra_ferramentas()
        self.criar_area_principal()
        self.criar_rodape()

    def configurar_estilos(self):
        estilo = ttk.Style(self.janela)
        estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 11, "bold"))
        estilo.configure("Info.TLabel", foreground="#555555")
        estilo.configure("Acao.TButton", padding=(10, 6))

    def criar_menu(self):
        menu = tk.Menu(self.janela)

        arquivo = tk.Menu(menu, tearoff=False)
        arquivo.add_command(label="Abrir imagem...", accelerator="Ctrl+O", command=self.selecionar_imagem)
        arquivo.add_command(label="Salvar imagem filtrada...", accelerator="Ctrl+S", command=self.salvar_filtrada)
        arquivo.add_separator()
        arquivo.add_command(label="Sair", accelerator="Ctrl+Q", command=self.fechar)
        menu.add_cascade(label="Arquivo", menu=arquivo)

        visualizar = tk.Menu(menu, tearoff=False)
        visualizar.add_command(label="Comparação lado a lado", command=lambda: self.abas.select(self.aba_comparacao))
        visualizar.add_command(label="Antes e depois", command=lambda: self.abas.select(self.aba_detalhe))
        visualizar.add_separator()
        visualizar.add_command(label="Aumentar zoom", accelerator="Ctrl++", command=self.aumentar_zoom)
        visualizar.add_command(label="Diminuir zoom", accelerator="Ctrl+-", command=self.diminuir_zoom)
        visualizar.add_command(label="Ajustar à janela", accelerator="Ctrl+0", command=self.ajustar_zoom)
        menu.add_cascade(label="Visualizar", menu=visualizar)

        ajuda = tk.Menu(menu, tearoff=False)
        ajuda.add_command(label="Sobre", command=self.mostrar_sobre)
        menu.add_cascade(label="Ajuda", menu=ajuda)

        self.janela.config(menu=menu)
        self.janela.bind("<Control-plus>", lambda _evento: self.aumentar_zoom())
        self.janela.bind("<Control-equal>", lambda _evento: self.aumentar_zoom())
        self.janela.bind("<Control-minus>", lambda _evento: self.diminuir_zoom())
        self.janela.bind("<Control-0>", lambda _evento: self.ajustar_zoom())

    def criar_barra_ferramentas(self):
        barra = ttk.Frame(self.janela, padding=(10, 8))
        barra.pack(fill="x")

        self.botao_selecionar = ttk.Button(
            barra, text="Abrir imagem", command=self.selecionar_imagem, style="Acao.TButton"
        )
        self.botao_selecionar.pack(side="left", padx=(0, 6))

        self.botao_filtrar = ttk.Button(
            barra, text="Aplicar filtro", command=self.iniciar_processamento, state="disabled", style="Acao.TButton"
        )
        self.botao_filtrar.pack(side="left", padx=6)

        self.botao_cancelar = ttk.Button(
            barra, text="Cancelar", command=self.cancelar_processamento, state="disabled", style="Acao.TButton"
        )
        self.botao_cancelar.pack(side="left", padx=6)

        self.botao_salvar = ttk.Button(
            barra, text="Salvar resultado", command=self.salvar_filtrada, state="disabled", style="Acao.TButton"
        )
        self.botao_salvar.pack(side="left", padx=6)

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", padx=10)
        self.caixa_ruido = ttk.Checkbutton(
            barra, text="Adicionar ruído sal e pimenta", variable=self.com_ruido
        )
        self.caixa_ruido.pack(side="left", padx=4)

    def criar_area_principal(self):
        informacoes = ttk.Frame(self.janela, padding=(12, 2, 12, 8))
        informacoes.pack(fill="x")
        ttk.Label(informacoes, textvariable=self.texto_imagem, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(informacoes, textvariable=self.texto_metricas, style="Info.TLabel").pack(anchor="w", pady=(3, 0))

        self.abas = ttk.Notebook(self.janela)
        self.abas.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.aba_comparacao = ttk.Frame(self.abas, padding=8)
        self.aba_detalhe = ttk.Frame(self.abas, padding=8)
        self.abas.add(self.aba_comparacao, text="Comparação lado a lado")
        self.abas.add(self.aba_detalhe, text="Antes e depois / Zoom")

        self.criar_comparacao()
        self.criar_visualizacao_detalhada()

    def criar_comparacao(self):
        self.paineis = {}
        itens = [("original", "Original"), ("ruidosa", "Com ruído"), ("filtrada", "Filtrada")]
        for coluna, (chave, titulo) in enumerate(itens):
            self.aba_comparacao.columnconfigure(coluna, weight=1, uniform="paineis")
            grupo = ttk.LabelFrame(self.aba_comparacao, text=titulo, padding=6)
            grupo.grid(row=0, column=coluna, padx=5, sticky="nsew")
            painel = tk.Label(
                grupo,
                text="Sem imagem",
                bg="#e8eaed",
                fg="#666666",
                anchor="center",
            )
            painel.pack(fill="both", expand=True)
            painel.bind("<Double-Button-1>", lambda _evento: self.abas.select(self.aba_detalhe))
            self.paineis[chave] = painel
        self.aba_comparacao.rowconfigure(0, weight=1)

    def criar_visualizacao_detalhada(self):
        controles = ttk.Frame(self.aba_detalhe)
        controles.pack(fill="x", pady=(0, 8))

        ttk.Label(controles, text="Divisão antes/depois:").pack(side="left")
        ttk.Scale(
            controles,
            from_=0,
            to=100,
            variable=self.divisor,
            command=lambda _valor: self.atualizar_detalhe(),
            length=230,
        ).pack(side="left", padx=(6, 18))

        ttk.Button(controles, text="−", width=3, command=self.diminuir_zoom).pack(side="left")
        ttk.Scale(
            controles,
            from_=25,
            to=300,
            variable=self.zoom,
            command=lambda _valor: self.atualizar_detalhe(),
            length=180,
        ).pack(side="left", padx=6)
        ttk.Button(controles, text="+", width=3, command=self.aumentar_zoom).pack(side="left")
        ttk.Button(controles, text="Ajustar", command=self.ajustar_zoom).pack(side="left", padx=(8, 0))
        self.rotulo_zoom = ttk.Label(controles, text="100%", width=6, anchor="e")
        self.rotulo_zoom.pack(side="left", padx=8)

        moldura = ttk.Frame(self.aba_detalhe)
        moldura.pack(fill="both", expand=True)
        moldura.rowconfigure(0, weight=1)
        moldura.columnconfigure(0, weight=1)

        self.canvas_detalhe = tk.Canvas(moldura, bg="#25282c", highlightthickness=0)
        rolagem_vertical = ttk.Scrollbar(moldura, orient="vertical", command=self.canvas_detalhe.yview)
        rolagem_horizontal = ttk.Scrollbar(moldura, orient="horizontal", command=self.canvas_detalhe.xview)
        self.canvas_detalhe.configure(
            yscrollcommand=rolagem_vertical.set,
            xscrollcommand=rolagem_horizontal.set,
        )
        self.canvas_detalhe.bind("<Configure>", lambda _evento: self.atualizar_detalhe())
        self.canvas_detalhe.grid(row=0, column=0, sticky="nsew")
        rolagem_vertical.grid(row=0, column=1, sticky="ns")
        rolagem_horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas_detalhe.create_text(
            20,
            20,
            anchor="nw",
            fill="white",
            text="Aplique o filtro para habilitar a comparação antes/depois.",
            tags="mensagem",
        )

    def criar_rodape(self):
        rodape = ttk.Frame(self.janela, padding=(10, 7))
        rodape.pack(fill="x")
        self.barra = ttk.Progressbar(
            rodape,
            mode="determinate",
            maximum=100,
            variable=self.progresso,
            length=260,
        )
        self.barra.pack(side="left")
        ttk.Label(rodape, textvariable=self.texto_progresso, width=5, anchor="e").pack(side="left", padx=(5, 12))
        ttk.Separator(rodape, orient="vertical").pack(side="left", fill="y", padx=(0, 12))
        ttk.Label(rodape, textvariable=self.texto_status, anchor="w").pack(side="left", fill="x", expand=True)

    def mostrar(self, chave, array):
        painel = self.paineis[chave]
        largura = max(painel.winfo_width(), TAMANHO_PAINEL)
        altura = max(painel.winfo_height(), TAMANHO_PAINEL)
        imagem = ImageOps.contain(Image.fromarray(array), (largura, altura), Image.Resampling.LANCZOS)
        foto = ImageTk.PhotoImage(imagem)
        self.fotos[chave] = foto
        painel.config(image=foto, text="")

    def limpar(self, chave, texto=""):
        self.paineis[chave].config(image="", text=texto or "Sem imagem")
        self.fotos.pop(chave, None)

    def selecionar_imagem(self):
        caminho = filedialog.askopenfilename(
            parent=self.janela,
            title="Selecione uma imagem",
            initialdir=DIRETORIO_IMAGENS,
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return

        try:
            self.original = abrir_imagem(caminho)
        except (OSError, UnidentifiedImageError):
            messagebox.showerror("Erro", f"Não foi possível abrir a imagem:\n{caminho}")
            return

        self.resultado = None
        self.mostrar("original", self.original)
        self.limpar("ruidosa")
        self.limpar("filtrada")
        self.botao_filtrar.config(state="normal")
        self.botao_salvar.config(state="disabled")
        self.progresso.set(0)
        self.texto_progresso.set("0%")
        altura, largura = self.original.shape
        self.texto_imagem.set(f"{Path(caminho).name}  •  {largura} × {altura} pixels  •  tons de cinza")
        self.texto_metricas.set("PSNR e tempo aparecerão após o processamento")
        self.texto_status.set("Imagem carregada. Configure o ruído e clique em Aplicar filtro.")
        self.canvas_detalhe.delete("all")
        self.canvas_detalhe.create_text(
            20,
            20,
            anchor="nw",
            fill="white",
            text="Aplique o filtro para habilitar a comparação antes/depois.",
        )

    def iniciar_processamento(self):
        if self.original is None:
            return

        for widget in (self.botao_selecionar, self.botao_filtrar, self.botao_salvar, self.caixa_ruido):
            widget.config(state="disabled")
        self.botao_cancelar.config(state="normal")
        self.texto_status.set("Preparando o processamento...")
        self.progresso.set(0)
        self.texto_progresso.set("0%")

        self.resultado = None
        self.cancelamento.clear()
        self.fila_processamento = queue.Queue()
        self.progresso_atual = (0, self.original.shape[0])
        self.thread = threading.Thread(
            target=self.processar_em_segundo_plano, args=(self.com_ruido.get(),), daemon=True
        )
        self.thread.start()
        self.janela.after(50, self.verificar_processamento)

    def processar_em_segundo_plano(self, com_ruido):
        try:
            resultado = processar(
                self.original,
                com_ruido,
                callback_progresso=self.registrar_progresso,
                cancelado=self.cancelamento.is_set,
            )
        except ProcessamentoCancelado:
            self.fila_processamento.put(("cancelado",))
        except Exception as erro:
            self.fila_processamento.put(("erro", erro))
        else:
            self.fila_processamento.put(("concluido", resultado))

    def registrar_progresso(self, atual, total):
        # A atribuição da tupla é atômica no CPython. A interface lê somente o
        # valor mais recente, evitando bloquear o redesenho ao esvaziar uma fila.
        self.progresso_atual = (atual, total)
        # O filtro é intensivo em CPU. Ceder a execução ao final de cada linha
        # dá tempo para a thread principal redesenhar a barra e responder à UI.
        time.sleep(0)

    def verificar_processamento(self):
        atual, total = self.progresso_atual
        percentual = atual * 100 / total
        self.progresso.set(percentual)
        self.texto_progresso.set(f"{percentual:.0f}%")
        if atual < total:
            self.texto_status.set(f"Processando linha {atual} de {total}...")

        finalizado = False
        while True:
            try:
                evento = self.fila_processamento.get_nowait()
            except queue.Empty:
                break

            if evento[0] == "concluido":
                self.resultado = evento[1]
                self.finalizar_processamento()
                finalizado = True
            elif evento[0] == "cancelado":
                self.finalizar_cancelamento()
                finalizado = True
            elif evento[0] == "erro":
                self.finalizar_erro(evento[1])
                finalizado = True

        if not finalizado:
            self.janela.after(50, self.verificar_processamento)

    def restaurar_controles(self):
        self.botao_selecionar.config(state="normal")
        self.botao_filtrar.config(state="normal" if self.original is not None else "disabled")
        self.caixa_ruido.config(state="normal")
        self.botao_cancelar.config(state="disabled")

    def finalizar_processamento(self):
        self.restaurar_controles()
        self.progresso.set(100)
        self.texto_progresso.set("100%")
        self.mostrar("filtrada", self.resultado["filtrada"])
        self.botao_salvar.config(state="normal")

        if self.resultado["ruidosa"] is not None:
            self.mostrar("ruidosa", self.resultado["ruidosa"])
            self.texto_metricas.set(
                f"Tempo: {self.resultado['tempo']:.2f} s  •  "
                f"PSNR ruidosa: {self.resultado['psnr_ruidosa']:.2f} dB  •  "
                f"PSNR filtrada: {self.resultado['psnr_filtrada']:.2f} dB"
            )
        else:
            self.limpar("ruidosa", "Ruído não adicionado")
            self.texto_metricas.set(
                f"Tempo: {self.resultado['tempo']:.2f} s  •  "
                "PSNR indisponível sem uma referência ruidosa"
            )

        self.texto_status.set("Processamento concluído. Explore as abas ou salve o resultado.")
        self.atualizar_detalhe()

    def finalizar_cancelamento(self):
        self.restaurar_controles()
        self.botao_salvar.config(state="disabled")
        self.progresso.set(0)
        self.texto_progresso.set("0%")
        self.texto_status.set("Processamento cancelado pelo usuário.")

    def finalizar_erro(self, erro):
        self.restaurar_controles()
        self.botao_salvar.config(state="disabled")
        self.texto_status.set("Erro durante o processamento.")
        messagebox.showerror("Erro", f"Falha ao aplicar o filtro:\n{erro}", parent=self.janela)

    def cancelar_processamento(self):
        if self.thread is None or not self.thread.is_alive():
            return
        self.cancelamento.set()
        self.botao_cancelar.config(state="disabled")
        self.texto_status.set("Cancelando o processamento...")

    def atualizar_detalhe(self):
        self.rotulo_zoom.config(text=f"{self.zoom.get():.0f}%")
        if self.original is None or self.resultado is None:
            return

        original = Image.fromarray(self.original)
        filtrada = Image.fromarray(self.resultado["filtrada"])
        corte = round(original.width * self.divisor.get() / 100)
        composicao = original.copy()
        if corte < original.width:
            composicao.paste(filtrada.crop((corte, 0, original.width, original.height)), (corte, 0))

        escala = self.zoom.get() / 100
        tamanho = (
            max(1, round(composicao.width * escala)),
            max(1, round(composicao.height * escala)),
        )
        composicao = composicao.resize(tamanho, Image.Resampling.LANCZOS)
        self.foto_detalhe = ImageTk.PhotoImage(composicao)

        largura_canvas = max(1, self.canvas_detalhe.winfo_width())
        altura_canvas = max(1, self.canvas_detalhe.winfo_height())
        deslocamento_x = max(0, (largura_canvas - tamanho[0]) // 2)
        deslocamento_y = max(0, (altura_canvas - tamanho[1]) // 2)
        posicao_divisor = round(corte * escala)
        self.canvas_detalhe.delete("all")
        self.canvas_detalhe.create_image(
            deslocamento_x,
            deslocamento_y,
            anchor="nw",
            image=self.foto_detalhe,
        )
        self.canvas_detalhe.create_line(
            deslocamento_x + posicao_divisor,
            deslocamento_y,
            deslocamento_x + posicao_divisor,
            deslocamento_y + tamanho[1],
            fill="#00a3ff",
            width=3,
        )
        self.canvas_detalhe.create_text(
            deslocamento_x + 12,
            deslocamento_y + 12,
            anchor="nw",
            text="ORIGINAL",
            fill="white",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.canvas_detalhe.create_text(
            deslocamento_x + tamanho[0] - 12,
            deslocamento_y + 12,
            anchor="ne",
            text="FILTRADA",
            fill="white",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.canvas_detalhe.configure(
            scrollregion=(
                0,
                0,
                max(largura_canvas, tamanho[0]),
                max(altura_canvas, tamanho[1]),
            )
        )

    def aumentar_zoom(self):
        self.zoom.set(min(300, self.zoom.get() + 25))
        self.atualizar_detalhe()

    def diminuir_zoom(self):
        self.zoom.set(max(25, self.zoom.get() - 25))
        self.atualizar_detalhe()

    def ajustar_zoom(self):
        if self.original is None:
            return
        self.janela.update_idletasks()
        largura = max(1, self.canvas_detalhe.winfo_width() - 8)
        altura = max(1, self.canvas_detalhe.winfo_height() - 8)
        zoom = min(largura / self.original.shape[1], altura / self.original.shape[0]) * 100
        self.zoom.set(max(25, min(300, zoom)))
        self.atualizar_detalhe()

    def mostrar_sobre(self):
        messagebox.showinfo(
            "Sobre",
            "Filtro de Mediana das Medianas\n\n"
            "Compare a imagem original, a versão com ruído sal e pimenta "
            "e o resultado filtrado.",
            parent=self.janela,
        )

    def salvar_filtrada(self):
        if self.resultado is None:
            return

        caminho = filedialog.asksaveasfilename(
            parent=self.janela,
            title="Salvar imagem filtrada",
            initialdir=DIRETORIO_IMAGENS,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")],
        )
        if not caminho:
            return

        try:
            salvar_imagem(self.resultado["filtrada"], caminho)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Erro", f"Não foi possível salvar a imagem:\n{erro}")
            return

        self.texto_status.set(f"Imagem filtrada salva em: {caminho}")

    def fechar(self, _evento=None):
        if self.encerrando:
            return
        self.encerrando = True
        self.cancelamento.set()
        self.janela.destroy()


if __name__ == "__main__":
    janela = tk.Tk()
    aplicacao = Aplicacao(janela)
    signal.signal(signal.SIGINT, lambda _sinal, _quadro: aplicacao.fechar())

    # Mantém o interpretador acordado para que o SIGINT (Ctrl+C) seja
    # processado mesmo enquanto o Tkinter aguarda eventos da interface.
    def verificar_sinais():
        janela.after(100, verificar_sinais)

    janela.after(100, verificar_sinais)
    try:
        janela.mainloop()
    except KeyboardInterrupt:
        aplicacao.fechar()
