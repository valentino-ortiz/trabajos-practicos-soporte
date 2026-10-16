import numpy as np
from autodetectar import candidatas


def imagen(celdas):  # asfalto con líneas pintadas solo en los bordes de las celdas dadas
    img = np.full((500, 200, 3), 80, np.uint8)
    for x, y, w, h in celdas:
        img[y - 1:y + 2, x:x + w] = 255
        img[y + h - 1:y + h + 2, x:x + w] = 255
    return img


# dos tramos de 3 celdas con un lugar faltante (pintado) en el medio: se propone ese lugar
pintadas = [[40, 50 + k * 30, 60, 30] for k in range(7)]
manual = [c for k, c in enumerate(pintadas) if k != 3]
cand = candidatas(manual, imagen(pintadas))
assert any(c[:2] == (40, 140) for c in cand), cand
assert not any(c[:2] == (40, y) for c in cand for y in (50, 80, 110, 170, 200, 230))  # no pisa manuales

# isla de 2.3 pasos sin líneas entre dos tramos: no se rellena
manual = [[40, 50 + k * 30, 60, 30] for k in (0, 1, 2)] + [[40, 50 + k * 30 + 39, 60, 30] for k in (4, 5, 6)]
assert not any(110 < c[1] < 199 for c in candidatas(manual, imagen(manual)))
print("ok")
