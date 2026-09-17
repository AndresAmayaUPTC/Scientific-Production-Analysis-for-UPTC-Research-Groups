"""Configuración de la ingesta, toda por variables de entorno.

Las credenciales NUNCA se escriben en el código: el scraper anterior llevaba
usuario y contraseña de Atlas en claro dentro de `extraccion-/scraping.py` y
`extraccion-/api.py`, que están versionados.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga el .env del proyecto si existe. Las variables ya presentes en el
# entorno mandan sobre el archivo, para que en despliegue (Render, Actions)
# valgan las del sistema sin tener que borrar el .env local.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv es opcional
    pass

# --- MongoDB ---
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "sci_uptc")

# Colecciones
COL_GRUPOS = "grupos"
COL_MIEMBROS = "miembros"
COL_PUBLICACIONES = "publicaciones"
COL_EJECUCIONES = "ejecuciones"   # historial de cada corrida del scraper
COL_META = "meta"                 # puntero a la ejecución activa

# --- Scraping ---
SCRAPE_URL = os.getenv(
    "SCRAPE_URL",
    "https://scienti.minciencias.gov.co/ciencia-war/busquedaGrupoXInstitucionGrupos.do"
    "?codInst=930&sglPais=&sgDepartamento=&maxRows=152"
    "&grupos_tr_=true&grupos_p_=1&grupos_mr_=152",
)
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "60"))
# Descargas simultáneas de fichas. Con 8 el portal cortaba conexiones
# (RemoteDisconnected en ~50 de 152 fichas); 3 es un término medio.
SCRAPE_WORKERS = int(os.getenv("SCRAPE_WORKERS", "3"))
# Fichas que fallan en la primera pasada se reintentan de una en una.
SCRAPE_RETRY_ROUNDS = int(os.getenv("SCRAPE_RETRY_ROUNDS", "3"))
SCRAPE_RETRY_PAUSE = float(os.getenv("SCRAPE_RETRY_PAUSE", "3"))          # s entre fichas
SCRAPE_RETRY_ROUND_PAUSE = float(os.getenv("SCRAPE_RETRY_ROUND_PAUSE", "30"))  # s antes de cada ronda

# --- Periodicidad ---
# Mensual (30 días). El GrupLac no tiene calendario de publicación: los
# grupos editan su ficha cuando quieren, y el ritmo medio observado es de
# unas 5 publicaciones nuevas al día repartidas entre 149 grupos.
INTERVALO_HORAS = float(os.getenv("SCRAPE_INTERVAL_HOURS", "720"))

# Qué hacer al arrancar el backend. El planificador solo dispara cada
# INTERVALO_HORAS *a partir* del arranque, así que sin esto un proceso que se
# reinicia a menudo no llegaría a scrapear nunca.
#   auto  (por defecto) lanza una ingesta si los datos están atrasados
#   true  lanza una siempre
#   false no lanza ninguna; espera al primer disparo del intervalo
EJECUTAR_AL_ARRANCAR = os.getenv("SCRAPE_ON_STARTUP", "auto").strip().lower()

# --- Respaldo ---
DIR_RESPALDOS = Path(os.getenv("BACKUP_DIR", BASE_DIR / "respaldos"))
RESPALDOS_A_CONSERVAR = int(os.getenv("BACKUP_KEEP", "10"))
EJECUCIONES_A_CONSERVAR = int(os.getenv("RUNS_KEEP", "3"))

# Excel original: último eslabón de la cadena de respaldo.
RES_XLSX = BASE_DIR / "extraccion-" / "resultados_grupos.xlsx"
MIEM_XLSX = BASE_DIR / "extraccion-" / "miembros_grupos.xlsx"

# --- Umbrales de calidad ---
# Una ejecución no reemplaza a la anterior si no los cumple. Evita que una
# caída parcial del portal deje el tablero con datos truncados.
MIN_GRUPOS = int(os.getenv("MIN_GRUPOS", "100"))
MIN_PUBLICACIONES = int(os.getenv("MIN_PUBLICACIONES", "5000"))
# Caída máxima tolerada frente a la ejecución vigente (0.20 = 20 %).
CAIDA_MAXIMA = float(os.getenv("MAX_DROP_RATIO", "0.20"))


def mongo_configurado() -> bool:
    return bool(MONGODB_URI)
