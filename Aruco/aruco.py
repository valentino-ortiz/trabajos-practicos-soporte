import cv2
import cv2.aruco as aruco
import numpy as np
import os

camera_matrix = np.array([
    [800, 0, 320],
    [0, 800, 240],
    [0, 0, 1]
], dtype=np.float32)

dist_coeffs = np.zeros((5, 1), dtype=np.float32)

marker_length = 0.05
half_l = marker_length / 2

marker_points = np.array([
    [-half_l,  half_l, 0],
    [ half_l,  half_l, 0],
    [ half_l, -half_l, 0],
    [-half_l, -half_l, 0]
], dtype=np.float32)

# Leer diccionario desde la configuración o usar predeterminado
def get_dictionary_id(dict_name):
    dicts = {
        "DICT_4X4_50": aruco.DICT_4X4_50,
        "DICT_4X4_100": aruco.DICT_4X4_100,
        "DICT_4X4_250": aruco.DICT_4X4_250,
        "DICT_4X4_1000": aruco.DICT_4X4_1000,
        "DICT_5X5_50": aruco.DICT_5X5_50,
        "DICT_5X5_100": aruco.DICT_5X5_100,
        "DICT_5X5_250": aruco.DICT_5X5_250,
        "DICT_5X5_1000": aruco.DICT_5X5_1000,
        "DICT_6X6_50": aruco.DICT_6X6_50,
        "DICT_6X6_100": aruco.DICT_6X6_100,
        "DICT_6X6_250": aruco.DICT_6X6_250,
        "DICT_6X6_1000": aruco.DICT_6X6_1000,
        "DICT_7X7_50": aruco.DICT_7X7_50,
        "DICT_7X7_100": aruco.DICT_7X7_100,
        "DICT_7X7_250": aruco.DICT_7X7_250,
        "DICT_7X7_1000": aruco.DICT_7X7_1000,
        "DICT_ARUCO_ORIGINAL": aruco.DICT_ARUCO_ORIGINAL,
    }
    return dicts.get(dict_name, aruco.DICT_4X4_50)

def generar_marcador_si_no_existe():
    """Genera el marcador y la configuración si no existen."""
    marker_file = "aruco_0.png"
    config_file = "config_diccionario.txt"
    
    # Si ya existe todo, no hacer nada
    if os.path.exists(marker_file) and os.path.exists(config_file):
        print(f"✅ Marcador y configuración ya existen")
        return
    
    print("=" * 60)
    print("  CONFIGURACIÓN AUTOMÁTICA DEL MARCADOR ARUCO")
    print("=" * 60)
    print()
    
    # Usar el diccionario más simple y compatible
    try:
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        dict_name = "DICT_4X4_50"
        print(f"Usando diccionario: {dict_name}")
    except (AttributeError, Exception):
        print("DICT_4X4_50 no disponible, probando con DICT_ARUCO_ORIGINAL...")
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_ARUCO_ORIGINAL)
        dict_name = "DICT_ARUCO_ORIGINAL"
        print(f"Usando diccionario: {dict_name}")
    
    # ID simple
    marker_id = 42
    
    # Generar marcador - tamaño razonable
    marker_size = 400
    border_bits = 1
    
    print(f"Generando marcador ID {marker_id}, tamaño {marker_size}px...")
    marker_img = np.zeros((marker_size, marker_size), dtype=np.uint8)
    marker_img = aruco.generateImageMarker(dictionary, marker_id, marker_size, marker_img, border_bits)
    
    # Añadir borde blanco MUY ancho para asegurar detección
    border_size = 100
    marker_final = cv2.copyMakeBorder(marker_img, border_size, border_size, border_size, border_size, 
                                      cv2.BORDER_CONSTANT, value=255)
    
    # Guardar
    cv2.imwrite(marker_file, marker_final)
    print(f"✅ Marcador guardado como: {marker_file}")
    
    # Verificar detección con parámetros flexibles
    print()
    print("Verificando detección...")
    
    parameters = aruco.DetectorParameters()
    parameters.adaptiveThreshConstant = 7
    parameters.minMarkerPerimeterRate = 0.02
    parameters.maxMarkerPerimeterRate = 5.0
    parameters.polygonalApproxAccuracyRate = 0.05
    parameters.errorCorrectionRate = 0.6
    
    detector = aruco.ArucoDetector(dictionary, parameters)
    
    gray = marker_final if len(marker_final.shape) == 2 else cv2.cvtColor(marker_final, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)
    
    if ids is not None:
        print("✅ ¡DETECCIÓN EXITOSA!")
        detected_id = np.asarray(ids).reshape(-1)[0]
        print(f"   ID detectado: {detected_id}")
        
        # Guardar configuración
        with open(config_file, "w") as f:
            f.write(dict_name)
        print(f"   Configuración guardada en: {config_file}")
        
        print()
        print("=" * 60)
        print("  ¡LISTO! Mostrando el marcador...")
        print("=" * 60)
        print()
        print("💡 Muestra 'aruco_0.png' frente a la cámara para ver el cubo 3D")
        print("   Presiona cualquier tecla para continuar...")
        
        # Mostrar el marcador para que el usuario lo vea
        cv2.imshow("Marcador ArUco - Presiona cualquier tecla", marker_final)
        cv2.waitKey(0)
        cv2.destroyWindow("Marcador ArUco - Presiona cualquier tecla")
    else:
        print("⚠️ No se pudo verificar la detección, pero se generó el marcador de todas formas")
        print(f"   Candidatos rechazados: {len(rejected) if rejected else 0}")
        
        # Guardar configuración de todas formas
        with open(config_file, "w") as f:
            f.write(dict_name)

# Generar marcador y configuración si es necesario
generar_marcador_si_no_existe()

# Cargar configuración
config_file = "config_diccionario.txt"
if os.path.exists(config_file):
    with open(config_file, "r") as f:
        dict_name = f.read().strip()
    print(f"Usando diccionario: {dict_name}")
else:
    dict_name = "DICT_4X4_50"
    print(f"Usando diccionario predeterminado: {dict_name}")

dictionary = aruco.getPredefinedDictionary(get_dictionary_id(dict_name))

# Parámetros de detección flexibles para mejor detección
parameters = aruco.DetectorParameters()
parameters.adaptiveThreshConstant = 7
parameters.minMarkerPerimeterRate = 0.02
parameters.maxMarkerPerimeterRate = 5.0
parameters.polygonalApproxAccuracyRate = 0.05
parameters.errorCorrectionRate = 0.6

detector = aruco.ArucoDetector(
    dictionary,
    parameters
)

cap = cv2.VideoCapture(0)

while True:

    ret, frame = cap.read()

    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    corners, ids, _ = detector.detectMarkers(gray)

    if ids is not None:

        for marker in corners:

            success, rvec, tvec = cv2.solvePnP(
                marker_points,
                marker[0],
                camera_matrix,
                dist_coeffs
            )

            if not success:
                continue

            cube_length = 0.05
            hl = cube_length / 2

            cube_points_3d = np.array([
                [-hl, -hl, 0],
                [ hl, -hl, 0],
                [ hl,  hl, 0],
                [-hl,  hl, 0],
                [-hl, -hl, cube_length],
                [ hl, -hl, cube_length],
                [ hl,  hl, cube_length],
                [-hl,  hl, cube_length],
            ], dtype=np.float32)

            cube_points_2d, _ = cv2.projectPoints(
                cube_points_3d,
                rvec,
                tvec,
                camera_matrix,
                dist_coeffs
            )

            cube_points_2d = np.int32(cube_points_2d.reshape(-1, 2))

            cv2.polylines(frame, [cube_points_2d[:4]], True, (0, 255, 0), 2)
            cv2.polylines(frame, [cube_points_2d[4:]], True, (0, 255, 0), 2)
            for i in range(4):
                cv2.line(frame, tuple(cube_points_2d[i]), tuple(cube_points_2d[i + 4]), (0, 0, 255), 2)

            cv2.drawFrameAxes(
                frame,
                camera_matrix,
                dist_coeffs,
                rvec,
                tvec,
                0.03
            )

    cv2.imshow(
        "Sistema Solar AR",
        frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == 27:
        break

cap.release()
cv2.destroyAllWindows()