"""Agrega un frame al ground truth a partir de una captura de main.py (tecla 's') y los errores que ves.

Uso: agregar_gt.py PRESET FRAME --vacias-ocupadas 22 138 --autos-libres 279
  --vacias-ocupadas: celdas VACÍAS que el detector marcó rojas (ocupadas)
  --autos-libres:    celdas con AUTO que el detector marcó verdes (libres)
Las demás celdas se toman como bien clasificadas (el detector es la base): sirve para medir errores y
regresiones, no como verdad independiente. Se guarda con "origen": "capturas" para distinguirlo.
Corre el video hasta FRAME (tarda lo mismo que main.py hasta ahí)."""
import argparse
import json
import cv2
from common import DIR, cargar_celdas, cargar_preset
from detector import Detector

ap = argparse.ArgumentParser()
ap.add_argument("preset", type=int)
ap.add_argument("frame", type=int)
ap.add_argument("--vacias-ocupadas", type=int, nargs="*", default=[])
ap.add_argument("--autos-libres", type=int, nargs="*", default=[])
a = ap.parse_args()
if set(a.vacias_ocupadas) & set(a.autos_libres):
    raise SystemExit("Una celda no puede estar en las dos listas")

cfg = cargar_preset(a.preset)
det = Detector(cargar_celdas(cfg["celdas"]), cfg)
cap = cv2.VideoCapture(str(DIR / cfg["video"]))
for _ in range(a.frame + 1):
    ok, img = cap.read()
    if not ok:
        raise SystemExit(f"El video no tiene el frame {a.frame}")
    est = det.update(img)
n = len(est)
if any(i >= n or est[i] is None for i in a.vacias_ocupadas + a.autos_libres):
    raise SystemExit("Hay celdas que no existen o están fuera de imagen en ese frame")
bad_v = [i for i in a.vacias_ocupadas if est[i]]
bad_a = [i for i in a.autos_libres if not est[i]]
if bad_v or bad_a:
    raise SystemExit(f"No coincide con la captura: {bad_v} ya estaban verdes, {bad_a} ya estaban rojas")

libres = {i for i, e in enumerate(est) if e}
libres |= set(a.vacias_ocupadas)
libres -= set(a.autos_libres)
path = DIR / "gt_labels.json"
gt = json.loads(path.read_text())
gt.setdefault(str(a.preset), {})[str(a.frame)] = {
    "libres": sorted(libres), "dudosas": [], "origen": "capturas",
    "errores": {"vacias_ocupadas": a.vacias_ocupadas, "autos_libres": a.autos_libres}}
path.write_text(json.dumps(gt))
print(f"preset {a.preset} frame {a.frame}: {len(libres)} libres, {len(a.vacias_ocupadas)} + {len(a.autos_libres)} errores cargados")
