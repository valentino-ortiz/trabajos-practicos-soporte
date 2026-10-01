"""
src/parser.py — Parser de recetas de ChefVoz.

Clase RecipeParser con dos métodos públicos:
  - parse_text(texto: str) → dict
  - parse_url(url: str) → dict

Usa heurísticas y expresiones regulares. No requiere NLP pesado.
Comentarios, variables y docstrings en español según las reglas del proyecto.
"""

import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup


# ── Constantes de regex ────────────────────────────────────────────────────────
# Unidades de medida aceptadas en la detección de ingredientes
_UNIDADES = (
    r"gramos?|gr?|kg|kilos?|ml|mililitros?|l|litros?|"
    r"tazas?|cdas?|cucharadas?|cditas?|cucharaditas?|"
    r"unidades?|uds?|dientes?|ramas?|pizcas?|"
    r"latas?|paquetes?|potes?"
)

# Detecta una cantidad al inicio: 3 / 1.5 / 1/2 / ¼ etc. seguida de unidad opcional
_RE_CANTIDAD = re.compile(
    rf"^(?P<cant>\d+(?:[.,]\d+)?|\d+\s*/\s*\d+)?\s*"
    rf"(?P<unidad>{_UNIDADES})?\.?\s*(?:de\s+)?(?P<nombre>.+)$",
    re.IGNORECASE,
)

# Detecta cabecera de sección como "Ingredientes:" o "Preparación"
_ENCABEZADOS_INGREDIENTES = re.compile(
    r"^ingredientes?\s*:?\s*$", re.IGNORECASE
)
_ENCABEZADOS_PASOS = re.compile(
    r"^(preparaci[oó]n|pasos?|instrucciones?|procedimiento|"
    r"elaboraci[oó]n|c[oó]mo\s+(?:se\s+)?hac\w+)\s*:?\s*$",
    re.IGNORECASE,
)

# Detecta "Paso 3:" o "3." o "3)" o "3" pegado al texto al inicio de una línea
_RE_NUM_PASO = re.compile(r"^(?:paso\s*)?\d+[\.\-\):\s]*", re.IGNORECASE)

# Detecta viñetas de lista al inicio de línea
_RE_VINETA = re.compile(r"^[\-\*\•\·]\s*")

# Detecta menciones de tiempo (para estimar duración)
_RE_MINUTOS = re.compile(r"(\d+)\s*(?:a\s*\d+\s*)?(?:minutos?|mins?\.?)\b", re.IGNORECASE)
_RE_HORAS   = re.compile(r"(\d+)\s*(?:a\s*\d+\s*)?(?:horas?|hs?\.?)\b", re.IGNORECASE)


class RecipeParser:
    """
    Parsea recetas desde texto libre o desde una URL web.

    Estrategia de detección:
    1. La primera línea no vacía y no-sección es el título.
    2. Las líneas bajo "Ingredientes:" se clasifican como ingredientes.
    3. Las líneas bajo "Preparación:" / "Pasos:" se clasifican como pasos.
    4. Si no hay cabecera explícita, se usa heurística: líneas cortas
       con cantidad detectada → ingredientes; líneas largas → pasos.
    """

    # ── API pública ────────────────────────────────────────────────────────────

    def parse_text(self, texto: str) -> Dict[str, Any]:
        """
        Analiza un texto libre de receta.

        Args:
            texto: Texto completo de la receta (puede incluir saltos de línea).

        Returns:
            Dict con claves ``titulo``, ``ingredientes`` y ``pasos``.
            ``ingredientes`` es lista de dicts: nombre, cantidad, unidad, orden.
            ``pasos`` es lista de dicts: numero, descripcion, duracion_estimada_seg.
        """
        lineas = self._limpiar_lineas(texto)

        titulo      = self._extraer_titulo(lineas)
        ingredientes, pasos = self._clasificar_lineas(lineas, titulo)

        # Fallback: si no hay pasos, las líneas largas clasificadas como
        # ingredientes sin cantidad se promuevan a pasos
        if not pasos:
            ingredientes, pasos = self._fallback_heuristico(ingredientes)

        return {
            "titulo":       titulo,
            "ingredientes": ingredientes,
            "pasos":        pasos,
        }

    def parse_url(self, url: str) -> Dict[str, Any]:
        """
        Descarga una página web de receta y la parsea.

        Intenta primero extraer ingredientes/pasos con selectores semánticos
        (listas HTML marcadas con palabras clave). Si falla, extrae el texto
        visible completo y llama a parse_text().

        Args:
            url: URL completa de la página de receta.

        Returns:
            Dict igual al de parse_text() con campos adicionales
            ``fuente`` y ``url``.

        Raises:
            No lanza excepciones al usuario: en caso de error devuelve un
            dict con título de error y un paso descriptivo del problema.
        """
        try:
            sopa = self._descargar_html(url)
        except Exception as error:
            return self._resultado_error(url, str(error))

        try:
            titulo     = self._titulo_desde_sopa(sopa)
            texto_base = self._texto_desde_sopa(sopa, titulo)
            resultado  = self.parse_text(texto_base)
            if titulo:
                resultado["titulo"] = titulo
        except Exception as error:
            return self._resultado_error(url, str(error))

        resultado["fuente"] = "web"
        resultado["url"]    = url
        return resultado

    # ── Métodos privados: carga ────────────────────────────────────────────────

    def _descargar_html(self, url: str) -> BeautifulSoup:
        """Descarga la URL y devuelve un objeto BeautifulSoup."""
        cabeceras = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
        respuesta = requests.get(url, headers=cabeceras, timeout=10)
        respuesta.raise_for_status()
        return BeautifulSoup(respuesta.text, "html.parser")

    def _titulo_desde_sopa(self, sopa: BeautifulSoup) -> str:
        """Extrae el título desde el <h1> de la página."""
        h1 = sopa.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    def _texto_desde_sopa(self, sopa: BeautifulSoup, titulo: str) -> str:
        """
        Construye un texto plano estructurado a partir del HTML.

        Intenta primero extraer datos de schema.org (JSON-LD).
        Luego intenta encontrar listas semánticas de ingredientes/pasos.
        Si no las encuentra, devuelve el texto visible completo de la página.
        """
        # 1. Intentar Schema.org (JSON-LD)
        import json
        for script in sopa.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    # Algunos sitios tienen una lista en @type
                    tipo = item.get("@type")
                    if tipo == "Recipe" or (isinstance(tipo, list) and "Recipe" in tipo):
                        ingredientes = item.get("recipeIngredient", [])
                        instrucciones = item.get("recipeInstructions", [])
                        
                        # Si el sitio engaña (tiene Schema.org pero sin pasos, como Paulina Cocina), ignorar
                        if not instrucciones or not ingredientes:
                            continue
                        
                        partes = [item.get("name") or titulo or "Receta Web", "", "Ingredientes:"]
                        if isinstance(ingredientes, list):
                            partes += [f"- {it}" for it in ingredientes]
                        else:
                            partes.append(f"- {ingredientes}")
                        
                        partes += ["", "Preparación:"]
                        if isinstance(instrucciones, list):
                            for i, it in enumerate(instrucciones, 1):
                                text = it.get("text") if isinstance(it, dict) else str(it)
                                # Limpiar etiquetas HTML residuales en el JSON
                                text = BeautifulSoup(text, "html.parser").get_text(strip=True)
                                partes.append(f"Paso {i}: {text}")
                        else:
                            partes.append(f"Paso 1: {instrucciones}")
                        
                        return "\n".join(partes)
            except Exception:
                continue

        # 2. Eliminar ruido de la página y buscar HTML semántico
        for etiqueta in sopa(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "svg", "button", "noscript"]):
            etiqueta.decompose()

        # Eliminar también secciones de comentarios por clase/id
        for etiqueta in sopa.find_all(lambda tag: 
            (tag.has_attr('id') and any(k in tag['id'].lower() for k in ['comment', 'comentario'])) or
            (tag.has_attr('class') and any(k in c.lower() for c in tag['class'] for k in ['comment', 'comentario']))
        ):
            etiqueta.decompose()

        # 3. Barrido secuencial inteligente (párrafos y listas) hasta chocar con el final del artículo
        regex_fin = re.compile(r"comentario|relacionad|suscrib|recomend|votar|evidencia|te puede|sugerencia|compartir|newsletter", re.IGNORECASE)
        lineas_limpias = []
        vistas = set()

        for nodo in sopa.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
            texto = nodo.get_text(strip=True)
            if not texto or len(texto) < 3:
                continue

            # Freno de mano: si encontramos un título de "fin de receta", dejamos de leer la página
            if nodo.name.startswith("h") and regex_fin.search(texto):
                break

            # Evitar palabras sueltas de spam
            l_lower = texto.lower()
            spam = {"compartir", "compartir en x", "copiar link", "link copiado.", "me gusta"}
            if l_lower in spam or any(k in l_lower for k in ["compartir en", "más recetas de", "¡hola! soy"]):
                continue

            # Deduplicador
            if l_lower in vistas:
                continue

            vistas.add(l_lower)
            lineas_limpias.append(texto)

        return "\n".join(lineas_limpias)

    def _buscar_lista_html(self, sopa: BeautifulSoup, patron_kw: str) -> List[str]:
        """
        Busca listas <ul>/<ol> cuyo contexto (id, clase o texto de padre)
        contenga alguna de las palabras del patrón dado.

        Returns:
            Lista de textos de los <li> encontrados.
        """
        regex_kw = re.compile(patron_kw, re.IGNORECASE)
        items: List[str] = []

        for lista in sopa.find_all(["ul", "ol"]):
            padre = lista.parent
            
            # Buscar el encabezado más cercano antes de la lista
            encabezado = ""
            prev = lista.find_previous(["h2", "h3", "h4", "strong"])
            if prev:
                encabezado = prev.get_text()
                
            contexto = " ".join([
                " ".join(padre.get("class") or []),
                padre.get("id") or "",
                " ".join(lista.get("class") or []),
                lista.get("id") or "",
                encabezado
            ])
            if regex_kw.search(contexto):
                for li in lista.find_all("li"):
                    texto = li.get_text(strip=True)
                    if texto:
                        items.append(texto)
                if items:
                    return items
        return items

    # ── Métodos privados: parseo de texto ──────────────────────────────────────

    def _limpiar_lineas(self, texto: str) -> List[str]:
        """Devuelve las líneas del texto sin blancos ni separadores decorativos."""
        resultado = []
        for linea in texto.splitlines():
            limpia = linea.strip()
            # Descartar líneas que son solo guiones, asteriscos, etc.
            if limpia and not re.fullmatch(r"[-=_*#]{3,}", limpia):
                resultado.append(limpia)
        return resultado

    def _extraer_titulo(self, lineas: List[str]) -> str:
        """Devuelve la primera línea que no sea un encabezado de sección."""
        for linea in lineas:
            if not _ENCABEZADOS_INGREDIENTES.match(linea) and not _ENCABEZADOS_PASOS.match(linea):
                return linea
        return "Receta Sin Título"

    def _clasificar_lineas(
        self, lineas: List[str], titulo: str
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Recorre las líneas y las asigna a ingredientes o pasos según
        la sección detectada (estado de máquina de estados simple).
        """
        ingredientes: List[Dict[str, Any]] = []
        pasos:        List[Dict[str, Any]] = []

        # Estado inicial: antes de cualquier sección, asumimos ingredientes
        # si el texto no tiene cabecera explícita.
        hay_cabecera_explicita = any(
            _ENCABEZADOS_INGREDIENTES.match(l) or _ENCABEZADOS_PASOS.match(l)
            for l in lineas
        )
        seccion_actual = "ingredientes" if not hay_cabecera_explicita else None

        orden = 1
        num_paso = 1

        for linea in lineas:
            # Saltar el título
            if linea == titulo:
                continue

            # ¿Es un encabezado de sección?
            if _ENCABEZADOS_INGREDIENTES.match(linea):
                seccion_actual = "ingredientes"
                continue
            if _ENCABEZADOS_PASOS.match(linea):
                seccion_actual = "pasos"
                continue

            # Sin sección definida (texto antes de cualquier cabecera)
            if seccion_actual is None:
                continue

            if seccion_actual == "ingredientes":
                ing = self._parsear_ingrediente(linea, orden)
                if ing:
                    ingredientes.append(ing)
                    orden += 1

            elif seccion_actual == "pasos":
                paso = self._parsear_paso(linea, num_paso)
                if paso:
                    pasos.append(paso)
                    num_paso += 1

        return ingredientes, pasos

    def _parsear_ingrediente(
        self, linea: str, orden: int
    ) -> Optional[Dict[str, Any]]:
        """
        Extrae cantidad, unidad y nombre de un ingrediente a partir de una línea.

        Returns:
            Dict del ingrediente o None si la línea está vacía.
        """
        # Quitar viñetas
        linea = _RE_VINETA.sub("", linea).strip()
        if not linea:
            return None

        match = _RE_CANTIDAD.match(linea)
        if match:
            cantidad = (match.group("cant") or "").strip()
            unidad   = (match.group("unidad") or "").strip()
            nombre   = (match.group("nombre") or "").strip()
            # Si el nombre quedó vacío pero sí hay cantidad, usar línea completa como nombre
            if not nombre:
                nombre   = linea
                cantidad = ""
                unidad   = ""
        else:
            cantidad = ""
            unidad   = ""
            nombre   = linea

        return {"nombre": nombre, "cantidad": cantidad, "unidad": unidad, "orden": orden}

    def _parsear_paso(
        self, linea: str, numero: int
    ) -> Optional[Dict[str, Any]]:
        """
        Extrae la descripción de un paso, quitando numeración al inicio.

        Returns:
            Dict del paso o None si la línea está vacía.
        """
        # Quitar "Paso 2:" / "2." / "2)" del inicio
        descripcion = _RE_NUM_PASO.sub("", linea).strip()
        if not descripcion:
            return None

        return {
            "numero":                 numero,
            "descripcion":            descripcion,
            "duracion_estimada_seg":  self._estimar_duracion(descripcion),
        }

    def _fallback_heuristico(
        self, ingredientes: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Si no se detectaron pasos, clasifica como paso toda línea-ingrediente
        que tenga más de 40 caracteres y ninguna cantidad detectada.
        """
        ing_filtrados: List[Dict[str, Any]] = []
        pasos: List[Dict[str, Any]] = []
        num_paso = 1

        for ing in ingredientes:
            if len(ing["nombre"]) > 40 and not ing["cantidad"]:
                pasos.append({
                    "numero":                num_paso,
                    "descripcion":           ing["nombre"],
                    "duracion_estimada_seg": self._estimar_duracion(ing["nombre"]),
                })
                num_paso += 1
            else:
                ing_filtrados.append(ing)

        return ing_filtrados, pasos

    # ── Métodos privados: utilidades ───────────────────────────────────────────

    @staticmethod
    def _estimar_duracion(texto: str) -> int:
        """
        Estima la duración en segundos basándose en menciones de tiempo en el texto.

        Ejemplos: "45 minutos" → 2700, "1 hora" → 3600, sin mención → 0.
        """
        m_min = _RE_MINUTOS.search(texto)
        if m_min:
            return int(m_min.group(1)) * 60

        m_hora = _RE_HORAS.search(texto)
        if m_hora:
            return int(m_hora.group(1)) * 3600

        return 0

    @staticmethod
    def _resultado_error(url: str, mensaje_error: str) -> Dict[str, Any]:
        """Devuelve un dict estándar de error para parse_url()."""
        return {
            "titulo":       "Error al extraer la receta",
            "ingredientes": [],
            "pasos": [
                {
                    "numero":                1,
                    "descripcion":           f"No se pudo procesar la URL. Detalle: {mensaje_error}",
                    "duracion_estimada_seg": 0,
                }
            ],
            "fuente": "error",
            "url":    url,
        }
