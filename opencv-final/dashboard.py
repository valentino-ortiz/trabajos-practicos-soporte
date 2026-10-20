"""API del dashboard del estacionamiento. Lee estacionamiento.db, que escribe main.py --registrar.
Tiempos en la API: minutos simulados (ver config.json: inicio y escala de cada preset)."""
import argparse
import json
from contextlib import closing
from datetime import datetime, timedelta

from flask import Flask, Response, abort, jsonify, render_template

import db
from camara import Camara
from common import DIR, cargar_celdas, cargar_preset, lote
from reglas import (estadia_promedio, estadias_completas, franja_pico, nivel_ocupacion, rotacion_por_franja,
                    serie_ocupacion)

app = Flask(__name__)
FRANJA_MIN = 10  # minutos simulados por franja, igual que reglas.FRANJA
camara = None  # se crea en __main__ con el preset elegido


def _existe(n):
    return str(n) in json.loads((DIR / "config.json").read_text())


def _sin_datos(n):
    return jsonify(error=f"Todavía no hay datos del lote {n}. Corré main.py --preset {n} --registrar"), 404


@app.get("/")
def pagina():
    return render_template("dashboard.html")


@app.get("/api/lotes")
def lotes():
    with closing(db.conectar()) as con:
        out = []
        for n in json.loads((DIR / "config.json").read_text()):
            out.append({"id": int(n), "nombre": lote(int(n))["nombre"],
                        "tiene_datos": db.ultima_sesion(con, int(n)) is not None})
    return jsonify(out)


@app.get("/api/lote/<int:n>/estado")
def estado(n):
    if not _existe(n):
        abort(404)
    with closing(db.conectar()) as con:
        s = db.ultima_sesion(con, n)
        if s is None:
            return _sin_datos(n)
        est = db.estado_actual(con, s["id"])
        t_max = con.execute("SELECT MAX(t_sim) FROM muestras WHERE sesion_id=?", (s["id"],)).fetchone()[0] or 0
    p = lote(n)
    celdas = [{"id": i, "x": x, "y": y, "w": w, "h": h, "libre": est.get(i)}
              for i, (x, y, w, h) in enumerate(cargar_celdas(cargar_preset(n)["celdas"]))]
    libres = sum(1 for v in est.values() if v)
    total = len(est)
    nivel = nivel_ocupacion(libres, total, p["umbrales"])
    hora = datetime.fromisoformat(s["inicio"]) + timedelta(seconds=t_max)
    return jsonify(
        lote=n, nombre=p["nombre"], sesion=s["id"],
        hora_simulada=hora.strftime("%H:%M"), minutos_simulados=round(t_max / 60, 1),
        libres=libres, total=total, nivel=nivel, alerta_lleno=nivel == "lleno",
        celdas=celdas)


@app.get("/api/lote/<int:n>/serie")
def serie(n):
    if not _existe(n):
        abort(404)
    with closing(db.conectar()) as con:
        s = db.ultima_sesion(con, n)
        if s is None:
            return _sin_datos(n)
        muestras = db.muestras(con, s["id"])
    puntos = [{"desde_min": f * FRANJA_MIN, "ocupacion": round(o, 3)} for f, o in serie_ocupacion(muestras)]
    return jsonify(franja_min=FRANJA_MIN, puntos=puntos)


@app.get("/api/lote/<int:n>/metricas")
def metricas(n):
    if not _existe(n):
        abort(404)
    with closing(db.conectar()) as con:
        s = db.ultima_sesion(con, n)
        if s is None:
            return _sin_datos(n)
        ev = db.eventos(con, s["id"])
        muestras = db.muestras(con, s["id"])
    prom = estadia_promedio(ev)
    pico = franja_pico(muestras)
    return jsonify(
        estadia_promedio_min=round(prom / 60, 1) if prom is not None else None,
        estadias_completas=len(estadias_completas(ev)),
        rotacion=[{"desde_min": f * FRANJA_MIN, "llegadas": k} for f, k in sorted(rotacion_por_franja(ev).items())],
        hora_pico=({"desde_min": pico[0] * FRANJA_MIN, "ocupacion": round(pico[1], 3)} if pico else None))


@app.get("/video")
def video():
    return Response(camara.stream(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camara")
def camara_estado():
    return jsonify(preset=camara.preset, corriendo=camara.corriendo.is_set())


@app.post("/api/camara/pausa")
def camara_pausa():
    camara.alternar()
    return camara_estado()


@app.post("/api/camara/preset/<int:n>")
def camara_preset(n):
    if not _existe(n):
        abort(404)
    camara.cambiar(n)
    return camara_estado()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dashboard con cámara en vivo")
    parser.add_argument("--preset", type=int, default=1, help="Preset inicial de la cámara (ver config.json)")
    args = parser.parse_args()
    if not _existe(args.preset):
        parser.error(f"No existe el preset {args.preset}")
    camara = Camara(args.preset)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
