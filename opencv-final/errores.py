"""Diagnóstico de errores contra gt_labels.json: textura sola vs textura+color, y qué señal causó cada error.
Uso: errores.py PRESET     (guarda gt/errores_N_FRAME_a..d.png: rojo = auto marcado libre, azul = vacía marcada ocupada)"""
import json
import sys
import cv2
import numpy as np
from common import DIR, cargar_celdas, cargar_preset, guardar_mosaicos
from detector import Detector


def correr(n, con_color):
    gt = json.loads((DIR / "gt_labels.json").read_text())[str(n)]
    cfg = dict(cargar_preset(n))
    if not con_color:
        cfg.pop("umbral_color", None)
    det = Detector(cargar_celdas(cfg["celdas"]), cfg)
    cap = cv2.VideoCapture(str(DIR / cfg["video"]))
    conf, errores, imagenes = dict(tp=0, fp=0, fn=0, tn=0), [], {}
    for f in range(max(map(int, gt)) + 1):
        ok, img = cap.read()
        estados = det.update(img)
        if str(f) not in gt:
            continue
        g = gt[str(f)]
        libres, dud, al = set(g["libres"]), set(g["dudosas"]), g.get("alcance")
        std, dist = det.medir(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        for i, e in enumerate(estados):
            if e is None or i in dud or (al is not None and i not in al):
                continue
            real = i in libres
            conf[("t" if real == e else "f") + ("p" if e else "n")] += 1
            if real != e:
                errores.append((f, i, real, e, std[i], dist[i], std[i] / cfg.get("umbral_std", 40),
                                dist[i] / cfg.get("umbral_color", np.inf), det.suave[i]))
        imagenes[f] = (img, det.poligonos())
    return cfg, conf, errores, imagenes


if __name__ == "__main__":
    n = int(sys.argv[1])
    for con_color in (False, True):
        cfg, conf, errores, imagenes = correr(n, con_color)
        print(f"{'textura + color' if con_color else 'solo textura   '}: {conf}")
    print(f"\numbral_std={cfg.get('umbral_std')} umbral_color={cfg.get('umbral_color')}")
    print("\nErrores (textura + color). 'real' y 'pred' dicen si la celda está LIBRE.")
    print("t_std y t_col son cada señal dividida por su umbral: >1 vota ocupada.")
    print("frame celda real   pred   std  dist  t_std  t_col  causa")
    por_causa = {}
    for f, i, real, pred, std, dist, ts, tc, _ in errores:
        if real:  # vacía marcada ocupada
            causa = "color" if tc > 1 >= ts else "textura" if ts > 1 >= tc else "ambas" if ts > 1 and tc > 1 else "suavizado"
        else:     # auto marcado libre
            causa = "ninguna señal lo ve"
        por_causa[(real, causa)] = por_causa.get((real, causa), 0) + 1
        print(f"{f:5d} {i:5d} {str(real):6s} {str(pred):6s} {std:5.1f} {dist:5.1f} {ts:6.2f} {tc:6.2f}  {causa}")
    print("\nResumen:")
    for (real, causa), k in sorted(por_causa.items()):
        print(f"  {'vacía marcada ocupada' if real else 'auto marcado libre'}: {causa} = {k}")
    for f, (img, pol) in imagenes.items():
        vis = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for fr, i, real, *_ in errores:
            if fr != f:
                continue
            p = np.round(pol[i] * 2).astype(np.int32)
            cv2.polylines(vis, [p], True, (255, 128, 0) if real else (0, 0, 255), 3)
            cx, cy = p.mean(0).astype(int)
            cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if any(e[0] == f for e in errores):
            print("Imágenes:", *guardar_mosaicos(vis, f"errores_{n}_{f}"))
