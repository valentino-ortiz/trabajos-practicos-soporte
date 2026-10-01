import os
import subprocess
import sys
import tempfile
import threading

from dotenv import load_dotenv
import speech_recognition as sr
from google import genai
from gtts import gTTS

DIR_PROYECTO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DIR_PROYECTO, ".env"))

WAKE_WORDS   = ["hola", "jarvis", "buenas"]
EXIT_WORDS   = ["chau", "chao", "adiós", "adios", "bye"]
LANGUAGE_STT = "es-AR"
LANGUAGE_TTS = "es"
MODEL        = "gemini-3.8-flash"
MICROPHONE_DEVICE_INDEX = int(os.getenv("MICROPHONE_DEVICE_INDEX", "0"))
MICROPHONE_SAMPLE_RATE = int(os.getenv("MICROPHONE_SAMPLE_RATE", "44100"))


def crear_microfono() -> sr.Microphone:
    return sr.Microphone(
        device_index=MICROPHONE_DEVICE_INDEX,
        sample_rate=MICROPHONE_SAMPLE_RATE,
        chunk_size=1024,
    )

client     = genai.Client()
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.8
recognizer.phrase_threshold = 0.2
recognizer.non_speaking_duration = 0.5
procesando = threading.Lock()
salir      = threading.Event()
stop_listening = None


def hablar(texto: str) -> None:
    tts = gTTS(texto, lang=LANGUAGE_TTS)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        ruta = f.name
        tts.save(ruta)
    subprocess.run(["mpg123", "-q", ruta], stderr=subprocess.DEVNULL)
    os.remove(ruta)


def procesar_pregunta() -> None:
    global stop_listening

    with procesando:
        if stop_listening is not None:
            stop_listening(wait_for_stop=True)

        pregunta = None
        try:
            hablar("Dime")
            with crear_microfono() as mic:
                recognizer.adjust_for_ambient_noise(mic, duration=0.3)
                audio_pregunta = recognizer.listen(
                    mic,
                    timeout=10,
                    phrase_time_limit=20,
                )
                pregunta = recognizer.recognize_google(
                    audio_pregunta,
                    language=LANGUAGE_STT,
                )
                print(f"Pregunta: {pregunta}")
        except sr.UnknownValueError:
            print("No pude entender la pregunta.")
            hablar("No te escuché, intentá de nuevo.")
        except sr.WaitTimeoutError:
            print("No detecté voz durante los diez segundos de espera.")
            hablar("No te escuché, intentá de nuevo.")
        except sr.RequestError as error:
            print(f"Error del servicio de reconocimiento: {error}")

        try:
            if pregunta:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=pregunta,
                )
                hablar(response.text)
        except Exception as error:
            print(f"Error al consultar Gemini con {MODEL}: {error}")
            hablar("No pude consultar al asistente en este momento.")
        finally:
            iniciar_escucha()


def al_detectar_voz(recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
    print(f"Audio detectado ({len(audio.frame_data)} bytes). Reconociendo...")
    try:
        texto = recognizer.recognize_google(audio, language=LANGUAGE_STT).lower()
        print(f"Escuché: {texto}")
    except sr.UnknownValueError:
        print("No entendí ese audio.")
        return
    except sr.RequestError as error:
        print(f"Error del servicio de reconocimiento: {error}")
        return

    if any(w in texto for w in EXIT_WORDS):
        hablar("Hasta luego!")
        salir.set()
        return

    if procesando.locked():
        return

    palabra_detectada = next((w for w in WAKE_WORDS if w in texto), None)
    if not palabra_detectada:
        return

    threading.Thread(target=procesar_pregunta, daemon=True).start()


with crear_microfono() as source:
    sys.stderr = open(os.devnull, "w")
    recognizer.adjust_for_ambient_noise(source, duration=1)
    sys.stderr = sys.__stderr__
    recognizer.energy_threshold = max(100, recognizer.energy_threshold)
    recognizer.dynamic_energy_threshold = False
    print(f"Micrófono listo: índice {MICROPHONE_DEVICE_INDEX}, "
          f"{MICROPHONE_SAMPLE_RATE} Hz, umbral {recognizer.energy_threshold:.0f}")

def iniciar_escucha() -> None:
    global stop_listening
    stop_listening = recognizer.listen_in_background(
        crear_microfono(),
        al_detectar_voz,
        phrase_time_limit=4,
    )


iniciar_escucha()
print("Escuchando. Decí 'hola', 'jarvis' o 'buenas'.")

try:
    salir.wait()
except KeyboardInterrupt:
    pass
finally:
    stop_listening(wait_for_stop=False)
