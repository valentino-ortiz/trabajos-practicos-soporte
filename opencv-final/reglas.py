"""Reglas de negocio del estacionamiento. Funciones puras: sin base de datos ni Flask.

Tiempos en segundos simulados desde el inicio de la sesión.
Evento = (celda, t, libre, inicial): `inicial` marca el estado visto en el primer frame válido,
que no cuenta como llegada ni como salida. Muestra = (t, libres, total).
"""

FRANJA = 600  # 10 minutos simulados


def nivel_ocupacion(libres, total, umbrales=(0.7, 0.9)):
    """'libre' (< 70% ocupado), 'medio' (70-90%), 'casi_lleno' (90-100%) o 'lleno' (100%)."""
    if total <= 0:
        return "libre"
    ocupacion = 1 - libres / total
    if ocupacion >= 1:
        return "lleno"
    if ocupacion >= umbrales[1]:
        return "casi_lleno"
    return "medio" if ocupacion >= umbrales[0] else "libre"


def estadias_completas(eventos):
    """[(celda, t_inicio, t_fin, duracion)]: solo ocupaciones cuya llegada y salida se vieron.
    Una celda que ya estaba ocupada al empezar queda 'en curso' y no entra."""
    inicio, out = {}, []
    for celda, t, libre, inicial in sorted(eventos, key=lambda e: e[1]):
        if libre:
            t0 = inicio.pop(celda, None)
            if t0 is not None:
                out.append((celda, t0, t, t - t0))
        elif inicial:
            inicio[celda] = None
        else:
            inicio[celda] = t
    return out


def estadia_promedio(eventos):
    """Duración media (segundos simulados) de las estadías completas, o None si no hay ninguna."""
    d = [e[3] for e in estadias_completas(eventos)]
    return sum(d) / len(d) if d else None


def rotacion_por_franja(eventos, franja=FRANJA):
    """{franja: llegadas}: cuántas celdas pasaron de libre a ocupada en cada franja."""
    out = {}
    for _, t, libre, inicial in eventos:
        if not libre and not inicial:
            out[int(t // franja)] = out.get(int(t // franja), 0) + 1
    return out


def serie_ocupacion(muestras, franja=FRANJA):
    """[(franja, ocupacion media 0-1)] ordenada por franja."""
    acum = {}
    for t, libres, total in muestras:
        if total > 0:
            s = acum.setdefault(int(t // franja), [0.0, 0])
            s[0] += 1 - libres / total
            s[1] += 1
    return [(f, s[0] / s[1]) for f, s in sorted(acum.items())]


def franja_pico(muestras, franja=FRANJA):
    """(franja, ocupacion media) de la franja más ocupada, o None sin muestras. Empata a favor de la primera."""
    serie = serie_ocupacion(muestras, franja)
    return max(serie, key=lambda s: s[1]) if serie else None
