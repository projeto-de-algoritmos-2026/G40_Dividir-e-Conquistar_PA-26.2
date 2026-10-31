import numpy as np 
from mediana_das_medianas import mediana 

JANELA = 15
LIMIAR = 40


def aplicar_filtro(img):
    altura, largura = img.shape 
    raio = JANELA // 2
    expandida = np.pad(img, raio, mode="edge")
    saida = img.copy()

    for i in range(altura):
        for j in range(largura):
            pixels_janela = expandida[i:i + JANELA, j:j + JANELA].ravel().tolist()
            valor_mediana = mediana(pixels_janela)
            if abs(int(img[i, j]) - valor_mediana) > LIMIAR:
                saida[i, j] = valor_mediana

    return saida