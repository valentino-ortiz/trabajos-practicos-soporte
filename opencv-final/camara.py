"""Cámara en vivo para el dashboard: corre el detector de main.py en un hilo y deja el último frame en JPEG.
Arranca en pausa; la sesión se crea con el primer play y el video, al terminar, se pausa solo."""
import threading
import time

import cv2

from common import cargar_celdas, cargar_preset
from detector import Detector
from main import Registrador, dibujar


class Camara:
    def __init__(self, preset):
        self.corriendo = threading.Event()
        self.preset = preset
        self.pedido = preset  # preset a cargar; lo aplica el hilo, que es dueño del video y de la conexión SQLite
        self.jpeg = None
        threading.Thread(target=self._loop, daemon=True).start()

    def alternar(self):
        self.corriendo.clear() if self.corriendo.is_set() else self.corriendo.set()

    def cambiar(self, preset):
        self.corriendo.clear()
        self.preset = self.pedido = preset

    def stream(self):
        """Generador MJPEG (multipart/x-mixed-replace)."""
        while True:
            if self.jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self.jpeg + b"\r\n"
            time.sleep(1 / 30)

    def _publicar(self, img, cartel=None):
        if img is None:
            return
        if cartel:
            img = img.copy()
            cv2.rectangle(img, (45, 90), (45 + 16 * len(cartel), 135), (0, 0, 0), -1)
            cv2.putText(img, cartel, (50, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        self.jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()

    def _loop(self):
        cap = reg = None
        while True:
            if self.pedido is not None:
                preset, self.pedido = self.pedido, None
                if cap:
                    cap.release()
                if reg:
                    reg.cerrar()
                cfg = cargar_preset(preset)
                celdas = cargar_celdas(cfg["celdas"])
                cap = cv2.VideoCapture(cfg["video"])
                if not cap.isOpened():
                    raise RuntimeError(f"No se pudo abrir {cfg['video']}")
                fps = cap.get(cv2.CAP_PROP_FPS) or 30
                _, ultimo = cap.read()  # primer frame como vista previa en pausa
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                det, reg, nro, fin = Detector(celdas, cfg, cfg["stabilize"]), None, 0, False

            if not self.corriendo.is_set():
                self._publicar(ultimo, "FIN DEL VIDEO - play para nueva sesion" if fin else "PAUSADO")
                time.sleep(0.2)
                continue

            if fin:  # play después del final: rebobinar y empezar sesión nueva
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                reg.cerrar()
                det, reg, nro, fin = Detector(celdas, cfg, cfg["stabilize"]), None, 0, False
            if reg is None:
                reg = Registrador(preset, fps)

            t0 = time.perf_counter()
            ok, img = cap.read()
            if not ok or img is None:
                fin = True
                self.corriendo.clear()
                continue
            estados = det.update(img)
            reg.registrar(nro, estados)  # pausar no avanza nro, así que el tiempo simulado queda congelado
            nro += 1
            dibujar(img, det, estados, len(celdas), cfg)
            ultimo = img
            self._publicar(img)
            time.sleep(max(0.0, 1 / fps - (time.perf_counter() - t0)))
