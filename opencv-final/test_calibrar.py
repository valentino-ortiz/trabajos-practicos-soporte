from calibrar import mejor_umbral

# separables: el umbral cae entre el máximo libre (10) y el mínimo ocupado (40)
assert 10 < mejor_umbral([5, 10, 40, 50], [False, False, True, True]) < 40
# un outlier libre alto no arrastra el umbral por encima de la mayoría ocupada
assert mejor_umbral([5, 6, 7, 60, 40, 45, 50], [0, 0, 0, 0, 1, 1, 1]) < 40
print("ok")

# umbral_color: un auto liso pero oscuro (std bajo, color lejos del asfalto) queda ocupado
import numpy as np
from calibrar import calcular_umbrales


class DetFalso:  # devuelve mediciones fijas: 4 libres lisas, 2 autos con textura, 1 auto liso oscuro
    cfg = {}

    def medir(self, img, gray):
        return np.array([5., 6, 7, 8, 60, 70, 6.5]), np.array([2., 3, 2, 4, 30, 25, 40])


img = np.zeros((10, 10, 3), np.uint8)
t_std, t_color = calcular_umbrales(DetFalso(), img, range(7), [0, 0, 0, 0, 1, 1, 1])
assert 8 < t_std < 60, t_std                             # la textura sola no ve al auto liso (6.5)
assert 4 < t_color < 40, t_color                           # separa asfalto (<=4) del auto liso (40)
print("ok color")
