"""
src/audio_engine.py — Motor de síntesis de voz de ChefVoz.

Clase AudioEngine:
  - generate_audio(texto) → str (ruta del .mp3 generado o cacheado)
  - get_audio_url(hash_audio) → str (URL relativa para servir desde Flask)

Estrategia de caché:
  - Nombre del archivo = MD5(texto).mp3
  - Si el archivo ya existe en cache/, se devuelve sin regenerar.
  - Limpieza opcional de archivos más viejos que MAX_DIAS_CACHE.

Manejo de errores:
  - Sin internet o falla de gTTS → lanza AudioEngineError con mensaje claro.
"""

import hashlib
import os
import time
from typing import Optional

import config


# ── Excepción personalizada ────────────────────────────────────────────────────

class AudioEngineError(Exception):
    """Error del motor de síntesis de voz."""


# ── Clase principal ────────────────────────────────────────────────────────────

class AudioEngine:
    """
    Motor de síntesis de voz basado en gTTS con caché local de archivos MP3.

    Attributes:
        dir_cache: Directorio donde se almacenan los archivos de audio.
        idioma: Código de idioma para gTTS (por defecto 'es').
        lento: Si es True, gTTS habla más despacio.
    """

    def __init__(
        self,
        dir_cache: Optional[str] = None,
        idioma: str = config.IDIOMA_TTS,
        lento: bool = config.TTS_LENTO,
    ) -> None:
        """
        Inicializa el AudioEngine.

        Args:
            dir_cache: Ruta al directorio de caché. Si es None usa config.DIR_CACHE_AUDIO.
            idioma: Código de idioma para gTTS (ej: 'es', 'en').
            lento: Si True, genera voz más lenta (mejor para instrucciones de cocina).
        """
        self.dir_cache = dir_cache or config.DIR_CACHE_AUDIO
        self.idioma = idioma
        self.lento = lento

        # Asegurar que el directorio de caché exista
        os.makedirs(self.dir_cache, exist_ok=True)

    # ── API pública ────────────────────────────────────────────────────────────

    def generate_audio(self, texto: str, lang: str = "es", tld: str = "com.ar") -> str:
        """
        Genera audio en MP3 para el texto dado usando gTTS.

        Si ya existe un archivo cacheado para ese texto, lo devuelve directamente
        sin volver a llamar a la API de Google.

        Args:
            texto: Texto a sintetizar en voz.

        Returns:
            Ruta absoluta al archivo .mp3 generado o cacheado.

        Raises:
            AudioEngineError: Si gTTS falla (sin conexión, texto vacío, etc.).
            ValueError: Si el texto está vacío.
        """
        texto = texto.strip()
        if not texto:
            raise ValueError("El texto para síntesis de voz no puede estar vacío.")

        texto_fonetico = self.normalizar_texto(texto)
        hash_audio = self.calcular_hash(texto, lang, tld)
        ruta_archivo = self._ruta_archivo(hash_audio)

        # ── Caché hit: el archivo ya existe ───────────────────────────────────
        if os.path.exists(ruta_archivo) and os.path.getsize(ruta_archivo) > 0:
            return ruta_archivo

        # ── Caché miss: generar con gTTS ──────────────────────────────────────
        self._generar_con_gtts(texto_fonetico, ruta_archivo, lang, tld)
        return ruta_archivo

    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """
        Traduce abreviaturas comunes de cocina a palabras completas 
        para mejorar la lectura fonética de gTTS.
        """
        import re
        reemplazos = [
            (r'\b0000\b', 'cuatro ceros'),
            (r'\b000\b', 'tres ceros'),
            (r'\b00\b', 'dos ceros'),
            (r'\bgr\b|\bgrs\b', 'gramos'),
            (r'\bkg\b|\bkgs\b', 'kilos'),
            (r'\bml\b', 'mililitros'),
            (r'\bcc\b', 'centímetros cúbicos'),
            (r'\bc/n\b', 'cantidad necesaria'),
            (r'\bcdita\.?|\bcditas\.?', 'cucharadita'),
            (r'\bcda\.?|\bcdas\.?', 'cucharada'),
            (r'\bcm\b', 'centímetros')
        ]
        texto_norm = texto
        for patron, reemplazo in reemplazos:
            texto_norm = re.sub(patron, reemplazo, texto_norm, flags=re.IGNORECASE)
        
        return texto_norm

    def get_audio_url(self, hash_audio: str) -> str:
        """
        Devuelve la URL relativa para servir un archivo de audio desde Flask.

        Args:
            hash_audio: Hash MD5 del texto (sin extensión).

        Returns:
            URL relativa, ej: '/api/audio/abc123def456'
        """
        return f"/api/audio/{hash_audio}"

    @classmethod
    def calcular_hash(cls, texto: str, lang: str = "es", tld: str = "com.ar") -> str:
        """
        Calcula el hash MD5 del texto NORMALIZADO + IDIOMA + TLD.

        Args:
            texto: Texto crudo a hashear.
            lang: Código del idioma.
            tld: Acento (Top Level Domain de Google).

        Returns:
            String hexadecimal del MD5.
        """
        texto_fonetico = cls.normalizar_texto(texto)
        combo = f"{texto_fonetico.strip()}|{lang.strip()}|{tld.strip()}"
        return hashlib.md5(combo.encode("utf-8")).hexdigest()

    def get_ruta_por_hash(self, hash_audio: str) -> Optional[str]:
        """
        Devuelve la ruta al archivo de audio si existe en caché.

        Args:
            hash_audio: Hash MD5 del texto.

        Returns:
            Ruta absoluta al archivo .mp3 o None si no existe.
        """
        ruta = self._ruta_archivo(hash_audio)
        return ruta if os.path.exists(ruta) else None

    def limpiar_cache_viejo(self, max_dias: int = config.MAX_DIAS_CACHE) -> int:
        """
        Elimina archivos de audio más antiguos que ``max_dias`` días.

        Args:
            max_dias: Días máximos de antigüedad. 0 = no limpiar.

        Returns:
            Número de archivos eliminados.
        """
        if max_dias <= 0:
            return 0

        umbral = time.time() - (max_dias * 86400)
        eliminados = 0

        try:
            for nombre_archivo in os.listdir(self.dir_cache):
                if not nombre_archivo.endswith(config.EXTENSION_AUDIO):
                    continue
                ruta = os.path.join(self.dir_cache, nombre_archivo)
                if os.path.getmtime(ruta) < umbral:
                    os.remove(ruta)
                    eliminados += 1
        except OSError as error:
            # No interrumpir la app si la limpieza falla
            print(f"[AudioEngine] Advertencia al limpiar caché: {error}")

        return eliminados

    # ── Métodos privados ───────────────────────────────────────────────────────

    def _calcular_hash(self, texto: str) -> str:
        """Calcula el hash MD5 del texto para nombrar el archivo cacheado."""
        return hashlib.md5(texto.encode("utf-8")).hexdigest()

    def _ruta_archivo(self, hash_audio: str) -> str:
        """Devuelve la ruta completa al archivo .mp3 según su hash."""
        return os.path.join(self.dir_cache, f"{hash_audio}{config.EXTENSION_AUDIO}")

    def _generar_con_gtts(self, texto: str, ruta_destino: str, lang: str = "es", tld: str = "com.ar") -> None:
        """
        Llama a gTTS para sintetizar el texto y guarda el resultado en disco.

        Args:
            texto: Texto a sintetizar.
            ruta_destino: Ruta donde guardar el archivo .mp3.

        Raises:
            AudioEngineError: Si gTTS falla por cualquier motivo
                              (sin internet, texto inválido, etc.).
        """
        try:
            # Importación diferida: gTTS puede no estar disponible en todos los entornos
            from gtts import gTTS
            from gtts.tts import gTTSError

            # Usamos el idioma y tld proporcionados
            tts = gTTS(text=texto, lang=lang, tld=tld, slow=self.lento)
            tts.save(ruta_destino)

        except ImportError:
            raise AudioEngineError(
                "La librería gTTS no está instalada. "
                "Ejecutá: pip install gTTS"
            )
        except Exception as error:
            # Eliminar archivo parcial si quedó algo en disco
            if os.path.exists(ruta_destino):
                try:
                    os.remove(ruta_destino)
                except OSError:
                    pass

            # Distinguir errores comunes para dar mensajes claros
            mensaje = str(error).lower()
            if "network" in mensaje or "connection" in mensaje or "failed" in mensaje:
                raise AudioEngineError(
                    "No se pudo generar el audio: sin conexión a internet. "
                    "Verificá tu conexión y volvé a intentarlo."
                ) from error
            raise AudioEngineError(
                f"Error al generar el audio con gTTS: {error}"
            ) from error
