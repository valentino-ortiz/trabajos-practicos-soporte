import argparse
import time

import cv2
import numpy as np

from common import cargar_celdas, cargar_preset, guardar_mosaicos
from detector import Detector


def dibujar(img, det, estados, n_celdas, cfg, info_extra=""):
    for poly, libre in zip(det.poligonos(), estados):
        if libre is None:
            continue
        color, thick = ((0, 255, 0), 5) if libre else ((0, 0, 255), 2)
        cv2.polylines(img, [np.round(poly).astype(np.int32)], True, color, thick)
    info = f'Libres: {estados.count(True)}/{n_celdas} (T:{cfg.get("umbral_std", 40)})' + info_extra
    cv2.rectangle(img, (45, 30), (560, 75), (180, 0, 180), -1)
    cv2.putText(img, info, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def capturar(crudo, det, estados, preset, nro):
    vis = cv2.resize(crudo, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    for i, (poly, libre) in enumerate(zip(det.poligonos(), estados)):
        if libre is None:
            continue
        p = np.round(poly * 2).astype(np.int32)
        cv2.polylines(vis, [p], True, (0, 255, 0) if libre else (0, 0, 255), 3)
        cx, cy = p.mean(0).astype(int)
        cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(vis, str(i), (cx - 10, cy + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    print(f"Captura del frame {nro} (verde = libre, rojo = ocupada):")
    for ruta in guardar_mosaicos(vis, f"snap_{preset}_{nro}"):
        print(f"  {ruta}")


def main():
    parser = argparse.ArgumentParser(description="Detector de celdas de estacionamiento")
    parser.add_argument("--preset", type=int, default=1, help="Número de preset (ver config.json)")
    parser.add_argument("--video", help="Ruta al video a procesar")
    parser.add_argument("--celdas", help="Archivo JSON con las celdas")
    parser.add_argument("--umbral", type=float, help="Umbral de textura (desvío estándar); pisa umbral_std del preset")
    parser.add_argument("--no-stabilize", action="store_true", help="Desactivar compensación de movimiento de cámara")
    parser.add_argument("--cada", type=int, default=1, metavar="N",
                        help="Correr el detector cada N frames (los demás reutilizan el resultado). Default 1")
    parser.add_argument("--sin-ventana", action="store_true", help="No abrir ventana (más rápido, para medir o grabar)")
    parser.add_argument("--salida", help="Guardar el video con las celdas dibujadas (ej: salida.mp4)")
    parser.add_argument("--max-frames", type=int, help="Procesar solo los primeros N frames")
    args = parser.parse_args()
    if args.cada < 1:
        parser.error("--cada debe ser >= 1")

    cfg = dict(cargar_preset(args.preset))
    if args.umbral is not None:
        cfg["umbral_std"] = args.umbral
    video_file = args.video or cfg["video"]
    celdas = cargar_celdas(args.celdas or cfg["celdas"])
    stabilize = cfg["stabilize"] and not args.no_stabilize

    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {video_file}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_ms = 1000 / fps if fps > 0 else 33

    # al correr cada N frames, el suavizado y la confirmación se escalan para durar lo mismo en tiempo real
    N = args.cada
    det = Detector(celdas, cfg, stabilize, alpha=1 - (1 - 0.15) ** N, confirmar=max(1, round(5 / N)))

    escribir = None
    if args.salida:
        h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        escribir = cv2.VideoWriter(args.salida, cv2.VideoWriter_fourcc(*"mp4v"), fps or 30, (w, h))
        if not escribir.isOpened():
            raise RuntimeError(f"No se pudo crear {args.salida}")
    ventana = not args.sin_ventana
    if ventana:
        cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Image", 1280, 720)

    estados = [None] * len(celdas)
    acum = {"lectura": 0.0, "detector": 0.0, "estabilizar": 0.0, "medir": 0.0, "dibujo": 0.0}
    corridas = frames = 0
    ms_ema = None  # ms de procesamiento por frame (sin la espera de la ventana), para mostrar FPS
    t_inicio = time.perf_counter()

    while args.max_frames is None or frames < args.max_frames:
        t0 = time.perf_counter()
        ok, img = cap.read()
        if not ok or img is None:
            break
        t1 = time.perf_counter()
        if frames % N == 0:
            estados = det.update(img)
            corridas += 1
            acum["estabilizar"] += det.tiempos.get("estabilizar", 0)
            acum["medir"] += det.tiempos.get("medir", 0)
        t2 = time.perf_counter()
        crudo = img.copy() if ventana else None  # para la captura 's', sin lo dibujado encima
        ox, oy = det.offset
        extra = (f" Off:({ox},{oy})" if stabilize else "") + (f"  {1000 / ms_ema:.0f} FPS" if ms_ema else "")
        if ventana or escribir:
            dibujar(img, det, estados, len(celdas), cfg, extra)
        if escribir:
            escribir.write(img)
        t3 = time.perf_counter()
        acum["lectura"] += (t1 - t0) * 1e3
        acum["detector"] += (t2 - t1) * 1e3
        acum["dibujo"] += (t3 - t2) * 1e3
        frames += 1

        if ventana:
            cv2.imshow("Image", img)
            t4 = time.perf_counter()
            ms_ema = (t4 - t0) * 1e3 if ms_ema is None else 0.9 * ms_ema + 0.1 * (t4 - t0) * 1e3
            key = cv2.waitKey(max(1, round(frame_ms - (t4 - t0) * 1e3))) & 0xFF
            if key == ord('p'):  # pausa hasta la próxima tecla (que también se procesa)
                key = cv2.waitKey(0) & 0xFF
            if key == ord('s'):
                capturar(crudo, det, estados, args.preset, int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1)
            if key == ord('q'):
                break
        else:
            ms_ema = (t3 - t0) * 1e3 if ms_ema is None else 0.9 * ms_ema + 0.1 * (t3 - t0) * 1e3

    cap.release()
    if escribir:
        escribir.release()
    cv2.destroyAllWindows()

    total = time.perf_counter() - t_inicio
    if frames:
        print(f"\n{frames} frames en {total:.1f} s ({frames / total:.1f} FPS, el video original es de {fps:.0f})")
        print(f"Detector corrido {corridas} veces (cada {N} frames). Promedio por frame procesado:")
        print(f"  lectura del video : {acum['lectura'] / frames:6.1f} ms")
        print(f"  detector total    : {acum['detector'] / frames:6.1f} ms  (por frame, incluye los que se saltean)")
        print(f"     estabilización : {acum['estabilizar'] / max(corridas, 1):6.1f} ms  (por corrida)")
        print(f"     medición       : {acum['medir'] / max(corridas, 1):6.1f} ms  (por corrida)")
        print(f"  dibujo y salida   : {acum['dibujo'] / frames:6.1f} ms")


if __name__ == "__main__":
    main()
