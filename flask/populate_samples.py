import sqlite3
from datetime import datetime

conn = sqlite3.connect("presupuestos.db")
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

print("Poblando base de datos con datos de muestra...")

# 1. Categorías
categorias = [("Celulares",), ("Laptops",)]
for cat in categorias:
    try:
        cur.execute("INSERT OR IGNORE INTO categoria (nombre, activo) VALUES (?, 1)", cat)
    except Exception as e:
        print("Error categoría:", e)

# Obtener IDs de categorías
cur.execute("SELECT id, nombre FROM categoria WHERE activo = 1")
cats_map = {row[1]: row[0] for row in cur.fetchall()}

# 2. Productos
productos = [
    ("Samsung Z Flip", cats_map.get("Celulares")),
    ("iPhone 14 Pro", cats_map.get("Celulares")),
    ("MacBook Air M2", cats_map.get("Laptops")),
]
for prod in productos:
    cur.execute("SELECT id FROM producto WHERE nombre = ?", (prod[0],))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO producto (nombre, categoria_id, activo) VALUES (?, ?, 1)", prod)

# Obtener IDs de productos
cur.execute("SELECT id, nombre FROM producto WHERE activo = 1")
prods_map = {row[1]: row[0] for row in cur.fetchall()}

# 3. Piezas
piezas = [
    ("Módulo (Samsung Z Flip)", prods_map.get("Samsung Z Flip"), 20000.0),
    ("Batería (Samsung Z Flip)", prods_map.get("Samsung Z Flip"), 8000.0),
    ("Módulo (iPhone 14 Pro)", prods_map.get("iPhone 14 Pro"), 35000.0),
    ("Batería (iPhone 14 Pro)", prods_map.get("iPhone 14 Pro"), 12000.0),
    ("Pantalla Retina (MacBook Air M2)", prods_map.get("MacBook Air M2"), 75000.0),
    ("Batería (MacBook Air M2)", prods_map.get("MacBook Air M2"), 22000.0),
]

now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for pz_name, prod_id, costo in piezas:
    if not prod_id:
        continue
    cur.execute("SELECT id FROM pieza WHERE nombre = ? AND producto_id = ?", (pz_name, prod_id))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO pieza (nombre, producto_id, activo) VALUES (?, ?, 1)", (pz_name, prod_id))
        pz_id = cur.lastrowid
        cur.execute("INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)", (pz_id, costo, now_str))
    else:
        pz_id = row[0]
        cur.execute("SELECT id FROM costo_pieza WHERE pieza_id = ? AND es_actual = 1", (pz_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)", (pz_id, costo, now_str))

# Obtener IDs de piezas
cur.execute("SELECT id, nombre FROM pieza WHERE activo = 1")
piezas_map = {row[1]: row[0] for row in cur.fetchall()}

# 4. Tipos de Reparación
tipos_reparacion = [
    ("Cambio Módulo",),
    ("Cambio de Batería",),
    ("Limpieza interna",),
]
for tr in tipos_reparacion:
    cur.execute("INSERT OR IGNORE INTO tipo_reparacion (nombre, activo) VALUES (?, 1)", tr)

# Obtener IDs de tipos de reparación
cur.execute("SELECT id, nombre FROM tipo_reparacion WHERE activo = 1")
tr_map = {row[1]: row[0] for row in cur.fetchall()}

# 5. Precios de Reparación
precios = [
    (tr_map.get("Cambio Módulo"), prods_map.get("Samsung Z Flip"), 15000.0),
    (tr_map.get("Cambio de Batería"), prods_map.get("Samsung Z Flip"), 5000.0),
    (tr_map.get("Limpieza interna"), prods_map.get("Samsung Z Flip"), 3000.0),
    
    (tr_map.get("Cambio Módulo"), prods_map.get("iPhone 14 Pro"), 25000.0),
    (tr_map.get("Cambio de Batería"), prods_map.get("iPhone 14 Pro"), 8000.0),
    (tr_map.get("Limpieza interna"), prods_map.get("iPhone 14 Pro"), 4000.0),
    
    (tr_map.get("Cambio Módulo"), prods_map.get("MacBook Air M2"), 40000.0),
    (tr_map.get("Cambio de Batería"), prods_map.get("MacBook Air M2"), 15000.0),
    (tr_map.get("Limpieza interna"), prods_map.get("MacBook Air M2"), 6000.0),
]

for tr_id, prod_id, precio in precios:
    if not tr_id or not prod_id:
        continue
    cur.execute("SELECT id FROM precio_reparacion WHERE tipo_reparacion_id = ? AND producto_id = ? AND es_actual = 1", (tr_id, prod_id))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO precio_reparacion (tipo_reparacion_id, producto_id, precio, fecha_desde, es_actual) VALUES (?, ?, ?, ?, 1)", (tr_id, prod_id, precio, now_str))

# 6. Asociaciones de Piezas a Reparaciones (tipo_reparacion_pieza)
asociaciones = [
    ("Cambio Módulo", "Módulo (Samsung Z Flip)"),
    ("Cambio de Batería", "Batería (Samsung Z Flip)"),
    ("Cambio Módulo", "Módulo (iPhone 14 Pro)"),
    ("Cambio de Batería", "Batería (iPhone 14 Pro)"),
    ("Cambio Módulo", "Pantalla Retina (MacBook Air M2)"),
    ("Cambio de Batería", "Batería (MacBook Air M2)"),
]

for tr_name, pz_name in asociaciones:
    tr_id = tr_map.get(tr_name)
    pz_id = piezas_map.get(pz_name)
    if tr_id and pz_id:
        try:
            cur.execute("INSERT OR IGNORE INTO tipo_reparacion_pieza (tipo_reparacion_id, pieza_id) VALUES (?, ?)", (tr_id, pz_id))
        except Exception as e:
            print("Error asociación:", e)

conn.commit()
conn.close()
print("Datos de muestra creados con éxito!")
