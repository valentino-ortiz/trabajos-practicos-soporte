"""Migra los pickles viejos a celdas_N.json (formato único [x,y,w,h]). Los pickles no se borran."""
import pickle
from common import DIR, cargar_preset, guardar_celdas

for n, viejo in {1: "carParkPos", 2: "posiciones_nuevo", 3: "posiciones_park"}.items():
    cfg = cargar_preset(n)
    celdas = []
    for p in pickle.load(open(DIR / viejo, "rb")):
        celdas.append(tuple(p) if len(p) == 4 else (p[0], p[1], cfg["ancho"], cfg["alto"]))
    guardar_celdas(cfg["celdas"], celdas)
    print(n, len(celdas), "->", cfg["celdas"])
