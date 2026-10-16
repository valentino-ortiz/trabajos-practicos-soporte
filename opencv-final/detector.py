import cv2
import numpy as np

BRILLO_MIN = 20  # frames más oscuros (fade-in) se ignoran


def _features(gray, mask, n=300):
    p = cv2.goodFeaturesToTrack(gray, maxCorners=n, qualityLevel=0.01, minDistance=20, blockSize=7, mask=mask)
    return np.empty((0, 2), np.float32) if p is None else p.reshape(-1, 2)


class Detector:
    """update(frame) -> lista por celda: True libre, False ocupada, None fuera de imagen (o sin frame válido).

    - Estabilización: puntos de fondo de un frame de referencia, seguidos con Lucas-Kanade; cada frame se
      ajusta una similitud (traslación+rotación+escala) referencia->actual con RANSAC, sin acumular deltas.
    - Celdas: polígonos de 4 puntos transformados con esa similitud.
    - Señales: desvío estándar del gris dentro de la celda (textura: asfalto vacío es liso, un auto no) y
      distancia de color (Lab) al asfalto, para autos lisos que la textura no ve (oscuros, rojos).
      El color del asfalto se estima en cada frame con las celdas claramente lisas.
      Ocupada si cualquiera de las dos pasa su umbral: score = max(std / umbral_std, dist / umbral_color).
    - Estado: EMA, histéresis (dos umbrales) y N frames seguidos para confirmar un cambio.
    """

    def __init__(self, celdas, cfg, stabilize=None, alpha=0.15, histeresis=0.1, confirmar=5):
        self.cfg, self.alpha, self.h, self.N = cfg, alpha, histeresis, confirmar
        self.stabilize = cfg.get("stabilize", False) if stabilize is None else stabilize
        c = np.array(celdas, np.float32).reshape(-1, 4)
        x, y, w, h = c.T
        self.poly = np.stack([np.stack([x, y], 1), np.stack([x + w, y], 1),
                              np.stack([x + w, y + h], 1), np.stack([x, y + h], 1)], 1)  # (n,4,2)
        n = len(c)
        self.suave = np.full(n, np.nan)
        self.estado = np.zeros(n, bool)
        self.inicializado = np.zeros(n, bool)
        self.racha = np.zeros(n, int)
        self.M = np.array([[1, 0, 0], [0, 1, 0]], np.float32)  # referencia -> actual
        self.prev_gray = None
        self.centro = (960, 540)
        self.ref_pts = self.cur_pts = None
        self.asfalto = None  # color Lab medio del asfalto vacío

    @property
    def offset(self):  # desplazamiento en el centro de la imagen (el del origen se distorsiona con rotación/escala)
        c = np.array(self.centro, np.float32)
        d = self.M[:, :2] @ c + self.M[:, 2] - c
        return int(round(d[0])), int(round(d[1]))

    def _mascara_celdas(self, shape, M):
        mask = np.full(shape, 255, np.uint8)
        for p in self._transformar(M).astype(np.int32):
            cv2.fillConvexPoly(mask, p, 0)
        return mask

    def poligonos(self):
        return self._transformar(self.M)

    def _transformar(self, M):
        return self.poly @ M[:, :2].T + M[:, 2]

    def _estabilizar(self, gray):
        if self.prev_gray is None:
            self.ref_pts = _features(gray, self._mascara_celdas(gray.shape, self.M))
            self.cur_pts = self.ref_pts.copy()
        else:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(self.prev_gray, gray, self.cur_pts.reshape(-1, 1, 2), None,
                                                  winSize=(21, 21), maxLevel=3)
            ok = st.ravel() == 1
            self.ref_pts, self.cur_pts = self.ref_pts[ok], nxt.reshape(-1, 2)[ok]
            if len(self.ref_pts) >= 6:
                M, inl = cv2.estimateAffinePartial2D(self.ref_pts, self.cur_pts, method=cv2.RANSAC,
                                                     ransacReprojThreshold=3.0)
                if M is not None and inl.sum() >= 6:
                    self.M = M.astype(np.float32)
                    keep = inl.ravel() == 1
                    self.ref_pts, self.cur_pts = self.ref_pts[keep], self.cur_pts[keep]
            if len(self.ref_pts) < 80:  # reponer features perdidas, guardadas en coordenadas de referencia
                nuevos = _features(gray, self._mascara_celdas(gray.shape, self.M))
                if len(self.cur_pts):
                    d = np.linalg.norm(nuevos[:, None] - self.cur_pts[None], axis=2).min(1)
                    nuevos = nuevos[d > 15]
                if len(nuevos):
                    inv = cv2.invertAffineTransform(self.M)
                    self.ref_pts = np.vstack([self.ref_pts, nuevos @ inv[:, :2].T + inv[:, 2]])
                    self.cur_pts = np.vstack([self.cur_pts, nuevos])
        self.prev_gray = gray

    def medir(self, img, gray):
        """Por celda: (desvío estándar del gris, distancia de color al asfalto). NaN si la celda sale de la imagen."""
        H, W = gray.shape
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        std = np.full(len(self.poly), np.nan)
        color = np.full((len(self.poly), 3), np.nan)
        for i, p in enumerate(self.poligonos()):
            x0, y0 = np.floor(p.min(0)).astype(int)
            x1, y1 = np.ceil(p.max(0)).astype(int)
            if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
                continue
            m = np.zeros((y1 - y0, x1 - x0), np.uint8)
            cv2.fillConvexPoly(m, np.round(p - [x0, y0]).astype(np.int32), 1)
            std[i] = cv2.meanStdDev(gray[y0:y1, x0:x1], mask=m)[1][0, 0]
            color[i] = cv2.mean(lab[y0:y1, x0:x1], mask=m)[:3]
        # asfalto = mediana de las celdas bien lisas; un auto liso suelto no mueve la mediana
        lisas = std < 0.7 * self.cfg.get("umbral_std", 40)
        if lisas.sum() >= 5:
            self.asfalto = np.median(color[lisas], axis=0)
        dist = np.zeros(len(std)) if self.asfalto is None else np.linalg.norm(color - self.asfalto, axis=1)
        return std, dist

    def update(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        n = len(self.poly)
        if gray.mean() < BRILLO_MIN:
            return [None if not self.inicializado[i] else bool(self.estado[i]) for i in range(n)]
        self.centro = (gray.shape[1] / 2, gray.shape[0] / 2)
        if self.stabilize:
            self._estabilizar(gray)
        std, dist = self.medir(img, gray)
        # 40: valor típico hasta correr calibrar.py; sin umbral_color la señal de color queda apagada
        crudo = np.maximum(std / self.cfg.get("umbral_std", 40), dist / self.cfg.get("umbral_color", np.inf))
        valido = ~np.isnan(crudo)
        nuevo = valido & np.isnan(self.suave)
        self.suave[nuevo] = crudo[nuevo]
        act = valido & ~nuevo
        self.suave[act] = self.alpha * crudo[act] + (1 - self.alpha) * self.suave[act]

        score = self.suave
        self.estado[nuevo] = score[nuevo] < 1
        self.inicializado |= nuevo
        objetivo = self.estado.copy()
        objetivo[self.estado & (score > 1 + self.h)] = False
        objetivo[~self.estado & (score < 1 - self.h)] = True
        cambia = valido & ~nuevo & (objetivo != self.estado)
        self.racha = np.where(cambia, self.racha + 1, 0)
        flip = self.racha >= self.N
        self.estado[flip] = objetivo[flip]
        self.racha[flip] = 0
        return [bool(self.estado[i]) if valido[i] else None for i in range(n)]
