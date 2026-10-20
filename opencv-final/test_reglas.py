import os
import tempfile

import db
from reglas import (estadia_promedio, estadias_completas, franja_pico, nivel_ocupacion, rotacion_por_franja,
                    serie_ocupacion)

# niveles: 100 celdas
assert nivel_ocupacion(50, 100) == "libre"        # 50% ocupado
assert nivel_ocupacion(30, 100) == "medio"        # 70% justo
assert nivel_ocupacion(10, 100) == "casi_lleno"   # 90% justo
assert nivel_ocupacion(0, 100) == "lleno"
assert nivel_ocupacion(0, 0) == "libre"           # sin celdas no hay alerta

# celda 1 ya ocupada al inicio y se va a t=100 (en curso, no cuenta); celda 2 llega a t=50 y se va a t=350
# (300 s); celda 3 llega a t=700 y no se va (no cuenta); celda 2 vuelve a llegar a t=800 (otra llegada)
ev = [(1, 0, False, True), (2, 0, True, True), (1, 100, True, False), (2, 50, False, False),
      (2, 350, True, False), (3, 700, False, False), (2, 800, False, False)]
assert estadias_completas(ev) == [(2, 50, 350, 300)]
assert estadia_promedio(ev) == 300
assert estadia_promedio([(1, 0, False, True)]) is None
assert rotacion_por_franja(ev) == {0: 1, 1: 2}    # llegadas: t=50 -> franja 0; t=700, 800 -> franja 1

# muestras: franja 0 con 50% y 100% ocupado (media 0.75), franja 1 con 90%
m = [(0, 50, 100), (300, 0, 100), (700, 10, 100)]
assert serie_ocupacion(m) == [(0, 0.75), (1, 0.9)]
assert franja_pico(m) == (1, 0.9)
assert franja_pico([]) is None

# base de datos real en un archivo temporal
with tempfile.TemporaryDirectory() as d:
    con = db.conectar(os.path.join(d, "t.db"))
    assert db.ultima_sesion(con, 1) is None
    s = db.nueva_sesion(con, 1, "08:00", 2)
    db.registrar_eventos(con, s, ev)
    db.registrar_muestra(con, s, 0, 50, 100)
    assert db.ultima_sesion(con, 1)["id"] == s
    assert db.eventos(con, s) == sorted(ev, key=lambda e: e[1])
    assert db.estado_actual(con, s) == {1: True, 2: False, 3: False}   # último evento de cada celda
    assert db.muestras(con, s) == [(0, 50, 100)]
    s2 = db.nueva_sesion(con, 1, "08:00", 2)
    assert db.ultima_sesion(con, 1)["id"] == s2 and db.eventos(con, s2) == []  # sesiones aisladas
    con.close()
print("ok")
