import numpy as np 
from mediana_das_medianas import mediana 

JANELA = 15
LIMIAR = 40


class ProcessamentoCancelado(Exception):
    """Indica que o processamento foi interrompido pelo usuário."""


def aplicar_filtro(img, callback_progresso=None, cancelado=None):
    altura, largura = img.shape 
    raio = JANELA // 2
    expandida = np.pad(img, raio, mode="edge")
    saida = img.copy()

    for i in range(altura):
        if cancelado is not None and cancelado():
            raise ProcessamentoCancelado

        for j in range(largura):
            pixels_janela = expandida[i:i + JANELA, j:j + JANELA].ravel().tolist()
            valor_mediana = mediana(pixels_janela)
            if abs(int(img[i, j]) - valor_mediana) > LIMIAR:
                saida[i, j] = valor_mediana

        if callback_progresso is not None:
            callback_progresso(i + 1, altura)

    return saida
