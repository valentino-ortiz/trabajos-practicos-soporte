"""
src/state_machine.py — Máquina de estados para la sesión de cocina.

Clase RecipeSession:
  Mantiene el estado de una receta activa mientras el usuario cocina.
  - Sabe en qué paso está (índice).
  - Permite avanzar (next_step), retroceder (prev_step) y reiniciar.
  - Combina los datos de la receta con el AudioEngine para devolver el
    texto y la URL de audio del paso actual.
"""

from typing import Any, Dict, Optional
from deep_translator import GoogleTranslator

from src.audio_engine import AudioEngine


def _traducir(texto: str, lang: str) -> str:
    if not texto or not str(texto).strip() or lang == "es":
        return texto
    try:
        return GoogleTranslator(source='es', target=lang).translate(str(texto))
    except Exception as e:
        print(f"Error traduciendo a {lang}: {e}")
        return texto

class RecipeSession:
    """
    Controla el progreso de lectura de una receta.
    
    Attributes:
        receta: Diccionario con la estructura de la receta (título, pasos, etc.).
        audio_engine: Instancia de AudioEngine para generar la voz.
        paso_actual: Índice del paso actual (0 = lectura de ingredientes, 
                     1 = primer paso de preparación, etc.).
    """

    def __init__(self, receta: Dict[str, Any], audio_engine: Optional[AudioEngine] = None):
        """
        Inicializa la sesión.
        
        Args:
            receta: Diccionario con la receta (debe tener 'titulo', 'ingredientes', 'pasos').
            audio_engine: Motor de audio. Si es None, crea uno nuevo.
        """
        self.receta = receta
        self.audio_engine = audio_engine or AudioEngine()
        
        # Validar estructura básica
        if "titulo" not in self.receta or "pasos" not in self.receta:
            raise ValueError("La receta debe contener 'titulo' y 'pasos'.")
            
        self.paso_actual = 0  # 0 siempre será el resumen/ingredientes
        
        # Total de pasos de la sesión = 1 (ingredientes) + N (pasos de preparación)
        self.total_pasos = 1 + len(self.receta.get("pasos", []))

    def get_current_state(self, lang: str = "es", tld: str = "com.ar") -> Dict[str, Any]:
        """
        Devuelve el estado actual de la sesión, incluyendo el texto a leer
        y la URL del audio generado para este paso.
        """
        texto_original = self._obtener_texto_paso(self.paso_actual)
        
        # Traducir los textos
        texto_a_leer = _traducir(texto_original, lang)
        titulo_traducido = _traducir(self.receta.get("titulo", "Receta"), lang)
        
        ingredientes_traducidos = []
        if self.paso_actual == 0:
            for ing in self.receta.get("ingredientes", []):
                ingredientes_traducidos.append({
                    "cantidad": ing.get("cantidad", ""),
                    "unidad": _traducir(ing.get("unidad", ""), lang) if ing.get("unidad") else "",
                    "nombre": _traducir(ing.get("nombre", ""), lang) if ing.get("nombre") else ""
                })
        
        # Generar o recuperar el audio de caché
        try:
            self.audio_engine.generate_audio(texto_a_leer, lang, tld)
            hash_audio = AudioEngine.calcular_hash(texto_a_leer, lang, tld)
            url_audio = self.audio_engine.get_audio_url(hash_audio)
            error_audio = None
        except Exception as error:
            url_audio = None
            error_audio = str(error)

        return {
            "titulo": titulo_traducido,
            "indice_actual": self.paso_actual,
            "total_pasos": self.total_pasos,
            "es_primero": self.paso_actual == 0,
            "es_ultimo": self.paso_actual == self.total_pasos - 1,
            "texto": texto_a_leer,
            "url_audio": url_audio,
            "error_audio": error_audio,
            "progreso_porcentaje": int((self.paso_actual / max(1, self.total_pasos - 1)) * 100),
            "ingredientes": ingredientes_traducidos
        }

    def next_step(self) -> bool:
        """
        Avanza al siguiente paso.
        
        Returns:
            True si avanzó, False si ya estaba en el último paso.
        """
        if self.paso_actual < self.total_pasos - 1:
            self.paso_actual += 1
            return True
        return False

    def prev_step(self) -> bool:
        """
        Retrocede al paso anterior.
        
        Returns:
            True si retrocedió, False si ya estaba en el primer paso.
        """
        if self.paso_actual > 0:
            self.paso_actual -= 1
            return True
        return False
        
    def reset(self) -> None:
        """Vuelve al primer paso."""
        self.paso_actual = 0

    # ── Métodos privados ───────────────────────────────────────────────────────

    def _obtener_texto_paso(self, indice: int) -> str:
        """
        Construye el texto que gTTS debe leer para un índice dado.
        
        El índice 0 es un resumen de la receta y los ingredientes principales.
        Los índices 1 a N corresponden a los pasos de preparación.
        """
        if indice == 0:
            return self._construir_texto_ingredientes()
            
        # Para pasos de preparación, ajustar el índice (-1 porque el 0 es ingredientes)
        idx_paso = indice - 1
        pasos = self.receta.get("pasos", [])
        
        if 0 <= idx_paso < len(pasos):
            # Agregar muletilla natural antes de leer el paso
            paso_info = pasos[idx_paso]
            num = paso_info.get("numero", idx_paso + 1)
            desc = paso_info.get("descripcion", "")
            return f"Paso {num}. {desc}"
            
        return "Paso no encontrado."

    def _construir_texto_ingredientes(self) -> str:
        """
        Crea un texto amigable y natural para leer los ingredientes.
        Ej: "Vamos a preparar Tarta. Necesitaremos 3 manzanas, 2 huevos..."
        """
        titulo = self.receta.get("titulo", "esta receta")
        ingredientes = self.receta.get("ingredientes", [])
        
        if not ingredientes:
            return f"Vamos a preparar {titulo}. No se detectaron ingredientes específicos. Avanzá al siguiente paso para comenzar."
            
        texto = f"Vamos a preparar {titulo}. Necesitaremos los siguientes ingredientes: "
        
        lista_nombres = []
        for ing in ingredientes:
            # Construir frase del ingrediente ej "200 gramos de harina" o "sal a gusto"
            cant = str(ing.get("cantidad", "")).strip()
            unidad = str(ing.get("unidad", "")).strip()
            nombre = str(ing.get("nombre", "")).strip()
            
            frase = []
            if cant:
                frase.append(cant)
            if unidad:
                frase.append(unidad)
                if nombre:
                    frase.append("de")
            if nombre:
                frase.append(nombre)
                
            lista_nombres.append(" ".join(frase))
            
        # Unir ingredientes con comas y una "y" al final para que suene natural
        if len(lista_nombres) > 1:
            texto += ", ".join(lista_nombres[:-1]) + f" y {lista_nombres[-1]}."
        else:
            texto += lista_nombres[0] + "."
            
        texto += " Cuando tengas todo listo, avanzá al primer paso."
        return texto
