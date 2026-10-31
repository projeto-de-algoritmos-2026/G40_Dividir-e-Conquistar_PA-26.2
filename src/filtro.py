import numpy as np 
from mediana_das_medianas import mediana 

janela = 15 
limiar = 40


def aplicar_filtro(img):
    altura, largura = img.shape 
    raio = janela // 2
    expandida = np.pad(img, raio, mode="edge")
    saida = img.copy()

    for i in range(altura):
        for j in range(largura):
            janela = expandida[i:i + janela, j:j + janela].ravel().tolist()
            valor_mediana = mediana(janela)
            if abs(int(img[i, j]) - valor_mediana) > limiar:
                saida[i, j] = valor_mediana

    return saida