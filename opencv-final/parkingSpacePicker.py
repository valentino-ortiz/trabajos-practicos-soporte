import argparse
import cv2

from autodetectar import candidatas
from common import cargar_celdas, cargar_preset, guardar_celdas


def main():
    parser = argparse.ArgumentParser(description="Selector de celdas de estacionamiento")
    parser.add_argument("--preset", type=int, default=1, help="Número de preset (ver config.json)")
    parser.add_argument("--imagen", help="Ruta a la imagen de fondo")
    parser.add_argument("--celdas", help="Archivo JSON donde guardar las celdas")
    parser.add_argument("--ancho", type=int, help="Ancho inicial de la celda")
    parser.add_argument("--alto", type=int, help="Alto inicial de la celda")
    args = parser.parse_args()

    cfg = cargar_preset(args.preset)
    img_file = args.imagen or cfg["imagen"]
    pos_file = args.celdas or cfg["celdas"]
    rectW = args.ancho or cfg["ancho"]
    rectH = args.alto or cfg["alto"]
    formato_individual = True

    # Tamaño actual del cursor (se puede ajustar con teclas)
    curW = rectW
    curH = rectH
    STEP_SIZE = 2  # Cuántos píxeles cambia cada vez que ajustas

    posList = [tuple(c) for c in cargar_celdas(pos_file)]
    candList = []  # candidatas de autodetección pendientes de aprobar (no se guardan hasta 'y')

    # Variables para Zoom y Pan
    zoom = 1.0
    view_x = 0
    view_y = 0
    pan_step = 50

    # Posición actual del mouse (para preview del rectángulo)
    mouse_x, mouse_y = 0, 0

    def mouseClick(events, x, y, flags, params):
        nonlocal zoom, view_x, view_y, posList, curW, curH, mouse_x, mouse_y

        # Convertir coordenadas de la vista actual a coordenadas originales de la imagen
        orig_x = int(view_x + x)
        orig_y = int(view_y + y)

        # Actualizar posición del mouse para preview
        mouse_x = orig_x
        mouse_y = orig_y

        if events == cv2.EVENT_LBUTTONDOWN:
            if formato_individual:
                posList.append((orig_x, orig_y, curW, curH))
            else:
                posList.append((orig_x, orig_y))

        if events == cv2.EVENT_RBUTTONDOWN:
            for i, (x1, y1, pw, ph, _) in enumerate(candList):  # primero se rechazan candidatas
                if x1 < orig_x < x1 + pw and y1 < orig_y < y1 + ph:
                    candList.pop(i)
                    return
            for i, pos in enumerate(posList):
                if formato_individual and len(pos) == 4:
                    x1, y1, pw, ph = pos
                else:
                    x1, y1 = pos[0], pos[1]
                    pw, ph = rectW, rectH
                if x1 < orig_x < x1 + pw and y1 < orig_y < y1 + ph:
                    posList.pop(i)
                    break

        guardar_celdas(pos_file, posList)

    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Image", 1280, 720)
    cv2.setMouseCallback("Image", mouseClick)

    base_img = cv2.imread(img_file)
    if base_img is None:
        print(f"No se pudo cargar la imagen: {img_file}")
        return

    h, w = base_img.shape[:2]

    print("\n--- CONTROLES ---")
    print("Click Izquierdo: Agregar celda (con el tamaño actual)")
    print("Tecla 'z': Borrar / Deshacer última celda agregada")
    print("Click Derecho: Borrar celda bajo el cursor")
    if formato_individual:
        print("Flechas ↑/↓ (o r/f): Ajustar ALTO del cursor (+/- 2px)")
        print("Flechas ←/→ (o v/c): Ajustar ANCHO del cursor (+/- 2px)")
    print("Teclas '+' o '=': Zoom In (Acercar)")
    print("Tecla '-': Zoom Out (Alejar)")
    print("Teclas W, A, S, D: Moverse por la imagen (Pan)")
    print("Tecla 'g': Autodetectar candidatas (magenta) a partir de las celdas marcadas")
    print("   Click Derecho sobre una candidata: rechazarla")
    print("   Tecla 'y': aceptar todas las candidatas restantes / 'n': descartarlas")
    print("Tecla 'q': Salir\n")

    while True:
        img = base_img.copy()

        # Dibujar las celdas existentes
        for pos in posList:
            if formato_individual and len(pos) == 4:
                px, py, pw, ph = pos
            else:
                px, py = pos[0], pos[1]
                pw, ph = rectW, rectH
            cv2.rectangle(img, (px, py), (px + pw, py + ph), (0, 0, 255), 2)
        for px, py, pw, ph, _ in candList:
            cv2.rectangle(img, (px, py), (px + pw, py + ph), (255, 0, 255), 2)
        if candList:
            cv2.rectangle(img, (5, 35), (520, 60), (0, 0, 0), -1)
            cv2.putText(img, f'{len(candList)} candidatas: click der. rechaza, y acepta, n descarta', (10, 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        # Dibujar preview del cursor actual (rectángulo verde semi-transparente)
        if formato_individual:
            preview_x1 = mouse_x
            preview_y1 = mouse_y
            preview_x2 = mouse_x + curW
            preview_y2 = mouse_y + curH
            cv2.rectangle(img, (preview_x1, preview_y1), (preview_x2, preview_y2), (0, 255, 0), 1)

            # Mostrar tamaño actual del cursor en la esquina
            cv2.rectangle(img, (5, 5), (200, 30), (0, 0, 0), -1)
            cv2.putText(img, f'Cursor: {curW}x{curH}', (10, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Calcular el tamaño de la vista según el zoom
        view_w = int(w / zoom)
        view_h = int(h / zoom)

        # Limitar los bordes para no salir de la imagen
        view_x = max(0, min(view_x, w - view_w))
        view_y = max(0, min(view_y, h - view_h))

        # Recortar la región que se está visualizando
        img_display = img[view_y : view_y + view_h, view_x : view_x + view_w]

        cv2.imshow("Image", img_display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('g'):
            candList = candidatas(posList, base_img)
            print(f"{len(candList)} candidatas propuestas")
        elif key == ord('y') and candList:
            posList += [tuple(int(v) for v in c[:4]) for c in candList]
            candList = []
            guardar_celdas(pos_file, posList)
        elif key == ord('n'):
            candList = []
        elif key == ord('z') or key == ord('Z'):
            if posList:
                posList.pop()
                guardar_celdas(pos_file, posList)
        # Ajustar tamaño del cursor (solo en formato individual)
        elif formato_individual and key == ord('r'):  # ↑ = Aumentar alto
            curH += STEP_SIZE
        elif formato_individual and key == ord('f'):  # ↓ = Disminuir alto
            curH = max(STEP_SIZE, curH - STEP_SIZE)
        elif formato_individual and key == ord('c'):  # → = Aumentar ancho
            curW += STEP_SIZE
        elif formato_individual and key == ord('v'):  # ← = Disminuir ancho
            curW = max(STEP_SIZE, curW - STEP_SIZE)
        # También soportar teclas de flechas reales
        elif formato_individual and key == 82:  # Flecha arriba
            curH += STEP_SIZE
        elif formato_individual and key == 84:  # Flecha abajo
            curH = max(STEP_SIZE, curH - STEP_SIZE)
        elif formato_individual and key == 83:  # Flecha derecha
            curW += STEP_SIZE
        elif formato_individual and key == 81:  # Flecha izquierda
            curW = max(STEP_SIZE, curW - STEP_SIZE)
        elif key == ord('+') or key == ord('='):
            zoom = min(zoom * 1.5, 10.0)
        elif key == ord('-'):
            zoom = max(zoom / 1.5, 1.0)
        elif key == ord('w'):
            view_y -= int(pan_step / zoom)
        elif key == ord('s'):
            view_y += int(pan_step / zoom)
        elif key == ord('a'):
            view_x -= int(pan_step / zoom)
        elif key == ord('d'):
            view_x += int(pan_step / zoom)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()