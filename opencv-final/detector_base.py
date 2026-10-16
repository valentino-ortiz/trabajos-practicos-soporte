import cv2
import numpy as np


def calcular_offset_frame(prev_gray, cur_gray):
    """Desplazamiento global (dx, dy) entre dos frames: mediana de Lucas-Kanade sobre Shi-Tomasi."""
    pts_prev = cv2.goodFeaturesToTrack(prev_gray, mask=None, maxCorners=200,
                                       qualityLevel=0.01, minDistance=30, blockSize=7)
    if pts_prev is None or len(pts_prev) < 10:
        return 0.0, 0.0
    pts_cur, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray, cur_gray, pts_prev, None, winSize=(21, 21), maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    ok = status.flatten() == 1
    if ok.sum() < 5:
        return 0.0, 0.0
    deltas = (pts_cur[ok] - pts_prev[ok]).reshape(-1, 2)
    return float(np.median(deltas[:, 0])), float(np.median(deltas[:, 1]))


class Detector:
    """Algoritmo base (Fase 0). update(frame) -> lista por celda: True libre, False ocupada, None fuera de imagen."""

    def __init__(self, celdas, cfg, stabilize=None, alpha=0.15):
        self.celdas = celdas
        self.cfg = cfg
        self.stabilize = cfg.get("stabilize", False) if stabilize is None else stabilize
        self.alpha = alpha
        self.base_area = cfg["ancho"] * cfg["alto"]
        self.prev_gray = None
        self.acum = [0.0, 0.0]
        self.offset = (0, 0)
        self.smoothed = [0.0] * len(celdas)

    def procesar(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self.stabilize:
            if self.prev_gray is not None:
                dx, dy = calcular_offset_frame(self.prev_gray, gray)
                self.acum[0] += dx
                self.acum[1] += dy
                self.offset = (int(round(self.acum[0])), int(round(self.acum[1])))
            self.prev_gray = gray.copy()
        blur = cv2.GaussianBlur(gray, (3, 3), 1)
        trhe = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
                                     self.cfg["thresh_block_size"], self.cfg["thresh_c"])
        k = np.ones((3, 3), np.uint8)
        op = cv2.morphologyEx(cv2.medianBlur(trhe, 5), cv2.MORPH_OPEN, k)
        return cv2.dilate(op, k)

    def update(self, img):
        binaria = self.procesar(img)
        ox, oy = self.offset
        H, W = binaria.shape
        estados = []
        for i, (px, py, pw, ph) in enumerate(self.celdas):
            x, y = px + ox, py + oy
            if y < 0 or x < 0 or y + ph > H or x + pw > W:
                estados.append(None)
                continue
            count = cv2.countNonZero(binaria[y:y + ph, x:x + pw])
            s = self.smoothed[i]
            self.smoothed[i] = count if s == 0 else self.alpha * count + (1 - self.alpha) * s
            umbral = int(self.cfg["threshold"] * pw * ph / self.base_area)
            estados.append(self.smoothed[i] < umbral)
        return estados
