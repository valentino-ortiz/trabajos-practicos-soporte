import json
from pathlib import Path

DIR = Path(__file__).parent


def cargar_preset(n):
    cfg = json.loads((DIR / "config.json").read_text())
    return cfg.get(str(n), cfg["1"])


def cargar_celdas(path):
    """Devuelve lista de [x, y, w, h]; [] si el archivo no existe."""
    p = DIR / path
    return json.loads(p.read_text()) if p.exists() else []


def guardar_celdas(path, celdas):
    (DIR / path).write_text(json.dumps([list(map(int, c)) for c in celdas]))


def guardar_mosaicos(vis, nombre):
    """Guarda la imagen en 4 mitades a tamaño real (gt/NOMBRE_a..d.png) y devuelve las rutas."""
    import cv2
    out = DIR / "gt"
    out.mkdir(exist_ok=True)
    H, W = vis.shape[:2]
    rutas = []
    for k, (r, c) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
        ruta = out / f"{nombre}_{'abcd'[k]}.png"
        cv2.imwrite(str(ruta), vis[r * H // 2:(r + 1) * H // 2, c * W // 2:(c + 1) * W // 2])
        rutas.append(ruta)
    return rutas
