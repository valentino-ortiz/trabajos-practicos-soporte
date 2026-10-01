import os
import argparse
import cv2
import numpy as np
from collections import OrderedDict
import os


class RastreadorCentroides:
    """Rastreador simple por centroides para objetos detectados."""

    def __init__(self, maxDesaparecidos=50, maxDistancia=50):
        self.siguienteID = 0
        self.objetos = OrderedDict()
        self.desaparecidos = OrderedDict()
        self.maxDesaparecidos = maxDesaparecidos
        self.maxDistancia = maxDistancia

    def registrar(self, centroide):
        self.objetos[self.siguienteID] = centroide
        self.desaparecidos[self.siguienteID] = 0
        self.siguienteID += 1

    def eliminar(self, objectID):
        del self.objetos[objectID]
        del self.desaparecidos[objectID]

    def actualizar(self, rects):
        # Si no hay rectángulos detectados, aumentar contador de desaparición
        if len(rects) == 0:
            for objectID in list(self.desaparecidos.keys()):
                self.desaparecidos[objectID] += 1
                if self.desaparecidos[objectID] > self.maxDesaparecidos:
                    self.eliminar(objectID)
            return self.objetos

        centros_entrada = np.zeros((len(rects), 2), dtype="int")

        for (i, (startX, startY, endX, endY)) in enumerate(rects):
            cX = int((startX + endX) / 2.0)
            cY = int((startY + endY) / 2.0)
            centros_entrada[i] = (cX, cY)

        if len(self.objetos) == 0:
            for i in range(0, len(centros_entrada)):
                self.registrar(centros_entrada[i])
        else:
            ids = list(self.objetos.keys())
            centros = list(self.objetos.values())

            D = np.linalg.norm(np.array(centros)[:, np.newaxis] - centros_entrada, axis=2)

            filas = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[filas]

            usadasFilas = set()
            usadasCols = set()

            for (fila, col) in zip(filas, cols):
                if fila in usadasFilas or col in usadasCols:
                    continue
                if D[fila, col] > self.maxDistancia:
                    continue
                objectID = ids[fila]
                self.objetos[objectID] = centros_entrada[col]
                self.desaparecidos[objectID] = 0
                usadasFilas.add(fila)
                usadasCols.add(col)

            filasNoUsadas = set(range(0, D.shape[0])).difference(usadasFilas)
            colsNoUsadas = set(range(0, D.shape[1])).difference(usadasCols)

            if D.shape[0] >= D.shape[1]:
                for fila in filasNoUsadas:
                    objectID = ids[fila]
                    self.desaparecidos[objectID] += 1
                    if self.desaparecidos[objectID] > self.maxDesaparecidos:
                        self.eliminar(objectID)
            else:
                for col in colsNoUsadas:
                    self.registrar(centros_entrada[col])

        return self.objetos


def redimensionar(frame, ancho=None):
    if ancho is None:
        return frame
    (h, w) = frame.shape[:2]
    r = ancho / float(w)
    dim = (ancho, int(h * r))
    return cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)


def ejecutar(ruta_video=None, min_area=500, ancho=700, mostrar=True):
    """Ejecuta el contador sobre un video o webcam.

    Parámetros:
    - ruta_video: ruta al archivo de video o None para webcam
    - min_area: área mínima para considerar un contorno
    - ancho: ancho de redimensionamiento para procesado
    - mostrar: si True abre ventana con resultado
    """
    fuente = 0 if ruta_video is None else ruta_video

    cap = cv2.VideoCapture(fuente)
    if not cap.isOpened():
        print("Error: no se pudo abrir la fuente de video.")
        return

    sustractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
    rastreador = RastreadorCentroides(maxDesaparecidos=40, maxDistancia=60)
    objetos_rastreables = {}

    total_suben = 0
    total_bajan = 0

    W = None
    H = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = redimensionar(frame, ancho=ancho)

        if W is None or H is None:
            (H, W) = frame.shape[:2]

        mascara = sustractor.apply(frame)
        _, umbral = cv2.threshold(mascara, 244, 255, cv2.THRESH_BINARY)
        umbral = cv2.erode(umbral, None, iterations=2)
        umbral = cv2.dilate(umbral, None, iterations=2)

        contornos, _ = cv2.findContours(umbral.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        rects = []
        for c in contornos:
            if cv2.contourArea(c) < min_area:
                continue
            (x, y, w, h) = cv2.boundingRect(c)
            rects.append((x, y, x + w, y + h))
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        objetos = rastreador.actualizar(rects)

        linea = H // 2
        cv2.line(frame, (0, linea), (W, linea), (0, 0, 255), 2)

        for (objectID, centroide) in objetos.items():
            historial = objetos_rastreables.get(objectID, None)
            if historial is None:
                objetos_rastreables[objectID] = [centroide]
                historial = objetos_rastreables[objectID]
            else:
                historial.append(centroide)

            y = [c[1] for c in historial]

            if len(y) >= 2:
                if y[-2] < linea and y[-1] >= linea:
                    total_bajan += 1
                elif y[-2] > linea and y[-1] <= linea:
                    total_suben += 1

            texto_id = f"ID {objectID}"
            cv2.putText(frame, texto_id, (centroide[0] - 10, centroide[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 2)
            cv2.circle(frame, (centroide[0], centroide[1]), 4, (255, 255, 255), -1)

        info = [("Suben", total_suben), ("Bajan", total_bajan)]
        for (i, (k, v)) in enumerate(info):
            texto = f"{k}: {v}"
            cv2.putText(frame, texto, (10, H - ((i * 20) + 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        if mostrar:
            cv2.imshow("Conteo", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Contador simple de vehículos")
    ap.add_argument("--video", help="ruta al archivo de video (opcional)")
    ap.add_argument("--min-area", type=int, default=500, help="área mínima del contorno")
    ap.add_argument("--width", type=int, default=700, help="ancho de procesamiento")
    ap.add_argument("--show", action="store_true", help="mostrar ventana con resultado")
    args = ap.parse_args()

    ejecutar(ruta_video=args.video, min_area=args.min_area, ancho=args.width, mostrar=args.show)


# Video local dentro de la carpeta del proyecto, independientemente del cwd.
directorio_proyecto = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(directorio_proyecto, "WhatsApp Video 2026-09-27 at 12.59.08.mp4")

if not os.path.exists(video_path):
    print(f"Error: no se encontró el archivo de video: {video_path}")
else:
    ejecutar(ruta_video=video_path, mostrar=True)
