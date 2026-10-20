"""SQLite del estacionamiento. WAL: un proceso escribe (main.py --registrar) y otro lee (dashboard.py).
t_sim = segundos simulados desde el inicio de la sesión."""
import sqlite3
from datetime import datetime

from common import DIR

DB_PATH = DIR / "estacionamiento.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY, preset INTEGER NOT NULL, inicio TEXT NOT NULL,
    escala REAL NOT NULL, creada_en TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS eventos (
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id), celda INTEGER NOT NULL,
    t_sim REAL NOT NULL, libre INTEGER NOT NULL, inicial INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS muestras (
    sesion_id INTEGER NOT NULL REFERENCES sesiones(id), t_sim REAL NOT NULL,
    libres INTEGER NOT NULL, total INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_eventos ON eventos(sesion_id, celda);
CREATE INDEX IF NOT EXISTS ix_muestras ON muestras(sesion_id, t_sim);
"""


def conectar(path=DB_PATH):
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(ESQUEMA)
    return con


def nueva_sesion(con, preset, inicio, escala):
    cur = con.execute("INSERT INTO sesiones (preset, inicio, escala, creada_en) VALUES (?,?,?,?)",
                      (preset, inicio, escala, datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return cur.lastrowid


def registrar_eventos(con, sesion, eventos):
    """eventos: [(celda, t_sim, libre, inicial)]"""
    con.executemany("INSERT INTO eventos (sesion_id, celda, t_sim, libre, inicial) VALUES (?,?,?,?,?)",
                    [(sesion, c, t, int(l), int(i)) for c, t, l, i in eventos])
    con.commit()


def registrar_muestra(con, sesion, t_sim, libres, total):
    con.execute("INSERT INTO muestras (sesion_id, t_sim, libres, total) VALUES (?,?,?,?)",
                (sesion, t_sim, libres, total))
    con.commit()


def ultima_sesion(con, preset):
    return con.execute("SELECT * FROM sesiones WHERE preset=? ORDER BY id DESC LIMIT 1", (preset,)).fetchone()


def eventos(con, sesion):
    """[(celda, t_sim, libre, inicial)] en el formato de reglas.py"""
    return [(r[0], r[1], bool(r[2]), bool(r[3])) for r in con.execute(
        "SELECT celda, t_sim, libre, inicial FROM eventos WHERE sesion_id=? ORDER BY t_sim, rowid", (sesion,))]


def muestras(con, sesion):
    """[(t_sim, libres, total)]"""
    return [tuple(r) for r in con.execute(
        "SELECT t_sim, libres, total FROM muestras WHERE sesion_id=? ORDER BY t_sim", (sesion,))]


def estado_actual(con, sesion):
    """{celda: libre} según el último evento de cada celda."""
    return {r[0]: bool(r[1]) for r in con.execute(
        "SELECT celda, libre FROM eventos WHERE rowid IN "
        "(SELECT MAX(rowid) FROM eventos WHERE sesion_id=? GROUP BY celda)", (sesion,))}
