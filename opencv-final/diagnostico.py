"""Titileo (cambios de estado por celda) y offset estimado vs. correlación de fase contra el frame de referencia.
Uso: diagnostico.py PRESET [--base]"""
import sys
import cv2
import numpy as np
import detector, detector_base
from common import DIR, cargar_celdas, cargar_preset

n = int(sys.argv[1])
Det = detector_base.Detector if "--base" in sys.argv else detector.Detector
cfg = cargar_preset(n)
cap = cv2.VideoCapture(str(DIR / cfg["video"]))
det = Det(cargar_celdas(cfg["celdas"]), cfg)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
chk = {int(total * k) for k in (.25, .5, .75, .99)}
prev, cambios, ref = None, 0, None
for f in range(total):
    ok, img = cap.read()
    if not ok:
        break
    est = det.update(img)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if ref is None and g.mean() > 20:
        ref = np.float32(g)
    cur = np.array([-1 if e is None else int(e) for e in est])
    if prev is not None:
        cambios += int(((cur != prev) & (cur >= 0) & (prev >= 0)).sum())
    prev = cur
    if f in chk and ref is not None:
        (dx, dy), _ = cv2.phaseCorrelate(ref, np.float32(g))
        print(f"  frame {f}: offset estimado {det.offset}  fase(-dx,-dy)=({-dx:.1f},{-dy:.1f})")
print(f"preset {n}: {cambios} cambios de estado, {cambios / len(prev):.2f} por celda")
