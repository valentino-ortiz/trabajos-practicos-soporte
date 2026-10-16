"""Autodetección de celdas por propagación del patrón de las celdas manuales.

Agrupa las celdas manuales en pilas de celdas contiguas (columnas: mismo x y ancho, una debajo de otra; filas:
mismo y y alto, una al lado de otra), mide el paso y propone candidatas en huecos cortos de la pila y
extendiéndola hacia ambos lados. La extensión se corta en la primera candidata sin líneas pintadas.
Las celdas manuales nunca se modifican: solo se proponen candidatas que no se superponen con ellas.
Evidencia de cada candidata: cuánto se parecen sus líneas separadoras a las de las celdas manuales (1.0 = igual).
"""
import cv2
import numpy as np

EXTENDER = 3       # máximo de pasos que se extiende cada pila más allá de sus extremos
MIN_EVIDENCIA = 0.6
HUECO_MAX = 3      # huecos de hasta 3 celdas faltantes se rellenan


def _pilas(c, eje):
    """Pilas de celdas alineadas en el eje (0: columnas, 1: filas), ordenadas a lo largo, con su paso.
    Dentro de una pila se admiten huecos de hasta HUECO_MAX celdas."""
    pos, tam = c[:, eje], c[:, 2 + eje]
    orden = np.argsort(pos)
    grupos, cur = [], [orden[0]]
    for i in orden[1:]:
        if abs(pos[i] - pos[cur[-1]]) <= tam[i] * 0.2 and abs(tam[i] - tam[cur[-1]]) <= tam[i] * 0.2:
            cur.append(i)
        else:
            grupos.append(cur)
            cur = [i]
    grupos.append(cur)
    pilas = []
    for g in grupos:
        s = c[g][np.argsort(c[g][:, 1 - eje])]
        d = np.diff(s[:, 1 - eje])
        largo = np.median(s[:, 3 - eje])
        contiguas = d[d <= 1.5 * largo]
        if len(contiguas) < 2:
            continue
        paso = float(np.median(contiguas))
        tramos = [t for t in np.split(s, np.where(d > 1.5 * largo)[0] + 1) if len(t) >= 3]
        # se unen tramos separados por un hueco que sea casi un múltiplo exacto del paso (lugares faltantes);
        # islas y zonas rayadas no caen en múltiplos exactos y quedan como pilas separadas
        unidos = tramos[:1]
        for t in tramos[1:]:
            r = (t[0, 1 - eje] - unidos[-1][-1, 1 - eje]) / paso
            if r <= HUECO_MAX + 1 and abs(r - round(r)) < 0.15:
                unidos[-1] = np.vstack([unidos[-1], t])
            else:
                unidos.append(t)
        pilas += [(t, paso) for t in unidos]
    return pilas


def _solapa(a, b, frac=0.2):
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ix * iy > frac * min(a[2] * a[3], b[2] * b[3])


def _borde(gray, celda, eje):
    """Fracción del borde (arriba/abajo en columnas, izq/der en filas) donde hay una línea fina clara:
    el píxel del borde es más claro que los que están 4 px hacia adentro y hacia afuera."""
    g = gray if eje == 0 else gray.T          # en filas se trabaja sobre la imagen transpuesta
    x, y, w, h = celda if eje == 0 else (celda[1], celda[0], celda[3], celda[2])
    H = g.shape[0]
    fr = []
    for yy in (y, y + h):
        if yy - 5 < 0 or yy + 6 > H:
            fr.append(0.0)
            continue
        linea = g[yy - 1:yy + 2, x:x + w].max(0).astype(int)  # tolera ±1 px de error en la posición
        fr.append(float(((linea > g[yy - 5, x:x + w] + 15) & (linea > g[yy + 5, x:x + w] + 15)).mean()))
    return float(np.mean(fr))


def candidatas(celdas, img):
    """Devuelve [(x, y, w, h, evidencia)] ordenadas de mayor a menor evidencia (1.0 = como las manuales)."""
    c = np.array(celdas, int).reshape(-1, 4)
    if len(c) < 3:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    props = []
    for eje in (0, 1):
        for s, paso in _pilas(c, eje):
            tipica = np.median([_borde(gray, cel, eje) for cel in s])
            if tipica < 0.1:  # la pila manual no muestra líneas: no hay patrón que comparar
                continue
            base = np.median(s, axis=0).astype(int)  # posición transversal y tamaño de la pila

            def evaluar(p):
                cel = base.copy()
                cel[1 - eje] = int(round(p))
                x, y, w, h = cel
                if x < 0 or y < 0 or x + w > W or y + h > H:
                    return None
                return (x, y, w, h, round(min(_borde(gray, cel, eje) / tipica, 1.0), 2))

            for a, b in zip(s[:-1, 1 - eje], s[1:, 1 - eje]):    # huecos internos
                for j in range(1, int(round((b - a) / paso))):
                    props.append(evaluar(a + j * paso))
            for inicio, sentido in ((s[0, 1 - eje], -1), (s[-1, 1 - eje], 1)):  # extensiones
                for j in range(1, EXTENDER + 1):
                    p = evaluar(inicio + sentido * j * paso)
                    if p is None or p[4] < MIN_EVIDENCIA:
                        break
                    props.append(p)
    props = [p for p in props if p is not None and p[4] >= MIN_EVIDENCIA]
    props.sort(key=lambda p: -p[4])
    elegidas = []
    for p in props:
        if not any(_solapa(p, q) for q in list(c) + elegidas):
            elegidas.append(p)
    return elegidas
