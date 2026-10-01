"""
Blueprint de la API REST de ChefVoz.

Contiene los endpoints REST implementados fase a fase:
  FASE 0 : /api/health
  FASE 1 : /api/recetas/parse
  FASE 2 : /api/audio/generate  y  /api/audio/<hash>
  FASE 5 : CRUD completo de recetas
"""

import os
import subprocess
import tempfile

from flask import Blueprint, jsonify, request, send_file, current_app

# Blueprint que agrupa todos los endpoints /api/*
api_bp = Blueprint("api", __name__)


@api_bp.route("/voz/reconocer", methods=["POST"])
def reconocer_voz():
    """Transcribe un fragmento WebM enviado por el navegador."""
    archivo = request.files.get("audio")
    if archivo is None:
        return jsonify({"error": "Falta el archivo de audio"}), 400

    origen = destino = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temporal:
            archivo.save(temporal.name)
            origen = temporal.name
        destino = f"{origen}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", origen,
             "-ar", "16000", "-ac", "1", destino],
            check=True,
        )

        import speech_recognition as sr
        reconocedor = sr.Recognizer()
        with sr.AudioFile(destino) as fuente:
            audio = reconocedor.record(fuente)
        texto = reconocedor.recognize_google(audio, language="es-AR")
        return jsonify({"texto": texto}), 200
    except sr.UnknownValueError:
        return jsonify({"texto": ""}), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500
    finally:
        for ruta in (origen, destino):
            if ruta:
                try:
                    os.remove(ruta)
                except OSError:
                    pass


@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    Endpoint de verificación de estado del servidor.

    Returns:
        JSON con estado 'ok' y versión de la API.
    """
    return jsonify({
        "estado": "ok",
        "version": "0.1.0",
        "mensaje": "ChefVoz API funcionando correctamente"
    }), 200


# ── FASE 1: Parser ────────────────────────────────────────────────────────────
@api_bp.route("/recetas/parse", methods=["POST"])
def parsear_receta():
    """POST /api/recetas/parse — Parsea texto o URL de receta y devuelve preview."""
    datos = request.get_json(silent=True)
    if not datos:
        return jsonify({"error": "Se esperaba un JSON con 'texto' o 'url'"}), 400

    texto = datos.get("texto", "").strip()
    url   = datos.get("url", "").strip()

    if not texto and not url:
        return jsonify({"error": "Proporciona 'texto' o 'url' en el JSON"}), 400

    try:
        from src.parser import RecipeParser
        parser = RecipeParser()
        if url:
            resultado = parser.parse_url(url)
        else:
            resultado = parser.parse_text(texto)
        return jsonify(resultado), 200
    except Exception as error:
        return jsonify({"error": f"Error al parsear la receta: {error}"}), 500


@api_bp.route("/recetas", methods=["POST"])
def crear_receta():
    """POST /api/recetas — Guarda una receta en la base de datos."""
    datos = request.get_json(silent=True)
    if not datos or "titulo" not in datos:
        return jsonify({"error": "Faltan datos requeridos (título)"}), 400

    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        nuevo_id = db.guardar_receta(datos)
        return jsonify({"mensaje": "Receta guardada", "id": nuevo_id}), 201
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_bp.route("/recetas/<int:receta_id>", methods=["PUT"])
def actualizar_receta(receta_id: int):
    """PUT /api/recetas/<id> — Actualiza una receta existente."""
    datos = request.get_json(silent=True)
    if not datos or "titulo" not in datos:
        return jsonify({"error": "Faltan datos requeridos (título)"}), 400

    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        # Verificar que existe
        receta_existente = db.obtener_receta_completa(receta_id)
        if not receta_existente:
            return jsonify({"error": "Receta no encontrada"}), 404
            
        db.actualizar_receta(receta_id, datos)
        return jsonify({"mensaje": "Receta actualizada"}), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_bp.route("/recetas", methods=["GET"])
def listar_recetas():
    """GET /api/recetas — Devuelve la lista de recetas (resumen)."""
    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        recetas = db.obtener_recetas()
        return jsonify(recetas), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_bp.route("/recetas/<int:receta_id>", methods=["GET"])
def obtener_receta(receta_id: int):
    """GET /api/recetas/<id> — Obtiene una receta completa."""
    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        receta = db.obtener_receta_completa(receta_id)
        if not receta:
            return jsonify({"error": "Receta no encontrada"}), 404
        return jsonify(receta), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_bp.route("/recetas/<int:receta_id>", methods=["DELETE"])
def eliminar_receta(receta_id: int):
    """DELETE /api/recetas/<id> — Elimina una receta."""
    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        borrado = db.eliminar_receta(receta_id)
        if not borrado:
            return jsonify({"error": "Receta no encontrada"}), 404
        return jsonify({"mensaje": "Receta eliminada"}), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_bp.route("/recetas/<int:receta_id>/favorita", methods=["POST"])
def toggle_favorita(receta_id: int):
    """POST /api/recetas/<id>/favorita — Alterna el estado de favorita."""
    try:
        from src.database import Database
        db = Database(current_app.config.get("RUTA_DB"))
        nuevo_estado = db.toggle_favorita(receta_id)
        if nuevo_estado is None:
            return jsonify({"error": "Receta no encontrada"}), 404
        return jsonify({"mensaje": "Favorita actualizada", "favorita": nuevo_estado}), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 500


# ── FASE 6: Sesión de Cocina (State Machine) ──────────────────────────────────
@api_bp.route("/recetas/<int:receta_id>/sesion/paso/<int:paso_index>", methods=["GET"])
def obtener_estado_sesion(receta_id: int, paso_index: int):
    """
    GET /api/recetas/<id>/sesion/paso/<paso_index>
    Carga la receta, instancia la máquina de estados, y devuelve el texto, 
    audio y progreso correspondiente a ese índice (0 = ingredientes).
    """
    try:
        from src.database import Database
        from src.state_machine import RecipeSession
        
        db = Database(current_app.config.get("RUTA_DB"))
        receta = db.obtener_receta_completa(receta_id)
        if not receta:
            return jsonify({"error": "Receta no encontrada"}), 404

        sesion = RecipeSession(receta)
        
        if paso_index < 0 or paso_index >= sesion.total_pasos:
            return jsonify({"error": "Índice de paso fuera de rango"}), 400
            
        sesion.paso_actual = paso_index
        acento = request.args.get("acento", "es|com.ar")
        lang, tld = "es", "com.ar"
        if "|" in acento:
            lang, tld = acento.split("|", 1)
        
        return jsonify(sesion.get_current_state(lang=lang, tld=tld)), 200

    except Exception as error:
        return jsonify({"error": str(error)}), 500


# ── FASE 2: Audio Engine ──────────────────────────────────────────────────────
@api_bp.route("/audio/generate", methods=["POST"])
def generar_audio():
    """
    POST /api/audio/generate

    Body JSON: { "texto": "Pelar las manzanas y cortarlas..." }

    Respuesta: { "hash": "<md5>", "url_audio": "/api/audio/<md5>" }
    """
    datos = request.get_json(silent=True)
    if not datos or not datos.get("texto", "").strip():
        return jsonify({"error": "Se esperaba un JSON con el campo 'texto'"}), 400

    texto = datos["texto"].strip()

    try:
        from src.audio_engine import AudioEngine, AudioEngineError
        motor = AudioEngine()
        motor.generate_audio(texto)
        hash_audio = AudioEngine.calcular_hash(texto)
        url_audio  = motor.get_audio_url(hash_audio)
        return jsonify({"hash": hash_audio, "url_audio": url_audio}), 200

    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        # Incluye AudioEngineError (sin conexión, gTTS falla, etc.)
        return jsonify({"error": str(error), "sin_audio": True}), 503


@api_bp.route("/audio/<hash_audio>", methods=["GET"])
def servir_audio(hash_audio: str):
    """
    GET /api/audio/<hash>

    Sirve el archivo .mp3 cacheado correspondiente al hash dado.
    Devuelve 404 si el archivo no existe.
    """
    # Validar que el hash sea hexadecimal (evitar path traversal)
    if not all(c in "0123456789abcdef" for c in hash_audio.lower()) or len(hash_audio) != 32:
        return jsonify({"error": "Hash inválido"}), 400

    try:
        from src.audio_engine import AudioEngine
        motor = AudioEngine()
        ruta_archivo = motor.get_ruta_por_hash(hash_audio)

        if ruta_archivo is None:
            return jsonify({"error": "Audio no encontrado. Generalo primero con POST /api/audio/generate"}), 404

        return send_file(
            ruta_archivo,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name=f"{hash_audio}.mp3",
        )
    except Exception as error:
        return jsonify({"error": f"Error al servir el audio: {error}"}), 500
