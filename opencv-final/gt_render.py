"""Renderiza frames con celdas numeradas para etiquetar a mano. Uso: gt_render.py PRESET FRAME [FRAME...]
Imágenes grandes salen en 4 mosaicos (_a.._d) con zoom 2x."""
import sys
import cv2
from common import DIR, cargar_celdas, cargar_preset

n = int(sys.argv[1])
cfg = cargar_preset(n)
celdas = cargar_celdas(cfg["celdas"])
cap = cv2.VideoCapture(str(DIR / cfg["video"]))
out = DIR / "gt"
out.mkdir(exist_ok=True)
for f in map(int, sys.argv[2:]):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ok, img = cap.read()
    grande = img.shape[1] >= 1500
    e = 2
    img = cv2.resize(img, None, fx=e, fy=e, interpolation=cv2.INTER_CUBIC)
    fs, th = (0.5, 1) if grande else (0.6, 2)
    for i, (x, y, w, h) in enumerate(celdas):
        x, y, w, h = x * e, y * e, w * e, h * e
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 255), 1)
        t = str(i)
        sz = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, fs, th)[0]
        cx, cy = x + (w - sz[0]) // 2, y + (h + sz[1]) // 2
        cv2.rectangle(img, (cx - 2, cy - sz[1] - 2), (cx + sz[0] + 2, cy + 3), (0, 0, 0), -1)
        cv2.putText(img, t, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), th)
    if not grande:
        cv2.imwrite(str(out / f"{n}_{f}.png"), img)
        continue
    H, W = img.shape[:2]
    for k, (r, c) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
        tile = img[r * H // 2:(r + 1) * H // 2, c * W // 2:(c + 1) * W // 2]
        cv2.imwrite(str(out / f"{n}_{f}_{'abcd'[k]}.png"), tile)
