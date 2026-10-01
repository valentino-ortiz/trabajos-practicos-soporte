"""
Módulo de configuración de ChefVoz.

Define rutas absolutas, constantes de la aplicación y ajustes de Flask.
Todas las rutas se calculan dinámicamente desde la ubicación de este archivo.
"""

import os

# ── Rutas base del proyecto ────────────────────────────────────────────────────
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DIR_SRC = os.path.join(DIR_BASE, "src")
DIR_STATIC = os.path.join(DIR_BASE, "static")
DIR_TEMPLATES = os.path.join(DIR_BASE, "templates")
DIR_CACHE_AUDIO = os.path.join(DIR_BASE, "cache")
DIR_DB = os.path.join(DIR_BASE, "data")

# ── Archivo de base de datos ───────────────────────────────────────────────────
RUTA_DB = os.path.join(DIR_DB, "chefvoz.db")

# ── Configuración de caché de audio ───────────────────────────────────────────
EXTENSION_AUDIO = ".mp3"
# Días máximos que se conserva un archivo de audio en caché (0 = sin límite)
MAX_DIAS_CACHE = 7

# ── Idioma para gTTS ───────────────────────────────────────────────────────────
IDIOMA_TTS = "es"
# Velocidad de voz: False = normal, True = lento
TTS_LENTO = False

# ── Configuración de Flask ─────────────────────────────────────────────────────
class Config:
    """Configuración base de Flask."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "chefvoz-dev-secret-key-2024")
    DEBUG = False
    TESTING = False
    # Tamaño máximo de subida (10 MB)
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

class ConfigDesarrollo(Config):
    """Configuración para el entorno de desarrollo."""
    DEBUG = True

class ConfigProduccion(Config):
    """Configuración para el entorno de producción."""
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion")

class ConfigPruebas(Config):
    """Configuración para el entorno de pruebas automatizadas."""
    TESTING = True
    DEBUG = True
    # Base de datos en memoria para pruebas rápidas
    RUTA_DB_PRUEBA = os.path.join(DIR_DB, "chefvoz_test.db")

# Mapa de entornos → clases de configuración
CONFIGURACIONES = {
    "desarrollo": ConfigDesarrollo,
    "produccion": ConfigProduccion,
    "pruebas": ConfigPruebas,
    "default": ConfigDesarrollo,
}


def obtener_config(entorno: str = "default") -> Config:
    """
    Devuelve la clase de configuración correspondiente al entorno indicado.

    Args:
        entorno: Nombre del entorno ('desarrollo', 'produccion', 'pruebas', 'default').

    Returns:
        Clase de configuración de Flask.
    """
    return CONFIGURACIONES.get(entorno, ConfigDesarrollo)
