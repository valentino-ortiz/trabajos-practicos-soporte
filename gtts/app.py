"""
Punto de entrada principal de ChefVoz.

Crea la aplicación Flask, registra los blueprints (rutas),
inicializa la base de datos y configura las carpetas necesarias.
"""

import os
import sys
import ssl

from flask import Flask, render_template, jsonify

# Asegurar que el directorio raíz del proyecto esté en el path
DIR_PROYECTO = os.path.dirname(os.path.abspath(__file__))
if DIR_PROYECTO not in sys.path:
    sys.path.insert(0, DIR_PROYECTO)

import config


def crear_directorios() -> None:
    """
    Crea los directorios necesarios para la aplicación si no existen.

    Directorios creados:
        - cache/  : archivos de audio generados por gTTS
        - data/   : base de datos SQLite
    """
    directorios = [config.DIR_CACHE_AUDIO, config.DIR_DB]
    for directorio in directorios:
        os.makedirs(directorio, exist_ok=True)


def crear_app(entorno: str = "default") -> Flask:
    """
    Fábrica de la aplicación Flask (Application Factory Pattern).

    Args:
        entorno: Nombre del entorno de configuración a usar.

    Returns:
        Instancia configurada de Flask.
    """
    app = Flask(
        __name__,
        template_folder=config.DIR_TEMPLATES,
        static_folder=config.DIR_STATIC,
    )

    # ── Configuración ──────────────────────────────────────────────────────────
    clase_config = config.obtener_config(entorno)
    app.config.from_object(clase_config)

    # ── Crear directorios necesarios ───────────────────────────────────────────
    crear_directorios()

    # ── Inicializar base de datos ──────────────────────────────────────────────
    with app.app_context():
        from src.database import Database
        db = Database()
        db.init_db()

    # ── Registrar blueprints (rutas) ───────────────────────────────────────────
    _registrar_rutas(app)

    return app


def _registrar_rutas(app: Flask) -> None:
    """
    Registra todos los blueprints y rutas de la aplicación.

    Args:
        app: Instancia de Flask donde se registran las rutas.
    """
    # ── Rutas de vistas (HTML) ─────────────────────────────────────────────────
    @app.route("/")
    @app.route("/editor")
    def index():
        """Redirige al dashboard de recetas."""
        return render_template("dashboard.html")

    @app.route("/nueva")
    def nueva_receta():
        """Vista para agregar nueva receta."""
        return render_template("nueva_receta.html")

    @app.route("/cocina/<int:receta_id>")
    def cocina(receta_id: int):
        """Vista de cocina paso a paso para una receta específica."""
        return render_template("cocina.html", receta_id=receta_id)

    # ── API REST ───────────────────────────────────────────────────────────────
    from src.api import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Manejo de errores HTTP ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def no_encontrado(error):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(500)
    def error_interno(error):
        return jsonify({"error": "Error interno del servidor"}), 500


# ── Punto de entrada ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    entorno = os.environ.get("FLASK_ENV", "desarrollo")
    aplicacion = crear_app(entorno)

    # Intentar levantar con HTTPS si existen los certificados.
    # Los navegadores modernos bloquean navigator.mediaDevices (micrófono)
    # en contextos no seguros. HTTPS lo habilita desde cualquier IP de red local.
    cert_path = os.path.join(DIR_PROYECTO, 'certs', 'cert.pem')
    key_path  = os.path.join(DIR_PROYECTO, 'certs', 'key.pem')

    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(cert_path, key_path)
        print("\n✔ Servidor HTTPS activo")
        print("  → https://localhost:5000")
        print("  → https://192.168.100.47:5000")
        print("  (La primera vez el navegador pedirá aceptar el certificado auto-firmado)\n")
        aplicacion.run(
            host="0.0.0.0",
            port=5000,
            debug=True,
            ssl_context=ssl_context,
        )
    else:
        print("\n⚠ Servidor HTTP (sin SSL). El micrófono solo funcionará en localhost.")
        print("  Para habilitar HTTPS, generá los certificados con:")
        print("  openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 3650 -nodes -subj '/CN=localhost'\n")
        aplicacion.run(
            host="0.0.0.0",
            port=5000,
            debug=True,
        )
