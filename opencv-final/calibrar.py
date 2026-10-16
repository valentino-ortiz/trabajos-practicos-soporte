"""Calibración asistida de los umbrales de un preset: textura (umbral_std) y color (umbral_color).

Interactivo:  calibrar.py PRESET --frame F
    Guarda el frame con cada celda numerada en 4 mitades (gt/calibrar_N_F_a..d.png), a tamaño real.
    En la terminal escribís los números de las celdas libres y de las ocupadas, separados por espacio.
    Hacen falta 2 o más de cada tipo. Se guarda en config.json.
Desde etiquetas: calibrar.py PRESET --desde-gt F   (usa gt_labels.json, sin ventana)
"""
import argparse
import json
import cv2
import numpy as np
from common import DIR, cargar_celdas, cargar_preset, guardar_mosaicos
from detector import Detector


def mejor_umbral(valores, ocupada):
    """Umbral que maximiza la exactitud balanceada (ocupada si valor > umbral)."""
    v, y = np.asarray(valores, float), np.asarray(ocupada, bool)
    o = np.unique(v)
    if len(o) < 2:
        return float(o[0])
    cand = (o[1:] + o[:-1]) / 2
    ba = [((v[y] > t).mean() + (v[~y] <= t).mean()) / 2 for t in cand]
    return float(cand[int(np.argmax(ba))])


def calcular_umbrales(det, img, ids, ocupada):
    """Textura primero; el umbral de color se ajusta solo con las celdas que la textura ve lisas,
    que es justo donde la textura falla (autos oscuros o rojos)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ids, ocupada = np.asarray(ids), np.asarray(ocupada, bool)
    std, _ = det.medir(img, gray)
    t_std = mejor_umbral(std[ids], ocupada)
    det.cfg["umbral_std"] = t_std  # el color del asfalto se estima con este umbral: se vuelve a medir
    _, dist = det.medir(img, gray)
    lisas = std[ids] <= t_std
    d, oc = dist[ids][lisas], ocupada[lisas]
    if oc.any() and (~oc).any():
        t_color = mejor_umbral(d, oc)
    elif (~oc).any():  # la muestra no tiene autos lisos: solo se evita marcar ocupado el asfalto
        t_color = float(d.max() * 1.1)
    else:
        t_color = None
    return t_std, t_color


def medir_en_frame(n, frame):
    cfg = cargar_preset(n)
    det = Detector(cargar_celdas(cfg["celdas"]), cfg)
    cap = cv2.VideoCapture(str(DIR / cfg["video"]))
    for _ in range(frame + 1):  # se recorre el video para que la estabilización llegue alineada
        ok, img = cap.read()
        if not ok:
            raise SystemExit(f"El video no tiene el frame {frame}")
        det.update(img)
    return det, img


def guardar(n, frame, t_std, t_color):
    path = DIR / "config.json"
    cfg = json.loads(path.read_text())
    cfg[str(n)].update(umbral_std=round(t_std, 2), calibrado_en=frame)
    if t_color is None:
        cfg[str(n)].pop("umbral_color", None)
    else:
        cfg[str(n)]["umbral_color"] = round(t_color, 2)
    path.write_text(json.dumps(cfg, indent=2))
    print(f"preset {n}: umbral_std = {t_std:.2f}, umbral_color = {t_color} (calibrado en frame {frame})")


def _ids(texto):
    return {int(t) for t in texto.replace(",", " ").split() if t.isdigit()}


def interactivo(n, frame):
    det, img = medir_en_frame(n, frame)
    std, _ = det.medir(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    e = 2  # escala para que el número entre en la celda
    vis = cv2.resize(img, None, fx=e, fy=e, interpolation=cv2.INTER_CUBIC)
    for i, p in enumerate(det.poligonos()):
        if np.isnan(std[i]):
            continue
        p = np.round(p * e).astype(np.int32)
        cv2.polylines(vis, [p], True, (0, 255, 255), 2)
        cx, cy = p.mean(0).astype(int)
        cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    # cuatro mitades a tamaño real: en una sola imagen los números no se leen
    print("Imágenes con números (abrilas con cualquier visor):")
    for ruta in guardar_mosaicos(vis, f"calibrar_{n}_{frame}"):
        print(f"  {ruta}")
    libres = _ids(input("Celdas LIBRES (números separados por espacio): "))
    ocupadas = _ids(input("Celdas OCUPADAS (números separados por espacio): "))
    if libres & ocupadas:
        raise SystemExit(f"Estas celdas están en las dos listas: {sorted(libres & ocupadas)}")
    validas = [i for i in libres | ocupadas if i < len(std) and not np.isnan(std[i])]
    if len(validas) != len(libres | ocupadas) or len(libres) < 2 or len(ocupadas) < 2:
        raise SystemExit("Hace falta al menos 2 números de cada tipo, y que existan en la imagen")
    ids = sorted(libres | ocupadas)
    guardar(n, frame, *calcular_umbrales(det, img, ids, [i in ocupadas for i in ids]))


def desde_gt(n, frame):
    g = json.loads((DIR / "gt_labels.json").read_text())[str(n)][str(frame)]
    det, img = medir_en_frame(n, frame)
    std, _ = det.medir(img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    lib, dud, al = set(g["libres"]), set(g["dudosas"]), g.get("alcance")
    ids = [i for i in range(len(std)) if not np.isnan(std[i]) and i not in dud and (al is None or i in al)]
    guardar(n, frame, *calcular_umbrales(det, img, ids, [i not in lib for i in ids]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("preset", type=int)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--frame", type=int)
    grupo.add_argument("--desde-gt", type=int, metavar="FRAME")
    a = ap.parse_args()
    if a.frame is not None:
        interactivo(a.preset, a.frame)
    else:
        desde_gt(a.preset, a.desde_gt)
