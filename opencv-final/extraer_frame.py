import argparse
from pathlib import Path

import cv2
import numpy as np


VIDEO = Path(__file__).with_name(
    "Busy Parking Lot - Aerial Time-Lapse [yojapmOkIfg].mkv"
)


def es_frame_negro(frame: np.ndarray, umbral_brillo: float = 65.0) -> bool:
    """
    Determina si un frame es negro o demasiado oscuro (por ejemplo durante un fade-in inicial).
    Calcula el brillo promedio en la escala de grises.
    """
    if frame is None:
        return True
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brillo_promedio = float(np.mean(gray))
    return brillo_promedio < umbral_brillo


def ajustar_brillo_contraste(
    frame: np.ndarray, alpha: float = 1.0, beta: float = 0.0, gamma: float = 1.0
) -> np.ndarray:
    """
    Aplica ajustes opcionales de brillo/contraste y corrección gamma al frame.
    - alpha: factor de contraste (1.0 = normal)
    - beta: incremento de brillo (0.0 = normal)
    - gamma: corrección gamma (< 1.0 aclara sombras, > 1.0 oscurece)
    """
    out = frame.copy()
    if alpha != 1.0 or beta != 0.0:
        out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)
    if gamma != 1.0 and gamma > 0:
        inv_gamma = 1.0 / gamma
        table = np.array(
            [((i / 255.0) ** inv_gamma) * 255 for i in range(256)]
        ).astype("uint8")
        out = cv2.LUT(out, table)
    return out


def extraer_frame(
    video_path: Path,
    output_path: Path,
    second: float,
    wait_seconds: float,
    umbral_brillo: float = 65.0,
    alpha: float = 1.0,
    beta: float = 0.0,
    gamma: float = 1.0,
) -> None:
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {video_path}")

    capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
    end_second = second + wait_seconds
    ok, frame_original = capture.read()

    # Avanzar frames si el frame actual es negro o está en medio de la transición fade-in
    while ok and frame_original is not None:
        current_second = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if not es_frame_negro(frame_original, umbral_brillo) or current_second >= end_second:
            break
        ok, frame_original = capture.read()

    capture.release()

    if not ok or frame_original is None:
        raise RuntimeError(f"No se pudo leer un frame válido cerca del segundo {second}")

    # Aplicar ajustes de brillo/contraste si se especificaron
    frame_procesado = ajustar_brillo_contraste(frame_original, alpha, beta, gamma)

    if not cv2.imwrite(str(output_path), frame_procesado):
        raise RuntimeError(f"No se pudo guardar la imagen: {output_path}")

    gray = cv2.cvtColor(frame_original, cv2.COLOR_BGR2GRAY)
    print(f"Frame guardado en: {output_path}")
    print(f"Brillo medio del frame original extraído: {np.mean(gray):.2f}/255")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae un frame de un video con OpenCV")
    parser.add_argument(
        "--video",
        type=Path,
        default=VIDEO,
        help=f"Ruta al archivo de video (por defecto: {VIDEO.name})",
    )
    parser.add_argument(
        "--segundo",
        type=float,
        default=2.0,
        help="Segundo del video que se quiere extraer (por defecto: 2.0 para evitar el fade-in inicial)",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("img.png"),
        help="Archivo de imagen de salida (por defecto: img.png)",
    )
    parser.add_argument(
        "--espera",
        type=float,
        default=30,
        help="Máximo de segundos para esperar un frame no negro (por defecto: 30)",
    )
    parser.add_argument(
        "--umbral-brillo",
        type=float,
        default=65.0,
        help="Umbral mínimo de brillo medio (0-255) para considerar que el frame no es negro/oscuro (por defecto: 65.0)",
    )
    parser.add_argument(
        "--brillo",
        type=float,
        default=0.0,
        help="Ajuste extra de brillo (beta) a sumar a los píxeles (ej: 20)",
    )
    parser.add_argument(
        "--contraste",
        type=float,
        default=1.0,
        help="Factor de contraste (alpha) para multiplicar píxeles (ej: 1.2)",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=1.0,
        help="Factor gamma para ajustar sombras/luces (ej: 0.8 para aclarar)",
    )
    args = parser.parse_args()

    if args.segundo < 0:
        parser.error("--segundo no puede ser negativo")
    if args.espera < 0:
        parser.error("--espera no puede ser negativa")

    extraer_frame(
        video_path=args.video,
        output_path=args.salida,
        second=args.segundo,
        wait_seconds=args.espera,
        umbral_brillo=args.umbral_brillo,
        alpha=args.contraste,
        beta=args.brillo,
        gamma=args.gamma,
    )


if __name__ == "__main__":
    main()