import argparse
import cv2
import numpy as np
import pickle

PRESETS = {
    1: {
        "video": "carPark.mp4",
        "posiciones": "carParkPos",
        "ancho": 107,
        "alto": 48,
        "threshold": 900,
        "stabilize": False,  # carPark.mp4 no necesita estabilización
        "thresh_block_size": 25,
        "thresh_c": 16
    },
    2: {
        "video": "video2.mkv",
        "posiciones": "posiciones_nuevo",
        "ancho": 40,  # Cambiar según el tamaño deseado para el video 2
        "alto": 23,  # Cambiar según el tamaño deseado para el video 2
        "threshold": 160,  # Umbral proporcional para celdas de 40x23
        "stabilize": True,   # Activar compensación de movimiento de cámara
        "thresh_block_size": 41, # Bloque más grande ayuda a ignorar sombras suaves
        "thresh_c": 20           # Constante mayor ayuda a requerir bordes más marcados
    },
    3: {
        "video": "video-park.mp4",
        "posiciones": "posiciones_park",
        "ancho": 40,  # Valores aproximados iniciales
        "alto": 20,
        "threshold": 150,
        "stabilize": False, # Desactivado por defecto, activalo si el video tiene movimiento
        "thresh_block_size": 25,
        "thresh_c": 16
    }
}


def calcular_offset_frame(prev_gray, cur_gray):
    """Calcula el desplazamiento global entre dos frames consecutivos
    usando Lucas-Kanade optical flow sobre features Shi-Tomasi.
    Devuelve (dx, dy) como mediana del movimiento detectado."""

    # Detectar esquinas (features) en el frame anterior
    feature_params = dict(
        maxCorners=200,
        qualityLevel=0.01,
        minDistance=30,
        blockSize=7
    )
    pts_prev = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)

    if pts_prev is None or len(pts_prev) < 10:
        return 0.0, 0.0

    # Trackear las features al frame actual con Lucas-Kanade
    lk_params = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
    )
    pts_cur, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, pts_prev, None, **lk_params)

    # Filtrar solo los puntos que se trackearon exitosamente
    good_prev = pts_prev[status.flatten() == 1]
    good_cur = pts_cur[status.flatten() == 1]

    if len(good_prev) < 5:
        return 0.0, 0.0

    # Calcular desplazamiento de cada punto
    deltas = good_cur - good_prev  # shape: (N, 1, 2) o (N, 2)
    deltas = deltas.reshape(-1, 2)

    # Usar mediana (robusto contra outliers = autos moviéndose)
    dx = np.median(deltas[:, 0])
    dy = np.median(deltas[:, 1])

    return dx, dy


def main():
    parser = argparse.ArgumentParser(description="Detector de celdas de estacionamiento")
    parser.add_argument("--preset", type=int, default=1, help="Número de preset a utilizar (1, 2, etc.)")
    parser.add_argument("--video", help="Ruta al video a procesar")
    parser.add_argument("--posiciones", help="Archivo con las posiciones de las celdas")
    parser.add_argument("--ancho", type=int, help="Ancho del rectángulo de la celda")
    parser.add_argument("--alto", type=int, help="Alto del rectángulo de la celda")
    parser.add_argument("--threshold", type=int, help="Umbral de píxeles para considerar celda libre")
    parser.add_argument("--no-stabilize", action="store_true", help="Desactivar compensación de movimiento de cámara")
    args = parser.parse_args()

    # Cargar valores del preset seleccionado (o por defecto 1)
    preset_config = PRESETS.get(args.preset, PRESETS[1])

    video_file = args.video if args.video is not None else preset_config["video"]
    pos_file = args.posiciones if args.posiciones is not None else preset_config["posiciones"]
    rectW = args.ancho if args.ancho is not None else preset_config["ancho"]
    rectH = args.alto if args.alto is not None else preset_config["alto"]
    stabilize = (not args.no_stabilize) and preset_config.get("stabilize", False)

    # Si no se especifica umbral, se calcula proporcionalmente a la superficie respecto al Preset 1 (900 px para 107x48)
    area_ratio = (rectW * rectH) / (107 * 48)
    default_threshold = int(900 * area_ratio)

    if args.threshold is not None:
        threshold_val = args.threshold
    elif "threshold" in preset_config:
        threshold_val = preset_config["threshold"]
    else:
        threshold_val = default_threshold

    # Parámetros para reducir sombras (adaptiveThreshold)
    thresh_block_size = preset_config.get("thresh_block_size", 25)
    thresh_c = preset_config.get("thresh_c", 16)

    cap = cv2.VideoCapture(video_file)

    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {video_file}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_delay = max(1, round(1000 / video_fps)) if video_fps > 0 else 33

    with open(pos_file, 'rb') as f:
        posList = pickle.load(f)

    # Variables para estabilización (offset acumulado frame-a-frame)
    prev_gray = None
    acum_x, acum_y = 0.0, 0.0  # Offset acumulado en float para precisión
    offset_x, offset_y = 0, 0  # Offset redondeado a int para dibujo

    # Variables para evitar titilación (suavizado exponencial del conteo de píxeles)
    smoothed_counts = {i: 0 for i in range(len(posList))}
    alpha = 0.15  # Factor de suavizado (menor = más estable pero tarda un par de frames más en cambiar)

    def check(imgPro, img, off_x, off_y):
        spaceCount = 0
        for i, pos in enumerate(posList):
            # Soportar ambos formatos: (x, y) y (x, y, w, h)
            if len(pos) == 4:
                px, py, pw, ph = pos
            else:
                px, py = pos[0], pos[1]
                pw, ph = rectW, rectH

            # Aplicar offset de compensación de cámara
            x = px + off_x
            y = py + off_y

            # Verificar que la celda no se salga de la imagen
            if y < 0 or x < 0 or y + ph > imgPro.shape[0] or x + pw > imgPro.shape[1]:
                continue

            crop = imgPro[y: y+ph, x: x+pw]
            count = cv2.countNonZero(crop)

            # Inicializar el contador suave rápido en el primer frame si estaba en 0
            if smoothed_counts[i] == 0:
                smoothed_counts[i] = count
            else:
                # Aplicar suavizado exponencial (Exponential Moving Average)
                smoothed_counts[i] = (alpha * count) + ((1 - alpha) * smoothed_counts[i])
            
            smoothed_count = smoothed_counts[i]

            # Umbral proporcional al área de esta celda específica
            cell_area = pw * ph
            cell_threshold = int(threshold_val * cell_area / (rectW * rectH)) if (rectW * rectH) > 0 else threshold_val

            if smoothed_count < cell_threshold:
                spaceCount += 1
                color = (0, 255, 0)
                thick = 5
            else:
                color = (0, 0, 255)
                thick = 2

            cv2.rectangle(img, (x, y), (x + pw, y + ph), color, thick)

        # Panel de información
        cv2.rectangle(img, (45, 30), (420, 75), (180, 0, 180), -1)
        info_text = f'Libres: {spaceCount}/{len(posList)} (T:{threshold_val})'
        if stabilize:
            info_text += f' Off:({off_x},{off_y})'
        cv2.putText(img, info_text, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Image", 1280, 720)

    while True:
        ok, img = cap.read()
        if not ok or img is None:
            break

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Estabilización frame-a-frame con acumulación
        if stabilize:
            if prev_gray is not None:
                dx, dy = calcular_offset_frame(prev_gray, gray)
                acum_x += dx
                acum_y += dy
                offset_x = int(round(acum_x))
                offset_y = int(round(acum_y))
            prev_gray = gray.copy()

        blur = cv2.GaussianBlur(gray, (3, 3), 1)
        # Usar parámetros configurables para el umbral adaptativo (ayuda a mitigar sombras)
        trhe = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, thresh_block_size, thresh_c)
        blur_trhe = cv2.medianBlur(trhe, 5)
        
        # Filtro morfológico (Apertura) para eliminar ruido fino como grietas o manchas del suelo
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(blur_trhe, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # Dilatar lo que quede para consolidar la forma de los autos
        dillate = cv2.dilate(opening, kernel, iterations=1)
        check(dillate, img, offset_x, offset_y)
        cv2.imshow("Image", img)
        if cv2.waitKey(frame_delay) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()