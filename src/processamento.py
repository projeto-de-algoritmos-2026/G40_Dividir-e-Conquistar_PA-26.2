import numpy as np
from PIL import Image


def abrir_imagem(caminho):
    with Image.open(caminho) as imagem:
        return np.array(imagem.convert("L"))


def adicionar_ruido_sal_pimenta(imagem):
    imagem_ruidosa = imagem.copy()
    quantidade = int(imagem.size * 0.05)
    indices = np.random.choice(imagem.size, quantidade * 2, replace=False)

    imagem_ruidosa.flat[indices[:quantidade]] = 0
    imagem_ruidosa.flat[indices[quantidade:]] = 255

    return imagem_ruidosa


def calcular_psnr(original, imagem):
    if original.shape != imagem.shape:
        raise ValueError("As imagens devem ter as mesmas dimensões")

    erro_quadratico_medio = np.mean(
        (original.astype(np.float64) - imagem.astype(np.float64)) ** 2
    )
    if erro_quadratico_medio == 0:
        return float("inf")

    return 20 * np.log10(255 / np.sqrt(erro_quadratico_medio))


def salvar_imagem(imagem, caminho):
    matriz = np.clip(imagem, 0, 255).astype(np.uint8)
    Image.fromarray(matriz).save(caminho)


def criar_imagem_comparacao(original, ruidosa, filtrada):
    if original.shape != ruidosa.shape or original.shape != filtrada.shape:
        raise ValueError("As imagens devem ter as mesmas dimensões")

    return np.hstack((original, ruidosa, filtrada))
