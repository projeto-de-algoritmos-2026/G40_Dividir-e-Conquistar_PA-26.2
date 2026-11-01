import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, UnidentifiedImageError
from filtro import aplicar_filtro
from processamento import (
    abrir_imagem,
    adicionar_ruido_sal_pimenta,
    calcular_psnr,
    salvar_imagem,
)

TAMANHO_PAINEL = 300

def processar(original, com_ruido=True):
    if com_ruido:
        entrada = adicionar_ruido_sal_pimenta(original)
    else:
        entrada = original

    inicio = time.perf_counter()
    filtrada = aplicar_filtro(entrada)
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
        self.janela.resizable(False, False)

        self.original = None
        self.resultado = None
        self.thread = None
        self.erro = None
        self.fotos = {}

        botoes = tk.Frame(janela, padx=10, pady=10)
        botoes.pack(fill="x")

        self.botao_selecionar = tk.Button(botoes, text="Selecionar imagem", command=self.selecionar_imagem)
        self.botao_selecionar.pack(side="left", padx=5)

        self.botao_filtrar = tk.Button(botoes, text="Aplicar filtro", command=self.aplicar_filtro, state="disabled")
        self.botao_filtrar.pack(side="left", padx=5)

        self.botao_salvar = tk.Button(botoes, text="Salvar imagem filtrada", command=self.salvar_filtrada, state="disabled")
        self.botao_salvar.pack(side="left", padx=5)

        self.com_ruido = tk.BooleanVar(value=True)
        self.caixa_ruido = tk.Checkbutton(botoes, text="Adicionar ruído sal e pimenta", variable=self.com_ruido)
        self.caixa_ruido.pack(side="left", padx=15)

        paineis = tk.Frame(janela, padx=10)
        paineis.pack()

        self.paineis = {}
        for coluna, (chave, titulo) in enumerate(
            [("original", "Original"), ("ruidosa", "Com ruído"), ("filtrada", "Filtrada")]
        ):
            tk.Label(paineis, text=titulo, font=("Arial", 11, "bold")).grid(row=0, column=coluna, pady=(0, 5))
            moldura = tk.Frame(paineis, width=TAMANHO_PAINEL, height=TAMANHO_PAINEL, bg="#e0e0e0")
            moldura.grid(row=1, column=coluna, padx=5)
            moldura.pack_propagate(False)
            painel = tk.Label(moldura, bg="#e0e0e0")
            painel.pack(expand=True)
            self.paineis[chave] = painel

        rodape = tk.Frame(janela, padx=10, pady=10)
        rodape.pack(fill="x")

        self.barra = ttk.Progressbar(rodape, mode="determinate", length=200)
        self.barra.pack(side="left", padx=5)

        self.status = tk.Label(rodape, text="Selecione uma imagem para começar.", anchor="w")
        self.status.pack(side="left", padx=5, fill="x", expand=True)

    def mostrar(self, chave, array):
        imagem = Image.fromarray(array)
        imagem.thumbnail((TAMANHO_PAINEL, TAMANHO_PAINEL))
        foto = ImageTk.PhotoImage(imagem)
        self.fotos[chave] = foto
        self.paineis[chave].config(image=foto, text="")

    def limpar(self, chave, texto=""):
        self.paineis[chave].config(image="", text=texto)
        self.fotos.pop(chave, None)

    def selecionar_imagem(self):
        caminho = filedialog.askopenfilename(
            title="Selecione uma imagem",
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
        altura, largura = self.original.shape
        self.status.config(text=f"Imagem carregada ({largura} x {altura} pixels).")

    def aplicar_filtro(self):
        if self.original is None:
            return

        for widget in (self.botao_selecionar, self.botao_filtrar, self.botao_salvar, self.caixa_ruido):
            widget.config(state="disabled")
        self.status.config(text="Processando... aguarde.")
        self.barra.config(mode="indeterminate")
        self.barra.start(10)

        self.resultado = None
        self.erro = None
        self.thread = threading.Thread(
            target=self.processar_em_segundo_plano, args=(self.com_ruido.get(),), daemon=True
        )
        self.thread.start()
        self.janela.after(100, self.verificar_processamento)

    def processar_em_segundo_plano(self, com_ruido):
        try:
            self.resultado = processar(self.original, com_ruido)
        except Exception as erro:
            self.erro = erro

    def verificar_processamento(self):
        if self.thread.is_alive():
            self.janela.after(100, self.verificar_processamento)
            return

        self.barra.stop()
        self.barra.config(mode="determinate", value=0)
        self.botao_selecionar.config(state="normal")
        self.botao_filtrar.config(state="normal")
        self.caixa_ruido.config(state="normal")

        if self.erro is not None:
            self.status.config(text="Erro durante o processamento.")
            messagebox.showerror("Erro", f"Falha ao aplicar o filtro:\n{self.erro}")
            return

        self.mostrar("filtrada", self.resultado["filtrada"])
        self.botao_salvar.config(state="normal")

        if self.resultado["ruidosa"] is not None:
            self.mostrar("ruidosa", self.resultado["ruidosa"])
            self.status.config(
                text=f"Concluído em {self.resultado['tempo']:.2f} s  |  "
                     f"PSNR ruidosa: {self.resultado['psnr_ruidosa']:.2f} dB  |  "
                     f"PSNR filtrada: {self.resultado['psnr_filtrada']:.2f} dB"
            )
        else:
            self.limpar("ruidosa", "Ruído não adicionado")
            self.status.config(
                text=f"Concluído em {self.resultado['tempo']:.2f} s  |  "
                     f"Sem ruído adicionado: PSNR indisponível (não há imagem limpa de referência)"
            )

    def salvar_filtrada(self):
        if self.resultado is None:
            return

        caminho = filedialog.asksaveasfilename(
            title="Salvar imagem filtrada",
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

        self.status.config(text=f"Imagem filtrada salva em: {caminho}")


if __name__ == "__main__":
    janela = tk.Tk()
    Aplicacao(janela)
    janela.mainloop()