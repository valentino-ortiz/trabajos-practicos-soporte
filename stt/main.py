#!/usr/bin/env python3
"""
Procesador de voz universal
---------------------------
Graba o carga un audio, lo transcribe con Whisper, y genera:
- Resumen extractivo
- Traducción a otro idioma
- Archivo de salida con transcripción, resumen y traducción
- Opción de copiar al portapapeles o leer en voz alta

Uso:
    python procesador_voz.py

Comandos:
    - Presionar F5 para iniciar/detener grabación (modo micrófono)
    - En el menú, elegir 'cargar archivo' para procesar un audio existente
    - Después de la transcripción, elegir acciones adicionales
"""

import os
import sys
import queue
import re
import threading
import tempfile
import wave
import time
from collections import Counter
from urllib.parse import quote
import webbrowser

import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from pynput.keyboard import Controller, Key
from deep_translator import GoogleTranslator
from gtts import gTTS

# Detectar plataforma para elegir motor de Whisper
IS_MAC = sys.platform == "darwin"
if IS_MAC:
    os.environ.setdefault("HF_HOME", os.path.expanduser("~/AI"))
    import mlx_whisper
else:
    from faster_whisper import WhisperModel

# Configuración
SAMPLE_RATE = 16000
HOTKEY = keyboard.Key.f5
MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo" if IS_MAC else "small")
LANG = os.environ.get("WHISPER_LANG") or "es"   # idioma de origen (para transcripción)
DEST_LANG = "en"                                # idioma destino para traducción

# Inicializar teclado virtual
_kbd = Controller()

# Cola para audio en grabación
_frames = queue.Queue()
recording = False
_lock = threading.Lock()

# ----------------------------------------------------------------------
# Funciones de grabación (igual que en el grupo 3)
# ----------------------------------------------------------------------
def _callback(indata, frames, time, status):
    if recording:
        _frames.put(indata.copy())

def toggle_recording():
    global recording
    if not recording:
        while not _frames.empty():
            _frames.get()
        recording = True
        print("● Grabando... (presiona F5 otra vez para detener)")
        return
    recording = False
    print("■ Detenido, transcribiendo...")
    chunks = []
    while not _frames.empty():
        chunks.append(_frames.get())
    if not chunks:
        print("(sin audio)")
        return None
    audio = np.concatenate(chunks).flatten().astype(np.float32)
    return audio

def _toggle_locked():
    if not _lock.acquire(blocking=False):
        print("… ocupado, esperá a que termine.")
        return
    try:
        audio = toggle_recording()
        if audio is not None:
            text = transcribir(audio)
            if text:
                procesar_texto(text)
    finally:
        _lock.release()

# ----------------------------------------------------------------------
# Transcripción con Whisper (según plataforma)
# ----------------------------------------------------------------------
def transcribir(audio):
    """Transcribe audio (numpy array) y devuelve texto."""
    if IS_MAC:
        result = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, language=LANG)
        return result["text"].strip()
    else:
        # faster-whisper espera ruta de archivo, guardamos temporal
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes((audio * 32767).astype(np.int16).tobytes())
            tmp_path = tmp.name
        try:
            model = WhisperModel(MODEL, device="cpu", compute_type="int8")
            segments, _ = model.transcribe(tmp_path, language=LANG)
            text = "".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)
        return text

# ----------------------------------------------------------------------
# Resumen extractivo (basado en frecuencia de palabras, similar al grupo 9)
# ----------------------------------------------------------------------
def resumir(texto, cantidad_oraciones=3):
    oraciones = re.split(r'(?<=[.!?])\s+', texto.strip())
    if len(oraciones) <= cantidad_oraciones:
        return texto
    palabras = re.findall(r'\w+', texto.lower())
    frecuencias = Counter(palabras)
    puntajes = []
    for oracion in oraciones:
        palabras_oracion = re.findall(r'\w+', oracion.lower())
        puntaje = sum(frecuencias[p] for p in palabras_oracion)
        puntajes.append((puntaje, oracion))
    mejores = sorted(puntajes, key=lambda x: x[0], reverse=True)[:cantidad_oraciones]
    orden_original = [o for _, o in sorted(mejores, key=lambda x: oraciones.index(x[1]))]
    return " ".join(orden_original)

# ----------------------------------------------------------------------
# Traducción (con deep_translator)
# ----------------------------------------------------------------------
def traducir(texto, destino=DEST_LANG, origen=LANG):
    if not texto:
        return ""
    try:
        traductor = GoogleTranslator(source=origen, target=destino)
        return traductor.translate(texto)
    except Exception as e:
        print(f"Error en traducción: {e}")
        return ""

# ----------------------------------------------------------------------
# Texto a voz (gTTS)
# ----------------------------------------------------------------------
def hablar(texto, idioma=DEST_LANG):
    if not texto:
        return
    try:
        tts = gTTS(text=texto, lang=idioma)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        tts.save(tmp_path)
        # Reproducir con el reproductor por defecto (solo en macOS/Linux/Windows)
        if sys.platform == "darwin":
            os.system(f"afplay {tmp_path}")
        elif sys.platform.startswith("linux"):
            os.system(f"mpg123 {tmp_path} 2>/dev/null")
        elif sys.platform == "win32":
            os.system(f"start {tmp_path}")
        else:
            print(f"Audio guardado en {tmp_path}")
        # Esperar un poco y luego borrar (opcional)
        time.sleep(2)
        os.unlink(tmp_path)
    except Exception as e:
        print(f"No se pudo reproducir: {e}")

# ----------------------------------------------------------------------
# Acciones sobre el texto (copiar, buscar en Google, guardar archivo)
# ----------------------------------------------------------------------
def copiar(texto):
    pyperclip.copy(texto)
    print("✔ Texto copiado al portapapeles")

def buscar_google(query):
    url = f"https://www.google.com/search?q={quote(query)}"
    webbrowser.open(url)
    print(f"🔎 Buscando en Google: {query}")

def guardar_resultado(transcripcion, resumen, traduccion, nombre_base=None):
    if not nombre_base:
        nombre_base = f"transcripcion_{int(time.time())}"
    with open(f"{nombre_base}.txt", "w", encoding="utf-8") as f:
        f.write("=== TRANSCRIPCIÓN ===\n")
        f.write(transcripcion + "\n\n")
        f.write("=== RESUMEN ===\n")
        f.write(resumen + "\n\n")
        f.write("=== TRADUCCIÓN (al inglés) ===\n")
        f.write(traduccion + "\n")
    print(f"📁 Archivo guardado: {nombre_base}.txt")

# ----------------------------------------------------------------------
# Procesamiento principal: dado el texto, muestra opciones
# ----------------------------------------------------------------------
def procesar_texto(texto):
    if not texto:
        print("No se detectó texto.")
        return
    print(f"\n📝 Transcripción: {texto!r}")

    # Generar resumen y traducción automáticamente
    resumen = resumir(texto)
    traduccion = traducir(texto)

    print("\n--- RESUMEN ---")
    print(resumen)
    print("\n--- TRADUCCIÓN ---")
    print(traduccion)

    # Menú de acciones
    while True:
        print("\nOpciones:")
        print("  [c] Copiar transcripción al portapapeles")
        print("  [r] Copiar resumen")
        print("  [t] Copiar traducción")
        print("  [g] Buscar en Google la transcripción")
        print("  [s] Guardar todo en archivo")
        print("  [v] Escuchar traducción (voz)")
        print("  [q] Salir (volver al menú principal)")
        op = input("Elegí una opción: ").strip().lower()
        if op == "c":
            copiar(texto)
        elif op == "r":
            copiar(resumen)
        elif op == "t":
            copiar(traduccion)
        elif op == "g":
            buscar_google(texto)
        elif op == "s":
            guardar_resultado(texto, resumen, traduccion)
        elif op == "v":
            hablar(traduccion)
        elif op == "q":
            break
        else:
            print("Opción no válida")

# ----------------------------------------------------------------------
# Función para procesar un archivo de audio
# ----------------------------------------------------------------------
def procesar_archivo(ruta_archivo):
    # Leer el archivo de audio y convertirlo a array numpy (16kHz mono)
    try:
        import soundfile as sf  # para leer archivos de audio fácilmente
        audio, sr = sf.read(ruta_archivo)
        if sr != SAMPLE_RATE:
            # Re-muestrear (simple, solo para demostración)
            import scipy.signal
            audio = scipy.signal.resample(audio, int(len(audio) * SAMPLE_RATE / sr))
            sr = SAMPLE_RATE
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # stereo a mono
        audio = audio.astype(np.float32)
    except ImportError:
        # Si no tiene soundfile, usar alternativa con ffmpeg (simplificado)
        print("Instalá 'soundfile' o 'scipy' para leer archivos. Usando ffmpeg...")
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        cmd = ["ffmpeg", "-i", ruta_archivo, "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "wav", tmp_path, "-y"]
        subprocess.run(cmd, check=True, capture_output=True)
        with wave.open(tmp_path, "rb") as wf:
            data = wf.readframes(wf.getnframes())
            audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767.0
        os.unlink(tmp_path)

    texto = transcribir(audio)
    if texto:
        procesar_texto(texto)

# ----------------------------------------------------------------------
# Menú principal
# ----------------------------------------------------------------------
def menu_principal():
    print("\n" + "="*50)
    print("  PROCESADOR DE VOZ UNIVERSAL")
    print("="*50)
    print("1. Grabar desde micrófono (con F5)")
    print("2. Cargar archivo de audio")
    print("3. Salir")
    return input("Elegí una opción: ").strip()

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    print(f"Plataforma: {'macOS (MLX)' if IS_MAC else sys.platform + ' (faster-whisper)'}")
    print(f"Modelo Whisper: {MODEL}")
    print(f"Idioma origen: {LANG}, destino: {DEST_LANG}")
    print("Presioná F5 para empezar/detener grabación (en modo 1).")
    print("Ctrl+C para salir en cualquier momento.")

    # Iniciar listener de teclado para hotkey (siempre activo)
    def on_press(key):
        if key == HOTKEY:
            threading.Thread(target=_toggle_locked, daemon=True).start()

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

    # Iniciar stream de audio (siempre escuchando para grabar cuando se active)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=_callback):
        while True:
            opcion = menu_principal()
            if opcion == "1":
                print("Modo grabación: presioná F5 para iniciar y otra vez para detener.")
                input("Presioná ENTER cuando hayas terminado de grabar (o presioná F5)...")
                # El audio se procesa automáticamente al soltar F5 (en _toggle_locked)
                # Pero si no se presionó F5, no pasa nada.
                # Para simplificar, en este modo el usuario debe presionar F5.
                # Podríamos esperar aquí hasta que se procese algo.
                print("Esperando grabación... (presioná F5 dos veces)")
                # Esperar un poco y volver al menú
                time.sleep(1)
            elif opcion == "2":
                ruta = input("Ruta del archivo de audio: ").strip()
                if os.path.exists(ruta):
                    procesar_archivo(ruta)
                else:
                    print("Archivo no encontrado.")
            elif opcion == "3":
                print("👋 ¡Hasta luego!")
                break
            else:
                print("Opción no válida.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Salida por Ctrl+C")
        sys.exit(0)