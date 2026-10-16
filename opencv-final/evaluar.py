"""Métricas contra gt_labels.json. Positivo = celda libre. Excluye celdas dudosas y fuera de imagen,
y el frame donde se calibró el preset (calibrado_en), para no evaluar sobre lo que se usó para calibrar.
Uso: evaluar.py [PRESET ...]"""
import json
import sys
import cv2
from common import DIR, cargar_celdas, cargar_preset
import argparse
import detector, detector_base


def evaluar(n, Det):
    gt = json.loads((DIR / "gt_labels.json").read_text()).get(str(n), {})
    if not gt:
        return None
    cfg = cargar_preset(n)
    celdas = cargar_celdas(cfg["celdas"])
    det = Det(celdas, cfg)
    cap = cv2.VideoCapture(str(DIR / cfg["video"]))
    tp = fp = fn = tn = 0
    for f in range(max(map(int, gt)) + 1):
        ok, img = cap.read()
        if not ok:
            break
        estados = det.update(img)
        if str(f) not in gt or f == cfg.get("calibrado_en"):
            continue
        libres, dud = set(gt[str(f)]["libres"]), set(gt[str(f)]["dudosas"])
        alcance = gt[str(f)].get("alcance")  # None = todas las celdas
        for i, e in enumerate(estados):
            if e is None or i in dud or (alcance is not None and i not in alcance):
                continue
            real = i in libres
            tp += real and e
            fp += (not real) and e
            fn += real and (not e)
            tn += (not real) and (not e)
    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=round(p, 3), recall=round(r, 3),
                exactitud=round((tp + tn) / (tp + tn + fp + fn), 3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("presets", nargs="*", type=int, default=[1, 2, 3])
    ap.add_argument("--base", action="store_true", help="usar el detector original de la fase 0")
    a = ap.parse_args()
    Det = detector_base.Detector if a.base else detector.Detector
    for n in a.presets:
        print(f"preset {n}:", evaluar(n, Det))
