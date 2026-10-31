def mediana(valores):
    return selecionar(valores, (len(valores) - 1 ) // 2)


def selecionar(valores, k):
    if len(valores) <=5:
        return ordenar_por_insercao(valores)[k]

    pivo = escolher_pivo(valores)
    menores, iguais, maiores = particionar(valores, pivo)

    if k < len(menores):
        return selecionar(menores, k)
    if k < len(menores) + len(iguais):
        return pivo
    return selecionar(maiores, k - len(menores) - len(iguais))

def escolher_pivo(valores):
    medianas = []
    for inicio in range(0,len(valores), 5):
        grupo = ordenar_por_insercao(valores[inicio:inicio + 5])
        medianas.append(grupo[(len(grupo) - 1) // 2])
    return selecionar(medianas, (len(medianas) - 1) // 2)

def particionar(valores,pivo):
    menores = []
    iguais = []
    maiores = []
    for valor in valores:
        if valor < pivo:
            menores.append(valor)
        elif valor > pivo:
            maiores.append(valor)
        else:
            iguais.append(valor)
    return menores, iguais, maiores

def ordenar_por_insercao(valores):
    ordenada = list(valores)
    for i in range(1,len(ordenada)):
        atual = ordenada[i]
        j = i-1
        while j>= 0 and ordenada[j] > atual:
            ordenada[j+1] = ordenada[j]
            j-= 1
        ordenada[j+1]= atual 
    return ordenada