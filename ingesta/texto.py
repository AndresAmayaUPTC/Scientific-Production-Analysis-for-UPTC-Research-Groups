"""Utilidades de texto compartidas por el backend y la ingesta.

Viven aparte para que el scraper y el lector de Excel apliquen exactamente la
misma normalización: si cambia la forma de sacar el año de un registro, cambia
en un solo sitio y ambos caminos quedan consistentes.
"""
import re
from collections import Counter
from datetime import date

# Coordenadas de las ciudades presentes en los datos, para el mapa.
# La clave se compara sin tildes y en mayúsculas (ver coords_de).
CIUDAD_COORDS = {
    "BOYACA - TUNJA": (5.5353, -73.3678),
    "BOYACA - DUITAMA": (5.8245, -73.0345),
    "BOYACA - SOGAMOSO": (5.7145, -72.9339),
    "BOYACA - CHIQUINQUIRA": (5.6144, -73.8181),
    "BOGOTA, D. C. - BOGOTA, D.C.": (4.7110, -74.0721),
    "VALLE DEL CAUCA - CALI": (3.4516, -76.5320),
    "ATLANTICO - BARRANQUILLA": (10.9685, -74.7813),
}

_TILDES = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def _norm_txt(v):
    if v is None:
        return ""
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return "" if s.lower() in ("nan", "-", "none") else s


def _norm_clas(v):
    v = _norm_txt(v)
    if not v:
        return "Sin clasificar"
    return v.split()[0].strip().upper()


def _coords_de(ciudad):
    clave = _norm_txt(ciudad).translate(_TILDES).upper()
    return CIUDAD_COORDS.get(clave)


# El año de publicación viene embebido en el texto, casi siempre justo
# después del ISSN ("... ISSN: 2214-7853, 2020 vol:33 ..."). Se prueban
# varios patrones de más a menos fiable; 0 significa "año desconocido".
# Cada formato guarda el año en un sitio distinto:
#  - artículos: después del ISSN  -> "... ISSN: 2214-7853, 2020 vol:33 ..."
#  - libros y capítulos: antes del ISBN -> "... Colombia, 2015, ISBN: 3659081485 ..."
# Un patrón que leía dígitos DESPUÉS del ISBN se descartó: capturaba trozos
# del propio código (77 de sus 99 capturas daban años imposibles).
_ANIO_PATRONES = [
    re.compile(r"ISSN:\s*[0-9Xx\-]+,\s*((?:19|20)\d{2})"),
    re.compile(r",\s*((?:19|20)\d{2})\s+vol", re.IGNORECASE),
    re.compile(r"((?:19|20)\d{2})\s*,(?:[^,]{0,140},)?\s*ISBN", re.IGNORECASE),
    re.compile(r"\bEd(?:itorial)?\b[^,;]{0,80}?\b((?:19|20)\d{2})\b", re.IGNORECASE),
]
_ANIO_MIN = 1950
_ANIO_MAX = date.today().year + 1


def _extraer_anio(txt):
    for pat in _ANIO_PATRONES:
        m = pat.search(txt or "")
        if m:
            try:
                a = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if _ANIO_MIN <= a <= _ANIO_MAX:
                return a
    return 0


# El parser original sustituye los tramos de 3+ espacios del HTML por " _ "
# (herencia del volcado a Excel). Ese relleno no significa nada, se ve en el
# tablero y además rompe la lectura del año en libros ("2024, _ ISBN:").
_SEPARADOR_RUIDO = re.compile(r"\s+_\s+")


def limpiar_registro(txt):
    """Normaliza el texto de una publicación tal como llega del GrupLac."""
    t = _norm_txt(txt)
    t = _SEPARADOR_RUIDO.sub(" ", t)
    t = re.sub(r"^[;\s]+", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


_LINEA_RE = re.compile(r"^\s*\d+\.\s*-\s*(.+?)\s*$")


def _parse_lineas(txt):
    """'1. - AUTOMATIZACION\\n2. - ENERGIAS' -> ['AUTOMATIZACION', 'ENERGIAS']"""
    out = []
    for raw in _norm_txt(txt).splitlines():
        m = _LINEA_RE.match(raw)
        nombre = (m.group(1) if m else raw).strip()
        if nombre and nombre not in out:
            out.append(nombre)
    return out


def _anio_formacion(txt):
    """'1992 - 9' -> 1992"""
    m = re.match(r"\s*((?:19|20)\d{2})", _norm_txt(txt))
    return int(m.group(1)) if m else 0


_STOPWORDS = {
    "de", "la", "el", "en", "los", "las", "del", "una", "uno", "unas", "unos",
    "por", "para", "con", "sin", "sobre", "entre", "desde", "hasta", "hacia",
    "como", "cómo", "más", "pero", "porque", "cuando", "donde", "dónde",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "otro", "otra", "otros", "otras", "todo", "toda", "todos", "todas",
    "mucho", "mucha", "muchos", "muchas", "poco", "poca", "pocos", "pocas",
    "tanto", "tan", "muy", "también", "solo", "sólo", "así", "cada", "sus",
    "nos", "les", "ante", "bajo", "cabe", "tras", "durante", "mediante",
    "issn", "vol", "fasc", "doi", "págs", "pags", "autores", "autor",
    "publicado", "publicada", "publicados", "publicadas", "publicación",
    "revista", "revistas", "especializada", "especializado", "libro",
    "libros", "capítulo", "capitulo", "capítulos", "capitulos", "editorial",
    "edición", "edicion", "https", "www", "org", "com", "cra", "etc",
    "son", "fue", "han", "hay", "está", "estan", "están", "ser", "tiene",
    "isbn", "the", "and", "for", "with", "from", "are", "was", "were",
    "has", "have", "had", "that", "this", "these", "those", "which",
    "their", "there", "been", "will", "would", "can", "its", "into",
    "between", "through", "under", "while", "each", "other", "such",
    "than", "then", "also", "based", "using", "used", "use", "study",
    "studies", "effect", "effects", "analysis", "case", "cases",
    "approach", "review", "research", "new", "two", "three", "first",
    "results", "result", "data", "model",
}
_WORD_RE = re.compile(r"[a-záéíóúñü]{3,}", re.IGNORECASE | re.UNICODE)
_ISSN_RE = re.compile(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 .&'/\-]{2,100}?)\s+ISSN\s*:", re.UNICODE)


def _contar_palabras(textos):
    c = Counter()
    for t in textos:
        for w in _WORD_RE.findall((t or "").lower()):
            if w not in _STOPWORDS:
                c[w] += 1
    return c


