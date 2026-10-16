import argparse
import cv2
import numpy as np

from common import cargar_celdas, cargar_preset, guardar_mosaicos
from detector import Detector


def main():
    parser = argparse.ArgumentParser(description="Detector de celdas de estacionamiento")
    parser.add_argument("--preset", type=int, default=1, help="Número de preset (ver config.json)")
    parser.add_argument("--video", help="Ruta al video a procesar")
    parser.add_argument("--celdas", help="Archivo JSON con las celdas")
    parser.add_argument("--umbral", type=float, help="Umbral de textura (desvío estándar); pisa umbral_std del preset")
    parser.add_argument("--no-stabilize", action="store_true", help="Desactivar compensación de movimiento de cámara")
    args = parser.parse_args()

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
    frame_delay = max(1, round(1000 / fps)) if fps > 0 else 33

    det = Detector(celdas, cfg, stabilize)
    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Image", 1280, 720)

    while True:
        ok, img = cap.read()
        if not ok or img is None:
            break
        estados = det.update(img)
        crudo = img.copy()  # para la captura 's', sin lo dibujado encima
        ox, oy = det.offset
        for poly, libre in zip(det.poligonos(), estados):
            if libre is None:
                continue
            color, thick = ((0, 255, 0), 5) if libre else ((0, 0, 255), 2)
            cv2.polylines(img, [np.round(poly).astype(np.int32)], True, color, thick)
        info = f'Libres: {estados.count(True)}/{len(celdas)} (T:{cfg.get("umbral_std", 40)})'
        if stabilize:
            info += f' Off:({ox},{oy})'
        cv2.rectangle(img, (45, 30), (420, 75), (180, 0, 180), -1)
        cv2.putText(img, info, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("Image", img)
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == ord('p'):  # pausa hasta la próxima tecla (que también se procesa)
            key = cv2.waitKey(0) & 0xFF
        if key == ord('s'):
            nro = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
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
            for ruta in guardar_mosaicos(vis, f"snap_{args.preset}_{nro}"):
                print(f"  {ruta}")
        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
