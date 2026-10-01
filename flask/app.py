import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash

# ─────────────────────────────────────────────
# Configuración general
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "presupuestos_secret_key_2024"

DB_PATH = "presupuestos.db"

ESTADOS_VALIDOS = {"Pendiente", "Aceptado", "Rechazado", "Terminado"}

@app.context_processor
def inject_config_alias():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT clave, valor FROM configuracion WHERE clave IN ('alias_servicios', 'alias_insumos', 'alias_proyectos', 'nombre_negocio')")
        rows = cur.fetchall()
        aliases = {
            'servicios': 'Reparaciones',
            'insumos': 'Piezas',
            'proyectos': 'Productos',
            'negocio': 'Mi Negocio'
        }
        for r in rows:
            if r['clave'] == 'alias_servicios': aliases['servicios'] = r['valor']
            elif r['clave'] == 'alias_insumos': aliases['insumos'] = r['valor']
            elif r['clave'] == 'alias_proyectos': aliases['proyectos'] = r['valor']
            elif r['clave'] == 'nombre_negocio': aliases['negocio'] = r['valor']
        return dict(config_alias=aliases)
    except Exception:
        return dict(config_alias={
            'servicios': 'Reparaciones',
            'insumos': 'Piezas',
            'proyectos': 'Productos',
            'negocio': 'Mi Negocio'
        })
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────
# Utilidades de base de datos
# ─────────────────────────────────────────────

def get_connection():
    """Abre y devuelve una conexión con row_factory configurada."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # permite acceder columnas por nombre
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Verifica la existencia del archivo de BD y crea todas las tablas
    necesarias si no existen todavía (CREATE TABLE IF NOT EXISTS).
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                descripcion TEXT
            );

            CREATE TABLE IF NOT EXISTS categoria (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                activo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS producto (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre       TEXT NOT NULL,
                categoria_id INTEGER NOT NULL,
                activo       INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (categoria_id) REFERENCES categoria(id)
            );

            CREATE TABLE IF NOT EXISTS pieza (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                producto_id INTEGER NOT NULL,
                activo      INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (producto_id) REFERENCES producto(id)
            );

            CREATE TABLE IF NOT EXISTS costo_pieza (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pieza_id    INTEGER NOT NULL,
                costo       REAL    NOT NULL,
                fecha_desde TEXT    NOT NULL,
                es_actual   INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (pieza_id) REFERENCES pieza(id)
            );

            CREATE TABLE IF NOT EXISTS tipo_reparacion (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                activo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS precio_reparacion (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_reparacion_id INTEGER NOT NULL,
                producto_id        INTEGER NOT NULL,
                precio             REAL    NOT NULL,
                fecha_desde        TEXT    NOT NULL,
                es_actual          INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (tipo_reparacion_id) REFERENCES tipo_reparacion(id),
                FOREIGN KEY (producto_id)        REFERENCES producto(id)
            );

            CREATE TABLE IF NOT EXISTS presupuesto (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_nombre   TEXT    NOT NULL,
                cliente_contacto TEXT,
                producto_id      INTEGER NOT NULL,
                urgencia         TEXT    NOT NULL DEFAULT 'Normal',
                total            REAL    NOT NULL,
                estado           TEXT    NOT NULL DEFAULT 'Pendiente',
                fecha_creacion   TEXT    NOT NULL,
                FOREIGN KEY (producto_id) REFERENCES producto(id)
            );

            CREATE TABLE IF NOT EXISTS presupuesto_detalle_pieza (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                presupuesto_id INTEGER NOT NULL,
                pieza_id       INTEGER NOT NULL,
                costo_cobrado  REAL    NOT NULL,
                FOREIGN KEY (presupuesto_id) REFERENCES presupuesto(id),
                FOREIGN KEY (pieza_id)       REFERENCES pieza(id)
            );

            CREATE TABLE IF NOT EXISTS presupuesto_detalle_reparacion (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                presupuesto_id     INTEGER NOT NULL,
                tipo_reparacion_id INTEGER NOT NULL,
                precio_cobrado     REAL    NOT NULL,
                FOREIGN KEY (presupuesto_id)     REFERENCES presupuesto(id),
                FOREIGN KEY (tipo_reparacion_id) REFERENCES tipo_reparacion(id)
            );

            CREATE TABLE IF NOT EXISTS tipo_reparacion_pieza (
                tipo_reparacion_id INTEGER NOT NULL,
                pieza_id INTEGER NOT NULL,
                PRIMARY KEY (tipo_reparacion_id, pieza_id),
                FOREIGN KEY (tipo_reparacion_id) REFERENCES tipo_reparacion(id),
                FOREIGN KEY (pieza_id) REFERENCES pieza(id)
            );
        """)
        conn.commit()

        # Insertar valores por defecto de configuración (solo si no existen)
        defaults = [
            ("margen_ganancia",      "0.30",  "Margen de ganancia global aplicado sobre el subtotal base (ej: 0.30 = 30 %)"),
            ("recargo_Normal",       "0.00",  "Recargo por urgencia Normal (ej: 0.00 = 0 %)"),
            ("recargo_24hs",         "0.20",  "Recargo por urgencia 24hs (ej: 0.20 = 20 %)"),
            ("recargo_Inmediato",    "0.50",  "Recargo por urgencia Inmediato (ej: 0.50 = 50 %)"),
            ("alias_servicios",      "Reparaciones", "Nombre utilizado para los tipos de servicio en la interfaz"),
            ("alias_insumos",        "Piezas", "Nombre utilizado para los repuestos o materiales en la interfaz"),
            ("alias_proyectos",      "Productos", "Nombre utilizado para los proyectos o equipos en la interfaz"),
            ("nombre_negocio",       "Mi Negocio", "Nombre comercial mostrado en el sistema"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO configuracion (clave, valor, descripcion) VALUES (?, ?, ?)",
            defaults,
        )
        conn.commit()

        # ── Migración: agregar columna 'activo' a tablas existentes (idempotente) ──
        migraciones = [
            "ALTER TABLE categoria       ADD COLUMN activo INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE producto        ADD COLUMN activo INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE pieza           ADD COLUMN activo INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE tipo_reparacion ADD COLUMN activo INTEGER NOT NULL DEFAULT 1",
        ]
        for sql in migraciones:
            try:
                cursor.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                # La columna ya existe → se ignora
                pass
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────
# Helpers de cálculo
# ─────────────────────────────────────────────

def _get_config(conn):
    """Lee la configuración de negocio desde la BD y la devuelve como dict."""
    cursor = conn.cursor()
    cursor.execute("SELECT clave, valor FROM configuracion")
    rows = cursor.fetchall()
    cfg = {r["clave"]: r["valor"] for r in rows}
    return {
        "margen_ganancia": float(cfg.get("margen_ganancia", 0.30)),
        "recargos": {
            "Normal":    float(cfg.get("recargo_Normal",    0.00)),
            "24hs":      float(cfg.get("recargo_24hs",      0.20)),
            "Inmediato": float(cfg.get("recargo_Inmediato", 0.50)),
        },
    }


def _calcular_presupuesto(conn, producto_id, pieza_ids, tipo_reparacion_ids, urgencia):
    """
    Núcleo del cálculo. Lee margen y recargos desde la BD.
    Devuelve un dict con el desglose y el total, o lanza ValueError.
    """
    cfg = _get_config(conn)
    recargos = cfg["recargos"]
    margen_ganancia = cfg["margen_ganancia"]

    if urgencia not in recargos:
        raise ValueError(f"Urgencia inválida. Valores permitidos: {list(recargos.keys())}")

    cursor = conn.cursor()

    # --- Verificar que el producto existe y está activo ---
    cursor.execute("SELECT id, nombre FROM producto WHERE id = ? AND activo = 1", (producto_id,))
    producto = cursor.fetchone()
    if not producto:
        raise ValueError(f"Producto con id={producto_id} no encontrado o dado de baja.")

    # --- Costos de piezas ---
    detalle_piezas = []
    subtotal_piezas = 0.0
    for pieza_id in pieza_ids:
        cursor.execute("""
            SELECT p.id, p.nombre, cp.costo
            FROM pieza p
            JOIN costo_pieza cp ON cp.pieza_id = p.id
            WHERE p.id = ? AND p.activo = 1 AND cp.es_actual = 1
        """, (pieza_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(
                f"Pieza con id={pieza_id} no encontrada, dada de baja o sin costo actual registrado."
            )
        detalle_piezas.append({
            "pieza_id": row["id"],
            "nombre":   row["nombre"],
            "costo":    row["costo"],
        })
        subtotal_piezas += row["costo"]

    # --- Precios de reparaciones ---
    detalle_reparaciones = []
    subtotal_reparaciones = 0.0
    for tr_id in tipo_reparacion_ids:
        cursor.execute("""
            SELECT tr.id, tr.nombre, pr.precio
            FROM tipo_reparacion tr
            JOIN precio_reparacion pr
                ON pr.tipo_reparacion_id = tr.id
               AND pr.producto_id = ?
            WHERE tr.id = ? AND tr.activo = 1 AND pr.es_actual = 1
        """, (producto_id, tr_id))
        row = cursor.fetchone()
        if not row:
            raise ValueError(
                f"Tipo de reparación id={tr_id} no encontrado, dado de baja o sin precio para producto id={producto_id}."
            )
        detalle_reparaciones.append({
            "tipo_reparacion_id": row["id"],
            "nombre":             row["nombre"],
            "precio":             row["precio"],
        })
        subtotal_reparaciones += row["precio"]

    # --- Cálculo final ---
    subtotal_base    = subtotal_piezas + subtotal_reparaciones
    margen_importe   = round(subtotal_base * margen_ganancia, 2)
    subtotal_con_mg  = subtotal_base + margen_importe
    recargo_pct      = recargos[urgencia]
    recargo_importe  = round(subtotal_con_mg * recargo_pct, 2)
    total            = round(subtotal_con_mg + recargo_importe, 2)

    return {
        "producto":                  {"id": producto["id"], "nombre": producto["nombre"]},
        "urgencia":                  urgencia,
        "detalle_piezas":            detalle_piezas,
        "subtotal_piezas":           round(subtotal_piezas, 2),
        "detalle_reparaciones":      detalle_reparaciones,
        "subtotal_reparaciones":     round(subtotal_reparaciones, 2),
        "subtotal_base":             round(subtotal_base, 2),
        "margen_ganancia_pct":       margen_ganancia,
        "margen_importe":            margen_importe,
        "urgencia_recargo_pct":      recargo_pct,
        "urgencia_recargo_importe":  recargo_importe,
        "total":                     total,
    }


# ═══════════════════════════════════════════════
# ENDPOINTS – Configuración de Negocio (parámetros)
# ═══════════════════════════════════════════════

@app.route("/api/configuracion", methods=["GET"])
def ver_configuracion():
    """Devuelve todos los parámetros de negocio configurables."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT clave, valor, descripcion FROM configuracion ORDER BY clave")
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/configuracion", methods=["PUT"])
def actualizar_configuracion():
    """
    Actualiza uno o más parámetros de negocio.
    Body JSON: { "margen_ganancia": 0.35, "recargo_24hs": 0.25, ... }
    Claves válidas: margen_ganancia, recargo_Normal, recargo_24hs, recargo_Inmediato
    """
    data = request.get_json(silent=True) or {}
    claves_validas = {"margen_ganancia", "recargo_Normal", "recargo_24hs", "recargo_Inmediato"}

    actualizados = {}
    errores = {}
    for clave, valor in data.items():
        if clave not in claves_validas:
            errores[clave] = f"Clave desconocida. Claves válidas: {sorted(claves_validas)}"
            continue
        try:
            valor_float = float(valor)
            if valor_float < 0:
                raise ValueError
            actualizados[clave] = str(valor_float)
        except (TypeError, ValueError):
            errores[clave] = "El valor debe ser un número no negativo (ej: 0.30 para 30 %)."

    if errores and not actualizados:
        return jsonify({"errores": errores}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for clave, valor in actualizados.items():
            cursor.execute(
                "UPDATE configuracion SET valor = ? WHERE clave = ?",
                (valor, clave),
            )
        conn.commit()
        resultado = {"actualizados": actualizados}
        if errores:
            resultado["errores"] = errores
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ═══════════════════════════════════════════════
# ENDPOINTS – Catálogo
# ═══════════════════════════════════════════════

# ── Categorías ──────────────────────────────────

@app.route("/api/categorias", methods=["GET"])
def listar_categorias():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM categoria WHERE activo = 1 ORDER BY nombre")
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/categorias/<int:categoria_id>", methods=["PUT"])
def actualizar_categoria(categoria_id):
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categoria WHERE id = ? AND activo = 1", (categoria_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Categoría con id={categoria_id} no encontrada o dada de baja."}), 404
        cursor.execute("UPDATE categoria SET nombre = ? WHERE id = ?", (nombre, categoria_id))
        conn.commit()
        return jsonify({"id": categoria_id, "nombre": nombre}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Ya existe una categoría con el nombre '{nombre}'."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/categorias/<int:categoria_id>", methods=["DELETE"])
def desactivar_categoria(categoria_id):
    """Borrado lógico: marca la categoría como inactiva (activo = 0)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, activo FROM categoria WHERE id = ?", (categoria_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"Categoría con id={categoria_id} no encontrada."}), 404
        if row["activo"] == 0:
            return jsonify({"error": "La categoría ya estaba dada de baja."}), 400
        cursor.execute("UPDATE categoria SET activo = 0 WHERE id = ?", (categoria_id,))
        conn.commit()
        return jsonify({"mensaje": f"Categoría id={categoria_id} dada de baja (borrado lógico)."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/categorias", methods=["POST"])
def crear_categoria():
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categoria (nombre, activo) VALUES (?, 1)", (nombre,))
        conn.commit()
        return jsonify({"id": cursor.lastrowid, "nombre": nombre}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Ya existe una categoría con el nombre '{nombre}'."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ── Productos ───────────────────────────────────

@app.route("/api/productos", methods=["GET"])
def listar_productos():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nombre, p.categoria_id, c.nombre AS categoria_nombre
            FROM producto p
            JOIN categoria c ON c.id = p.categoria_id
            WHERE p.activo = 1
            ORDER BY p.nombre
        """)
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/productos/<int:producto_id>", methods=["PUT"])
def actualizar_producto(producto_id):
    data = request.get_json(silent=True) or {}
    nombre       = (data.get("nombre") or "").strip()
    categoria_id = data.get("categoria_id")

    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    if not categoria_id:
        return jsonify({"error": "El campo 'categoria_id' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM producto WHERE id = ? AND activo = 1", (producto_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Producto con id={producto_id} no encontrado o dado de baja."}), 404
        cursor.execute("SELECT id FROM categoria WHERE id = ? AND activo = 1", (categoria_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Categoría con id={categoria_id} no encontrada o dada de baja."}), 404
        cursor.execute(
            "UPDATE producto SET nombre = ?, categoria_id = ? WHERE id = ?",
            (nombre, categoria_id, producto_id),
        )
        conn.commit()
        return jsonify({"id": producto_id, "nombre": nombre, "categoria_id": categoria_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/productos/<int:producto_id>", methods=["DELETE"])
def desactivar_producto(producto_id):
    """Borrado lógico: marca el producto como inactivo (activo = 0)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, activo FROM producto WHERE id = ?", (producto_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"Producto con id={producto_id} no encontrado."}), 404
        if row["activo"] == 0:
            return jsonify({"error": "El producto ya estaba dado de baja."}), 400
        cursor.execute("UPDATE producto SET activo = 0 WHERE id = ?", (producto_id,))
        conn.commit()
        return jsonify({"mensaje": f"Producto id={producto_id} dado de baja (borrado lógico)."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/productos", methods=["POST"])
def crear_producto():
    data = request.get_json(silent=True) or {}
    nombre       = (data.get("nombre") or "").strip()
    categoria_id = data.get("categoria_id")

    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    if not categoria_id:
        return jsonify({"error": "El campo 'categoria_id' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM categoria WHERE id = ? AND activo = 1", (categoria_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Categoría con id={categoria_id} no encontrada o dada de baja."}), 404

        cursor.execute(
            "INSERT INTO producto (nombre, categoria_id, activo) VALUES (?, ?, 1)",
            (nombre, categoria_id),
        )
        conn.commit()
        return jsonify({"id": cursor.lastrowid, "nombre": nombre, "categoria_id": categoria_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ── Piezas ──────────────────────────────────────

@app.route("/api/piezas", methods=["GET"])
def listar_piezas():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id,
                p.nombre,
                p.producto_id,
                pr.nombre AS producto_nombre,
                cp.costo  AS costo_actual,
                cp.fecha_desde AS costo_desde
            FROM pieza p
            JOIN producto pr ON pr.id = p.producto_id
            LEFT JOIN costo_pieza cp
                ON cp.pieza_id = p.id AND cp.es_actual = 1
            WHERE p.activo = 1
            ORDER BY p.nombre
        """)
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/piezas/<int:pieza_id>", methods=["PUT"])
def actualizar_pieza(pieza_id):
    """Actualiza el nombre y/o producto_id de una pieza."""
    data = request.get_json(silent=True) or {}
    nombre      = (data.get("nombre") or "").strip()
    producto_id = data.get("producto_id")

    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    if not producto_id:
        return jsonify({"error": "El campo 'producto_id' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pieza WHERE id = ? AND activo = 1", (pieza_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Pieza con id={pieza_id} no encontrada o dada de baja."}), 404
        cursor.execute("SELECT id FROM producto WHERE id = ? AND activo = 1", (producto_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Producto con id={producto_id} no encontrado o dado de baja."}), 404
        cursor.execute(
            "UPDATE pieza SET nombre = ?, producto_id = ? WHERE id = ?",
            (nombre, producto_id, pieza_id),
        )
        conn.commit()
        return jsonify({"id": pieza_id, "nombre": nombre, "producto_id": producto_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/piezas/<int:pieza_id>", methods=["DELETE"])
def desactivar_pieza(pieza_id):
    """Borrado lógico: marca la pieza como inactiva (activo = 0)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, activo FROM pieza WHERE id = ?", (pieza_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"Pieza con id={pieza_id} no encontrada."}), 404
        if row["activo"] == 0:
            return jsonify({"error": "La pieza ya estaba dada de baja."}), 400
        cursor.execute("UPDATE pieza SET activo = 0 WHERE id = ?", (pieza_id,))
        conn.commit()
        return jsonify({"mensaje": f"Pieza id={pieza_id} dada de baja (borrado lógico)."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/costos-piezas/<int:pieza_id>/historial", methods=["GET"])
def historial_costos_pieza(pieza_id):
    """Devuelve el historial completo de costos de una pieza, del más reciente al más antiguo."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pieza WHERE id = ?", (pieza_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Pieza con id={pieza_id} no encontrada."}), 404
        cursor.execute("""
            SELECT id, costo, fecha_desde, es_actual
            FROM costo_pieza
            WHERE pieza_id = ?
            ORDER BY fecha_desde DESC
        """, (pieza_id,))  # Historial completo aunque la pieza esté dada de baja
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/piezas", methods=["POST"])
def crear_pieza():
    """Crea la pieza y registra su costo inicial en costo_pieza."""
    data = request.get_json(silent=True) or {}
    nombre      = (data.get("nombre") or "").strip()
    producto_id = data.get("producto_id")
    costo       = data.get("costo")

    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400
    if not producto_id:
        return jsonify({"error": "El campo 'producto_id' es obligatorio."}), 400
    if costo is None:
        return jsonify({"error": "El campo 'costo' es obligatorio."}), 400
    try:
        costo = float(costo)
        if costo < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "'costo' debe ser un número no negativo."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM producto WHERE id = ? AND activo = 1", (producto_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Producto con id={producto_id} no encontrado o dado de baja."}), 404

        cursor.execute(
            "INSERT INTO pieza (nombre, producto_id, activo) VALUES (?, ?, 1)",
            (nombre, producto_id),
        )
        pieza_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)",
            (pieza_id, costo, datetime.now().isoformat()),
        )
        conn.commit()
        return jsonify({"id": pieza_id, "nombre": nombre, "producto_id": producto_id, "costo_inicial": costo}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ── Costos de Pieza (histórico) ─────────────────

@app.route("/api/costos-piezas/actualizar", methods=["POST"])
def actualizar_costo_pieza():
    """Marca el costo actual como obsoleto e inserta el nuevo."""
    data = request.get_json(silent=True) or {}
    pieza_id = data.get("pieza_id")
    nuevo_costo = data.get("costo")

    if not pieza_id:
        return jsonify({"error": "El campo 'pieza_id' es obligatorio."}), 400
    if nuevo_costo is None:
        return jsonify({"error": "El campo 'costo' es obligatorio."}), 400
    try:
        nuevo_costo = float(nuevo_costo)
        if nuevo_costo < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "'costo' debe ser un número no negativo."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pieza WHERE id = ? AND activo = 1", (pieza_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Pieza con id={pieza_id} no encontrada o dada de baja."}), 404

        # Marcar registros anteriores como obsoletos
        cursor.execute(
            "UPDATE costo_pieza SET es_actual = 0 WHERE pieza_id = ? AND es_actual = 1",
            (pieza_id,),
        )
        # Insertar nuevo costo
        cursor.execute(
            "INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)",
            (pieza_id, nuevo_costo, datetime.now().isoformat()),
        )
        conn.commit()
        return jsonify({
            "mensaje":   "Costo actualizado correctamente.",
            "pieza_id":  pieza_id,
            "nuevo_costo": nuevo_costo,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ── Tipos de Reparación ─────────────────────────

@app.route("/api/tipos-reparacion", methods=["GET"])
def listar_tipos_reparacion():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM tipo_reparacion WHERE activo = 1 ORDER BY nombre")
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/tipos-reparacion/<int:tipo_id>", methods=["PUT"])
def actualizar_tipo_reparacion(tipo_id):
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tipo_reparacion WHERE id = ? AND activo = 1", (tipo_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Tipo de reparación con id={tipo_id} no encontrado o dado de baja."}), 404
        cursor.execute("UPDATE tipo_reparacion SET nombre = ? WHERE id = ?", (nombre, tipo_id))
        conn.commit()
        return jsonify({"id": tipo_id, "nombre": nombre}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Ya existe un tipo de reparación con el nombre '{nombre}'."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/tipos-reparacion/<int:tipo_id>", methods=["DELETE"])
def desactivar_tipo_reparacion(tipo_id):
    """Borrado lógico: marca el tipo de reparación como inactivo (activo = 0)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, activo FROM tipo_reparacion WHERE id = ?", (tipo_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"Tipo de reparación con id={tipo_id} no encontrado."}), 404
        if row["activo"] == 0:
            return jsonify({"error": "El tipo de reparación ya estaba dado de baja."}), 400
        cursor.execute("UPDATE tipo_reparacion SET activo = 0 WHERE id = ?", (tipo_id,))
        conn.commit()
        return jsonify({"mensaje": f"Tipo de reparación id={tipo_id} dado de baja (borrado lógico)."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/precios-reparacion/<int:tipo_id>/<int:producto_id>/historial", methods=["GET"])
def historial_precios_reparacion(tipo_id, producto_id):
    """Devuelve el historial completo de precios para un tipo de reparación + producto."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.precio, pr.fecha_desde, pr.es_actual,
                   tr.nombre AS tipo_reparacion, p.nombre AS producto
            FROM precio_reparacion pr
            JOIN tipo_reparacion tr ON tr.id = pr.tipo_reparacion_id
            JOIN producto p ON p.id = pr.producto_id
            WHERE pr.tipo_reparacion_id = ? AND pr.producto_id = ?
            ORDER BY pr.fecha_desde DESC
        """, (tipo_id, producto_id))
        rows = cursor.fetchall()
        if not rows:
            return jsonify({"error": "No se encontraron registros para esa combinación."}), 404
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/tipos-reparacion", methods=["POST"])
def crear_tipo_reparacion():
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        return jsonify({"error": "El campo 'nombre' es obligatorio."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tipo_reparacion (nombre, activo) VALUES (?, 1)", (nombre,))
        conn.commit()
        return jsonify({"id": cursor.lastrowid, "nombre": nombre}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Ya existe un tipo de reparación con el nombre '{nombre}'."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ── Precios de Reparación (histórico) ───────────

@app.route("/api/precios-reparacion/actualizar", methods=["POST"])
def actualizar_precio_reparacion():
    """Registra o actualiza el precio de un tipo de reparación para un producto."""
    data = request.get_json(silent=True) or {}
    tipo_reparacion_id = data.get("tipo_reparacion_id")
    producto_id        = data.get("producto_id")
    nuevo_precio       = data.get("precio")

    if not tipo_reparacion_id:
        return jsonify({"error": "El campo 'tipo_reparacion_id' es obligatorio."}), 400
    if not producto_id:
        return jsonify({"error": "El campo 'producto_id' es obligatorio."}), 400
    if nuevo_precio is None:
        return jsonify({"error": "El campo 'precio' es obligatorio."}), 400
    try:
        nuevo_precio = float(nuevo_precio)
        if nuevo_precio < 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "'precio' debe ser un número no negativo."}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM tipo_reparacion WHERE id = ?", (tipo_reparacion_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Tipo de reparación id={tipo_reparacion_id} no encontrado."}), 404

        cursor.execute("SELECT id FROM producto WHERE id = ?", (producto_id,))
        if not cursor.fetchone():
            return jsonify({"error": f"Producto id={producto_id} no encontrado."}), 404

        # Marcar precios anteriores como obsoletos
        cursor.execute("""
            UPDATE precio_reparacion
               SET es_actual = 0
             WHERE tipo_reparacion_id = ? AND producto_id = ? AND es_actual = 1
        """, (tipo_reparacion_id, producto_id))

        # Insertar nuevo precio
        cursor.execute("""
            INSERT INTO precio_reparacion (tipo_reparacion_id, producto_id, precio, fecha_desde, es_actual)
            VALUES (?, ?, ?, ?, 1)
        """, (tipo_reparacion_id, producto_id, nuevo_precio, datetime.now().isoformat()))

        conn.commit()
        return jsonify({
            "mensaje":             "Precio de reparación actualizado correctamente.",
            "tipo_reparacion_id":  tipo_reparacion_id,
            "producto_id":         producto_id,
            "nuevo_precio":        nuevo_precio,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ═══════════════════════════════════════════════
# ENDPOINTS – Lógica de Presupuestos
# ═══════════════════════════════════════════════

def _parse_body_presupuesto(data):
    """Extrae y valida los campos comunes del body de presupuesto."""
    producto_id        = data.get("producto_id")
    pieza_ids          = data.get("piezas", [])
    tipo_reparacion_ids = data.get("reparaciones", [])
    urgencia           = (data.get("urgencia") or "Normal").strip()

    if not producto_id:
        raise ValueError("El campo 'producto_id' es obligatorio.")
    if not isinstance(pieza_ids, list):
        raise ValueError("'piezas' debe ser una lista de IDs.")
    if not isinstance(tipo_reparacion_ids, list):
        raise ValueError("'reparaciones' debe ser una lista de IDs.")
    if urgencia not in RECARGOS_URGENCIA:
        raise ValueError(f"'urgencia' inválida. Valores permitidos: {list(RECARGOS_URGENCIA.keys())}")

    return producto_id, pieza_ids, tipo_reparacion_ids, urgencia


@app.route("/api/presupuestos/calcular", methods=["POST"])
def calcular_presupuesto():
    """Devuelve el desglose del presupuesto SIN guardar en la BD."""
    data = request.get_json(silent=True) or {}
    conn = None
    try:
        producto_id, pieza_ids, tipo_reparacion_ids, urgencia = _parse_body_presupuesto(data)
        conn = get_connection()
        desglose = _calcular_presupuesto(conn, producto_id, pieza_ids, tipo_reparacion_ids, urgencia)
        return jsonify(desglose), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/presupuestos/guardar", methods=["POST"])
def guardar_presupuesto():
    """Calcula y persiste el presupuesto con sus detalles (precios fijos)."""
    data = request.get_json(silent=True) or {}
    cliente_nombre   = (data.get("cliente_nombre") or "").strip()
    cliente_contacto = (data.get("cliente_contacto") or "").strip()

    if not cliente_nombre:
        return jsonify({"error": "El campo 'cliente_nombre' es obligatorio."}), 400

    conn = None
    try:
        producto_id, pieza_ids, tipo_reparacion_ids, urgencia = _parse_body_presupuesto(data)
        conn = get_connection()
        desglose = _calcular_presupuesto(conn, producto_id, pieza_ids, tipo_reparacion_ids, urgencia)

        cursor = conn.cursor()
        fecha_creacion = datetime.now().isoformat()

        # Insertar cabecera del presupuesto
        cursor.execute("""
            INSERT INTO presupuesto
                (cliente_nombre, cliente_contacto, producto_id, urgencia, total, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, 'Pendiente', ?)
        """, (
            cliente_nombre,
            cliente_contacto or None,
            producto_id,
            urgencia,
            desglose["total"],
            fecha_creacion,
        ))
        presupuesto_id = cursor.lastrowid

        # Insertar detalle de piezas (costo fijado en este momento)
        for p in desglose["detalle_piezas"]:
            cursor.execute("""
                INSERT INTO presupuesto_detalle_pieza (presupuesto_id, pieza_id, costo_cobrado)
                VALUES (?, ?, ?)
            """, (presupuesto_id, p["pieza_id"], p["costo"]))

        # Insertar detalle de reparaciones (precio fijado en este momento)
        for r in desglose["detalle_reparaciones"]:
            cursor.execute("""
                INSERT INTO presupuesto_detalle_reparacion
                    (presupuesto_id, tipo_reparacion_id, precio_cobrado)
                VALUES (?, ?, ?)
            """, (presupuesto_id, r["tipo_reparacion_id"], r["precio"]))

        conn.commit()

        desglose["presupuesto_id"]    = presupuesto_id
        desglose["cliente_nombre"]    = cliente_nombre
        desglose["cliente_contacto"]  = cliente_contacto
        desglose["estado"]            = "Pendiente"
        desglose["fecha_creacion"]    = fecha_creacion
        return jsonify(desglose), 201

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/presupuestos", methods=["GET"])
def listar_presupuestos():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                pres.id,
                pres.cliente_nombre,
                pres.cliente_contacto,
                pres.producto_id,
                prod.nombre  AS producto_nombre,
                pres.urgencia,
                pres.total,
                pres.estado,
                pres.fecha_creacion
            FROM presupuesto pres
            JOIN producto prod ON prod.id = pres.producto_id
            ORDER BY pres.fecha_creacion DESC
        """)
        rows = cursor.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/presupuestos/<int:presupuesto_id>/estado", methods=["PUT", "POST"])
def actualizar_estado_presupuesto(presupuesto_id):
    data = request.get_json(silent=True) or {}
    nuevo_estado = (data.get("estado") or "").strip()

    if not nuevo_estado:
        return jsonify({"error": "El campo 'estado' es obligatorio."}), 400
    if nuevo_estado not in ESTADOS_VALIDOS:
        return jsonify({
            "error": f"Estado inválido. Valores permitidos: {sorted(ESTADOS_VALIDOS)}"
        }), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, estado FROM presupuesto WHERE id = ?", (presupuesto_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"Presupuesto con id={presupuesto_id} no encontrado."}), 404

        cursor.execute(
            "UPDATE presupuesto SET estado = ? WHERE id = ?",
            (nuevo_estado, presupuesto_id),
        )
        conn.commit()
        return jsonify({
            "presupuesto_id": presupuesto_id,
            "estado_anterior": row["estado"],
            "estado_nuevo":    nuevo_estado,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


# ═══════════════════════════════════════════════
# RUTAS WEB (Vistas HTML)
# ═══════════════════════════════════════════════

# ── Panel principal ────────────────────────────────

@app.route("/")
def vista_index():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM categoria WHERE activo = 1")
        n_cat = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM producto WHERE activo = 1")
        n_prod = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pieza WHERE activo = 1")
        n_pieza = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tipo_reparacion WHERE activo = 1")
        n_rep = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM presupuesto")
        n_pres = cur.fetchone()[0]
        stats = {
            "categorias":  n_cat,
            "productos":   n_prod,
            "piezas":      n_pieza,
            "reparaciones": n_rep,
            "presupuestos": n_pres,
        }
        
        # Datos para Chart.js (últimos presupuestos)
        cur.execute("SELECT fecha_creacion FROM presupuesto ORDER BY fecha_creacion DESC LIMIT 100")
        fechas = [r[0][:10] for r in cur.fetchall()]
        from collections import Counter
        conteo = Counter(fechas)
        # Ordenar cronológicamente
        chart_labels = sorted(conteo.keys())
        chart_values = [conteo[k] for k in chart_labels]
        
        # Últimos 5 presupuestos
        cur.execute("""
            SELECT pres.id, pres.cliente_nombre, pres.total, pres.estado, pres.fecha_creacion, prod.nombre AS producto_nombre
            FROM presupuesto pres
            JOIN producto prod ON prod.id = pres.producto_id
            ORDER BY pres.fecha_creacion DESC LIMIT 5
        """)
        ultimos_presupuestos = [dict(r) for r in cur.fetchall()]

        return render_template("index.html", stats=stats, chart_labels=chart_labels, chart_values=chart_values, ultimos_presupuestos=ultimos_presupuestos)
    finally:
        if conn:
            conn.close()


# ── Categorías ──────────────────────────────────

@app.route("/categorias")
def vista_categorias():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, activo FROM categoria ORDER BY nombre")
        categorias = [dict(r) for r in cur.fetchall()]
        return render_template("categorias/lista.html", categorias=categorias)
    finally:
        if conn:
            conn.close()


@app.route("/categorias/nueva")
def vista_categoria_nueva():
    return render_template("categorias/form.html", categoria=None)


@app.route("/categorias/crear", methods=["POST"])
def vista_categoria_crear():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("vista_categoria_nueva"))
    conn = None
    try:
        conn = get_connection()
        conn.execute("INSERT INTO categoria (nombre, activo) VALUES (?, 1)", (nombre,))
        conn.commit()
        flash(f"Categoría \u00ab{nombre}\u00bb creada correctamente.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ya existe una categoría con el nombre \u00ab{nombre}\u00bb.", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_categorias"))


@app.route("/categorias/<int:cid>/editar")
def vista_categoria_editar(cid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, activo FROM categoria WHERE id = ?", (cid,))
        row = cur.fetchone()
        if not row:
            flash("Categoría no encontrada.", "danger")
            return redirect(url_for("vista_categorias"))
        return render_template("categorias/form.html", categoria=dict(row))
    finally:
        if conn:
            conn.close()


@app.route("/categorias/<int:cid>/actualizar", methods=["POST"])
def vista_categoria_actualizar(cid):
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("vista_categoria_editar", cid=cid))
    conn = None
    try:
        conn = get_connection()
        conn.execute("UPDATE categoria SET nombre = ? WHERE id = ?", (nombre, cid))
        conn.commit()
        flash("Categoría actualizada correctamente.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ya existe una categoría con el nombre \u00ab{nombre}\u00bb.", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_categorias"))


@app.route("/categorias/<int:cid>/baja", methods=["POST"])
def vista_categoria_baja(cid):
    conn = None
    try:
        conn = get_connection()
        conn.execute("UPDATE categoria SET activo = 0 WHERE id = ?", (cid,))
        conn.commit()
        flash("Categoría dada de baja.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_categorias"))


# ── Productos ──────────────────────────────────

@app.route("/productos")
def vista_productos():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.nombre, p.categoria_id, p.activo, c.nombre AS categoria_nombre
            FROM producto p JOIN categoria c ON c.id = p.categoria_id
            ORDER BY p.nombre
        """)
        productos = [dict(r) for r in cur.fetchall()]
        return render_template("productos/lista.html", productos=productos)
    finally:
        if conn:
            conn.close()


@app.route("/productos/nuevo")
def vista_producto_nuevo():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM categoria WHERE activo = 1 ORDER BY nombre")
        categorias = [dict(r) for r in cur.fetchall()]
        return render_template("productos/form.html", producto=None, categorias=categorias)
    finally:
        if conn:
            conn.close()


@app.route("/productos/crear", methods=["POST"])
def vista_producto_crear():
    nombre = (request.form.get("nombre") or "").strip()
    categoria_id = request.form.get("categoria_id")
    if not nombre or not categoria_id:
        flash("Nombre y categoría son obligatorios.", "danger")
        return redirect(url_for("vista_producto_nuevo"))
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO producto (nombre, categoria_id, activo) VALUES (?, ?, 1)",
            (nombre, categoria_id),
        )
        conn.commit()
        flash(f"Producto \u00ab{nombre}\u00bb creado correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_productos"))


@app.route("/productos/<int:pid>/editar")
def vista_producto_editar(pid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, categoria_id, activo FROM producto WHERE id = ?", (pid,))
        row = cur.fetchone()
        if not row:
            flash("Producto no encontrado.", "danger")
            return redirect(url_for("vista_productos"))
        cur.execute("SELECT id, nombre FROM categoria WHERE activo = 1 ORDER BY nombre")
        categorias = [dict(r) for r in cur.fetchall()]
        return render_template("productos/form.html", producto=dict(row), categorias=categorias)
    finally:
        if conn:
            conn.close()


@app.route("/productos/<int:pid>/actualizar", methods=["POST"])
def vista_producto_actualizar(pid):
    nombre = (request.form.get("nombre") or "").strip()
    categoria_id = request.form.get("categoria_id")
    if not nombre or not categoria_id:
        flash("Nombre y categoría son obligatorios.", "danger")
        return redirect(url_for("vista_producto_editar", pid=pid))
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE producto SET nombre = ?, categoria_id = ? WHERE id = ?",
            (nombre, categoria_id, pid),
        )
        conn.commit()
        flash("Producto actualizado correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_productos"))


@app.route("/productos/<int:pid>/baja", methods=["POST"])
def vista_producto_baja(pid):
    conn = None
    try:
        conn = get_connection()
        conn.execute("UPDATE producto SET activo = 0 WHERE id = ?", (pid,))
        conn.commit()
        flash("Producto dado de baja.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_productos"))


# ── Piezas ────────────────────────────────────

@app.route("/piezas")
def vista_piezas():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.nombre, p.producto_id, p.activo,
                   pr.nombre AS producto_nombre,
                   cp.costo AS costo_actual, cp.fecha_desde AS costo_desde
            FROM pieza p
            JOIN producto pr ON pr.id = p.producto_id
            LEFT JOIN costo_pieza cp ON cp.pieza_id = p.id AND cp.es_actual = 1
            ORDER BY p.nombre
        """)
        piezas = [dict(r) for r in cur.fetchall()]
        return render_template("piezas/lista.html", piezas=piezas)
    finally:
        if conn:
            conn.close()


@app.route("/piezas/nueva")
def vista_pieza_nueva():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]
        return render_template("piezas/form.html", pieza=None, productos=productos)
    finally:
        if conn:
            conn.close()


@app.route("/piezas/crear", methods=["POST"])
def vista_pieza_crear():
    nombre = (request.form.get("nombre") or "").strip()
    producto_id = request.form.get("producto_id")
    costo = request.form.get("costo")
    if not nombre or not producto_id or costo is None:
        flash("Todos los campos son obligatorios.", "danger")
        return redirect(url_for("vista_pieza_nueva"))
    try:
        costo_val = float(costo)
    except ValueError:
        flash("El costo debe ser un número válido.", "danger")
        return redirect(url_for("vista_pieza_nueva"))
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO pieza (nombre, producto_id, activo) VALUES (?, ?, 1)",
            (nombre, producto_id),
        )
        pieza_id = cur.lastrowid
        cur.execute(
            "INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)",
            (pieza_id, costo_val, datetime.now().isoformat()),
        )
        conn.commit()
        flash(f"Pieza \u00ab{nombre}\u00bb creada correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_piezas"))


@app.route("/piezas/<int:pid>/editar")
def vista_pieza_editar(pid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, producto_id, activo FROM pieza WHERE id = ?", (pid,))
        row = cur.fetchone()
        if not row:
            flash("Pieza no encontrada.", "danger")
            return redirect(url_for("vista_piezas"))
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]
        return render_template("piezas/form.html", pieza=dict(row), productos=productos)
    finally:
        if conn:
            conn.close()


@app.route("/piezas/<int:pid>/actualizar", methods=["POST"])
def vista_pieza_actualizar(pid):
    nombre = (request.form.get("nombre") or "").strip()
    producto_id = request.form.get("producto_id")
    if not nombre or not producto_id:
        flash("Nombre y producto son obligatorios.", "danger")
        return redirect(url_for("vista_pieza_editar", pid=pid))
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE pieza SET nombre = ?, producto_id = ? WHERE id = ?",
            (nombre, producto_id, pid),
        )
        conn.commit()
        flash("Pieza actualizada correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_piezas"))


@app.route("/piezas/<int:pid>/costo", methods=["GET"])
def vista_pieza_costo_form(pid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.id, p.nombre, cp.costo AS costo_actual
            FROM pieza p
            LEFT JOIN costo_pieza cp ON cp.pieza_id = p.id AND cp.es_actual = 1
            WHERE p.id = ?
        """, (pid,))
        row = cur.fetchone()
        if not row:
            flash("Pieza no encontrada.", "danger")
            return redirect(url_for("vista_piezas"))
        cur.execute("""
            SELECT costo, fecha_desde, es_actual
            FROM costo_pieza WHERE pieza_id = ?
            ORDER BY fecha_desde DESC
        """, (pid,))
        historial = [dict(r) for r in cur.fetchall()]
        return render_template("piezas/costo.html", pieza=dict(row), historial=historial)
    finally:
        if conn:
            conn.close()


@app.route("/piezas/<int:pid>/costo", methods=["POST"])
def vista_pieza_costo_guardar(pid):
    costo = request.form.get("costo")
    try:
        costo_val = float(costo)
    except (TypeError, ValueError):
        flash("El costo debe ser un número válido.", "danger")
        return redirect(url_for("vista_pieza_costo_form", pid=pid))
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE costo_pieza SET es_actual = 0 WHERE pieza_id = ? AND es_actual = 1", (pid,)
        )
        conn.execute(
            "INSERT INTO costo_pieza (pieza_id, costo, fecha_desde, es_actual) VALUES (?, ?, ?, 1)",
            (pid, costo_val, datetime.now().isoformat()),
        )
        conn.commit()
        flash("Costo actualizado correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_piezas"))


@app.route("/piezas/<int:pid>/baja", methods=["POST"])
def vista_pieza_baja(pid):
    conn = None
    try:
        conn = get_connection()
        conn.execute("UPDATE pieza SET activo = 0 WHERE id = ?", (pid,))
        conn.commit()
        flash("Pieza dada de baja.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_piezas"))


# ── Tipos de Reparación ────────────────────────────

@app.route("/tipos-reparacion")
def vista_tipos_reparacion():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, activo FROM tipo_reparacion ORDER BY nombre")
        tipos = [dict(r) for r in cur.fetchall()]
        return render_template("reparaciones/lista.html", tipos=tipos)
    finally:
        if conn:
            conn.close()


@app.route("/tipos-reparacion/nuevo")
def vista_tipo_reparacion_nuevo():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT id, nombre, producto_id FROM pieza WHERE activo = 1 ORDER BY nombre")
        piezas = [dict(r) for r in cur.fetchall()]
        
        piezas_por_producto = {}
        for p in productos:
            piezas_por_producto[p['id']] = {
                'nombre': p['nombre'],
                'piezas': []
            }
        for pz in piezas:
            pid = pz['producto_id']
            if pid in piezas_por_producto:
                piezas_por_producto[pid]['piezas'].append(pz)
        
        piezas_por_producto = {k: v for k, v in piezas_por_producto.items() if len(v['piezas']) > 0}
        
        return render_template("reparaciones/form.html", tipo=None, piezas_por_producto=piezas_por_producto, piezas_asociadas=[])
    finally:
        if conn:
            conn.close()


@app.route("/tipos-reparacion/crear", methods=["POST"])
def vista_tipo_reparacion_crear():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("vista_tipo_reparacion_nuevo"))
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO tipo_reparacion (nombre, activo) VALUES (?, 1)", (nombre,))
        tipo_id = cur.lastrowid
        
        pieza_ids = request.form.getlist("piezas")
        for pid in pieza_ids:
            cur.execute("INSERT INTO tipo_reparacion_pieza (tipo_reparacion_id, pieza_id) VALUES (?, ?)", (tipo_id, int(pid)))
        conn.commit()
        flash(f"Tipo «{nombre}» creado correctamente.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ya existe un tipo con el nombre «{nombre}».", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_tipos_reparacion"))


@app.route("/tipos-reparacion/<int:tid>/editar")
def vista_tipo_reparacion_editar(tid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, activo FROM tipo_reparacion WHERE id = ?", (tid,))
        row = cur.fetchone()
        if not row:
            flash("Tipo de reparación no encontrado.", "danger")
            return redirect(url_for("vista_tipos_reparacion"))
        
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT id, nombre, producto_id FROM pieza WHERE activo = 1 ORDER BY nombre")
        piezas = [dict(r) for r in cur.fetchall()]
        
        piezas_por_producto = {}
        for p in productos:
            piezas_por_producto[p['id']] = {
                'nombre': p['nombre'],
                'piezas': []
            }
        for pz in piezas:
            pid = pz['producto_id']
            if pid in piezas_por_producto:
                piezas_por_producto[pid]['piezas'].append(pz)
        
        piezas_por_producto = {k: v for k, v in piezas_por_producto.items() if len(v['piezas']) > 0}
        
        cur.execute("SELECT pieza_id FROM tipo_reparacion_pieza WHERE tipo_reparacion_id = ?", (tid,))
        piezas_asociadas = [r["pieza_id"] for r in cur.fetchall()]
        
        return render_template("reparaciones/form.html", tipo=dict(row), piezas_por_producto=piezas_por_producto, piezas_asociadas=piezas_asociadas)
    finally:
        if conn:
            conn.close()


@app.route("/tipos-reparacion/<int:tid>/actualizar", methods=["POST"])
def vista_tipo_reparacion_actualizar(tid):
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("vista_tipo_reparacion_editar", tid=tid))
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tipo_reparacion SET nombre = ? WHERE id = ?", (nombre, tid))
        cur.execute("DELETE FROM tipo_reparacion_pieza WHERE tipo_reparacion_id = ?", (tid,))
        pieza_ids = request.form.getlist("piezas")
        for pid in pieza_ids:
            cur.execute("INSERT INTO tipo_reparacion_pieza (tipo_reparacion_id, pieza_id) VALUES (?, ?)", (tid, int(pid)))
        conn.commit()
        flash("Tipo actualizado correctamente.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ya existe un tipo con el nombre «{nombre}».", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_tipos_reparacion"))


@app.route("/tipos-reparacion/<int:tid>/baja", methods=["POST"])
def vista_tipo_reparacion_baja(tid):
    conn = None
    try:
        conn = get_connection()
        conn.execute("UPDATE tipo_reparacion SET activo = 0 WHERE id = ?", (tid,))
        conn.commit()
        flash("Tipo de reparación dado de baja.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_tipos_reparacion"))


@app.route("/tipos-reparacion/<int:tid>/precio", methods=["GET"])
def vista_precio_reparacion_form(tid):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM tipo_reparacion WHERE id = ?", (tid,))
        row = cur.fetchone()
        if not row:
            flash("Tipo de reparación no encontrado.", "danger")
            return redirect(url_for("vista_tipos_reparacion"))
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT pr.precio, pr.fecha_desde, p.nombre AS producto_nombre
            FROM precio_reparacion pr
            JOIN producto p ON p.id = pr.producto_id
            WHERE pr.tipo_reparacion_id = ? AND pr.es_actual = 1
            ORDER BY p.nombre
        """, (tid,))
        precios_actuales = [dict(r) for r in cur.fetchall()]
        return render_template(
            "reparaciones/precio.html",
            tipo=dict(row),
            productos=productos,
            precios_actuales=precios_actuales,
        )
    finally:
        if conn:
            conn.close()


@app.route("/tipos-reparacion/<int:tid>/precio", methods=["POST"])
def vista_precio_reparacion_guardar(tid):
    producto_id = request.form.get("producto_id")
    precio = request.form.get("precio")
    try:
        precio_val = float(precio)
    except (TypeError, ValueError):
        flash("El precio debe ser un número válido.", "danger")
        return redirect(url_for("vista_precio_reparacion_form", tid=tid))
    conn = None
    try:
        conn = get_connection()
        conn.execute("""
            UPDATE precio_reparacion SET es_actual = 0
            WHERE tipo_reparacion_id = ? AND producto_id = ? AND es_actual = 1
        """, (tid, producto_id))
        conn.execute("""
            INSERT INTO precio_reparacion (tipo_reparacion_id, producto_id, precio, fecha_desde, es_actual)
            VALUES (?, ?, ?, ?, 1)
        """, (tid, producto_id, precio_val, datetime.now().isoformat()))
        conn.commit()
        flash("Precio actualizado correctamente.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_tipos_reparacion"))


# ── Configuración ────────────────────────────────

@app.route("/configuracion", methods=["GET"])
def vista_configuracion():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT clave, valor FROM configuracion")
        raw = {r["clave"]: r["valor"] for r in cur.fetchall()}
        # Convertir a porcentaje entero para mostrar en el formulario
        cfg = {
            "margen_ganancia":   int(float(raw.get("margen_ganancia", 0.30)) * 100),
            "recargo_Normal":    int(float(raw.get("recargo_Normal",   0.00)) * 100),
            "recargo_24hs":      int(float(raw.get("recargo_24hs",     0.20)) * 100),
            "recargo_Inmediato": int(float(raw.get("recargo_Inmediato",0.50)) * 100),
            "alias_servicios":   raw.get("alias_servicios", "Reparaciones"),
            "alias_insumos":     raw.get("alias_insumos", "Piezas"),
            "alias_proyectos":   raw.get("alias_proyectos", "Productos"),
            "nombre_negocio":    raw.get("nombre_negocio", "Mi Negocio"),
        }
        return render_template("configuracion.html", cfg=cfg)
    finally:
        if conn:
            conn.close()


@app.route("/configuracion", methods=["POST"])
def vista_configuracion_guardar():
    claves_pct = ["margen_ganancia", "recargo_Normal", "recargo_24hs", "recargo_Inmediato"]
    claves_texto = ["alias_servicios", "alias_insumos", "alias_proyectos", "nombre_negocio"]
    conn = None
    try:
        conn = get_connection()
        for clave in claves_pct:
            valor_pct = request.form.get(clave)
            if valor_pct is not None:
                conn.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = ?",
                    (str(float(valor_pct) / 100), clave),
                )
        for clave in claves_texto:
            valor_txt = request.form.get(clave)
            if valor_txt is not None and valor_txt.strip():
                conn.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = ?",
                    (valor_txt.strip(), clave),
                )
        conn.commit()
        flash("Configuración guardada correctamente.", "success")
    except (TypeError, ValueError):
        flash("Valores inválidos. Solo se permiten números.", "danger")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_configuracion"))


# ── Presupuestos ─────────────────────────────────

@app.route("/presupuestos")
def vista_presupuestos():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT pres.id, pres.cliente_nombre, pres.cliente_contacto,
                   pres.urgencia, pres.total, pres.estado, pres.fecha_creacion,
                   prod.nombre AS producto_nombre
            FROM presupuesto pres
            JOIN producto prod ON prod.id = pres.producto_id
            ORDER BY pres.fecha_creacion DESC
        """)
        presupuestos = [dict(r) for r in cur.fetchall()]
        return render_template("presupuestos/lista.html", presupuestos=presupuestos)
    finally:
        if conn:
            conn.close()


@app.route("/presupuestos/nuevo")
def vista_presupuesto_nuevo():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM producto WHERE activo = 1 ORDER BY nombre")
        productos = [dict(r) for r in cur.fetchall()]

        # Piezas activas con costo vigente, incluimos producto_id para filtrar en JS
        cur.execute("""
            SELECT p.id, p.nombre, p.producto_id, prod.nombre AS producto_nombre,
                   cp.costo AS costo_actual
            FROM pieza p
            JOIN producto prod ON prod.id = p.producto_id
            JOIN costo_pieza cp ON cp.pieza_id = p.id AND cp.es_actual = 1
            WHERE p.activo = 1
            ORDER BY p.nombre
        """)
        piezas = [dict(r) for r in cur.fetchall()]

        # Tipos de reparación activos
        cur.execute("SELECT id, nombre FROM tipo_reparacion WHERE activo = 1 ORDER BY nombre")
        tipos_reparacion = [dict(r) for r in cur.fetchall()]

        # Mapa: producto_id -> [tipo_reparacion_id, ...] que tienen precio vigente
        cur.execute("""
            SELECT producto_id, tipo_reparacion_id, precio
            FROM precio_reparacion
            WHERE es_actual = 1
        """)
        tipos_por_producto = {}
        for row in cur.fetchall():
            pid = row["producto_id"]
            tid = row["tipo_reparacion_id"]
            precio = row["precio"]
            tipos_por_producto.setdefault(pid, []).append({"id": tid, "precio": precio})

        # Recargos actuales desde la BD (en porcentaje entero para mostrar)
        cur.execute("SELECT clave, valor FROM configuracion")
        raw_cfg = {r["clave"]: r["valor"] for r in cur.fetchall()}
        recargos = {
            "Normal":    int(float(raw_cfg.get("recargo_Normal",    0.00)) * 100),
            "24hs":      int(float(raw_cfg.get("recargo_24hs",      0.20)) * 100),
            "Inmediato": int(float(raw_cfg.get("recargo_Inmediato", 0.50)) * 100),
        }

        # Obtener piezas sugeridas por cada tipo de reparación
        cur.execute("SELECT tipo_reparacion_id, pieza_id FROM tipo_reparacion_pieza")
        sugerencias = {}
        for row in cur.fetchall():
            tid = row["tipo_reparacion_id"]
            pz_id = row["pieza_id"]
            sugerencias.setdefault(tid, []).append(pz_id)

        return render_template(
            "presupuestos/form.html",
            productos=productos,
            piezas=piezas,
            tipos_reparacion=tipos_reparacion,
            tipos_por_producto=tipos_por_producto,
            sugerencias=sugerencias,
            recargos=recargos,
        )
    finally:
        if conn:
            conn.close()


@app.route("/presupuestos/crear", methods=["POST"])
def vista_presupuesto_crear():
    cliente_nombre   = (request.form.get("cliente_nombre") or "").strip()
    cliente_contacto = (request.form.get("cliente_contacto") or "").strip()
    producto_id      = request.form.get("producto_id")
    urgencia         = request.form.get("urgencia", "Normal")
    pieza_ids        = [int(x) for x in request.form.getlist("piezas")]
    rep_ids          = [int(x) for x in request.form.getlist("reparaciones")]

    if not cliente_nombre or not producto_id:
        flash("Cliente y producto son obligatorios.", "danger")
        return redirect(url_for("vista_presupuesto_nuevo"))

    conn = None
    try:
        conn = get_connection()
        desglose = _calcular_presupuesto(conn, int(producto_id), pieza_ids, rep_ids, urgencia)

        cursor = conn.cursor()
        fecha = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO presupuesto
                (cliente_nombre, cliente_contacto, producto_id, urgencia, total, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, 'Pendiente', ?)
        """, (cliente_nombre, cliente_contacto or None, producto_id,
              urgencia, desglose["total"], fecha))
        pres_id = cursor.lastrowid

        for p in desglose["detalle_piezas"]:
            cursor.execute("""
                INSERT INTO presupuesto_detalle_pieza (presupuesto_id, pieza_id, costo_cobrado)
                VALUES (?, ?, ?)
            """, (pres_id, p["pieza_id"], p["costo"]))

        for r in desglose["detalle_reparaciones"]:
            cursor.execute("""
                INSERT INTO presupuesto_detalle_reparacion
                    (presupuesto_id, tipo_reparacion_id, precio_cobrado)
                VALUES (?, ?, ?)
            """, (pres_id, r["tipo_reparacion_id"], r["precio"]))

        conn.commit()
        flash(f"Presupuesto #{pres_id} creado correctamente. Total: ${desglose['total']:.2f}", "success")
        return redirect(url_for("vista_presupuesto_detalle", pres_id=pres_id))
    except ValueError as ve:
        flash(str(ve), "danger")
        return redirect(url_for("vista_presupuesto_nuevo"))
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"Error al guardar: {e}", "danger")
        return redirect(url_for("vista_presupuesto_nuevo"))
    finally:
        if conn:
            conn.close()


@app.route("/presupuestos/<int:pres_id>")
def vista_presupuesto_detalle(pres_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT pres.id, pres.cliente_nombre, pres.cliente_contacto,
                   pres.urgencia, pres.total, pres.estado, pres.fecha_creacion,
                   prod.nombre AS producto_nombre
            FROM presupuesto pres
            JOIN producto prod ON prod.id = pres.producto_id
            WHERE pres.id = ?
        """, (pres_id,))
        row = cur.fetchone()
        if not row:
            flash("Presupuesto no encontrado.", "danger")
            return redirect(url_for("vista_presupuestos"))
        p = dict(row)

        cur.execute("""
            SELECT dp.costo_cobrado, pz.nombre AS pieza_nombre
            FROM presupuesto_detalle_pieza dp
            JOIN pieza pz ON pz.id = dp.pieza_id
            WHERE dp.presupuesto_id = ?
        """, (pres_id,))
        detalle_piezas = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT dr.precio_cobrado, tr.nombre AS tipo_nombre
            FROM presupuesto_detalle_reparacion dr
            JOIN tipo_reparacion tr ON tr.id = dr.tipo_reparacion_id
            WHERE dr.presupuesto_id = ?
        """, (pres_id,))
        detalle_reparaciones = [dict(r) for r in cur.fetchall()]

        return render_template(
            "presupuestos/detalle.html",
            p=p,
            detalle_piezas=detalle_piezas,
            detalle_reparaciones=detalle_reparaciones,
        )
    finally:
        if conn:
            conn.close()


@app.route("/presupuestos/<int:pres_id>/estado", methods=["POST"])
def vista_presupuesto_estado(pres_id):
    nuevo_estado = (request.form.get("estado") or "").strip()
    if nuevo_estado not in ESTADOS_VALIDOS:
        flash(f"Estado inválido: {nuevo_estado}", "danger")
        return redirect(url_for("vista_presupuestos"))
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE presupuesto SET estado = ? WHERE id = ?",
            (nuevo_estado, pres_id),
        )
        conn.commit()
        flash(f"Presupuesto #{pres_id} marcado como {nuevo_estado}.", "success")
    finally:
        if conn:
            conn.close()
    return redirect(url_for("vista_presupuesto_detalle", pres_id=pres_id))


# ───────────────────────────────────────────────
# Entry point
# ───────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    app.run(debug=True, threaded=True)

