"""Scraping del GrupLac de Minciencias.

Reaprovecha las funciones de extracción del scraper original
(`extraccion-/scraping.py`), pero sin sus dos problemas de raíz:

  - ya no abre conexión a Mongo ni borra nada: solo devuelve datos, y quien
    decide qué hacer con ellos es `pipeline.ejecutar`;
  - las credenciales no viven en el código.

Si la página no trae la tabla esperada se lanza `ScrapingError`, en lugar de
devolver una lista vacía que luego se confundiría con "la UPTC no tiene grupos".
"""
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger("ingesta.scraper")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# El módulo original vive en una carpeta con guion final, que no es un nombre
# de paquete válido; se añade al path para reutilizar sus parsers.
_DIR_ORIGINAL = config.BASE_DIR / "extraccion-"


class ScrapingError(RuntimeError):
    """El portal respondió, pero no con lo que se esperaba."""


class PortalNoDisponible(ScrapingError):
    """El portal SCienTI no está sirviendo la aplicación.

    Ocurre de verdad: el servicio se cae con cierta frecuencia y devuelve 503
    desde el balanceador, o 404 de JBoss cuando la aplicación `ciencia-war` no
    está desplegada. No es un fallo del scraper y no hay nada que reintentar
    en el momento: la siguiente ejecución programada lo recogerá.
    """


def _revisar_respuesta(respuesta, url):
    """Traduce los códigos de error del portal a un mensaje accionable."""
    if respuesta.status_code in (403, 404, 500, 502, 503, 504):
        raise PortalNoDisponible(
            f"El portal SCienTI respondió {respuesta.status_code} en {url}. "
            "El servicio suele estar en mantenimiento o caído; compruébalo en "
            "https://scienti.minciencias.gov.co/ciencia-war/ desde el navegador. "
            "Los datos publicados no se han tocado."
        )
    respuesta.raise_for_status()


def _parsers():
    """Carga perezosa de las funciones de extracción del scraper original."""
    if str(_DIR_ORIGINAL) not in sys.path:
        sys.path.insert(0, str(_DIR_ORIGINAL))
    import scraping  # noqa: E402  (módulo de extraccion-/)
    return scraping


class _AdaptadorConTimeout(HTTPAdapter):
    """`requests` no tiene timeout por defecto: sin esto, una petición que el
    portal deja colgada bloquea el hilo para siempre. (El scraper original
    hacía `session.timeout = 30`, que `requests` ignora.)"""

    def __init__(self, *args, timeout=None, **kwargs):
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().send(request, **kwargs)


def crear_sesion(timeout=None):
    reintentos = Retry(
        total=3,
        connect=3,
        read=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1,
    )
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (SCI-UPTC; tablero academico UPTC)"})
    adapter = _AdaptadorConTimeout(
        max_retries=reintentos, pool_connections=10, pool_maxsize=10,
        timeout=timeout or config.SCRAPE_TIMEOUT,
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _ficha_valida(detalle):
    """Una ficha sirve si trae el nombre del grupo. `info_grupo_publicaciones`
    devuelve {} cuando la petición falla, y una página de error del portal
    llega sin `titulo`: en ambos casos el grupo se perdería más adelante."""
    return bool(detalle) and bool(str(detalle.get("titulo", "")).strip())


def descargar_fichas(enlaces, descargar, workers=None, rondas=None,
                     pausa=None, pausa_ronda=None, dormir=time.sleep):
    """Descarga las fichas y reintenta las que fallen.

    1. Primera pasada en paralelo, con pocos hilos (`workers`).
    2. Hasta `rondas` rondas más solo con las fallidas, de una en una,
       con `pausa` segundos entre fichas y `pausa_ronda` antes de cada ronda
       (se duplica en cada ronda, para dar tiempo a que el portal se recupere).

    Devuelve una lista alineada con `enlaces`: la ficha, o None si no se pudo.
    """
    workers = workers or config.SCRAPE_WORKERS
    rondas = config.SCRAPE_RETRY_ROUNDS if rondas is None else rondas
    pausa = config.SCRAPE_RETRY_PAUSE if pausa is None else pausa
    pausa_ronda = config.SCRAPE_RETRY_ROUND_PAUSE if pausa_ronda is None else pausa_ronda

    def intentar(enlace):
        try:
            return descargar(enlace)
        except Exception as e:  # el parser original solo captura RequestException
            log.debug("Ficha %s falló: %s", enlace, e)
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fichas = list(pool.map(intentar, enlaces))

    pendientes = [i for i, f in enumerate(fichas) if not _ficha_valida(f)]
    log.info("Primera pasada: %s de %s fichas correctas", len(enlaces) - len(pendientes), len(enlaces))

    for ronda in range(1, rondas + 1):
        if not pendientes:
            break
        espera = pausa_ronda * (2 ** (ronda - 1))
        log.info("Reintento %s/%s: %s fichas pendientes (esperando %.0f s)",
                 ronda, rondas, len(pendientes), espera)
        dormir(espera)

        siguen = []
        for n, i in enumerate(pendientes):
            if n:
                dormir(pausa)
            ficha = intentar(enlaces[i])
            if _ficha_valida(ficha):
                fichas[i] = ficha
            else:
                siguen.append(i)
        log.info("Reintento %s: recuperadas %s, siguen fallando %s",
                 ronda, len(pendientes) - len(siguen), len(siguen))
        pendientes = siguen

    if pendientes:
        log.warning("%s de %s fichas no se pudieron descargar tras %s reintentos",
                    len(pendientes), len(enlaces), rondas)
    for i in pendientes:
        fichas[i] = None
    return fichas


def obtener_grupos(url=None, sesion=None, workers=None):
    """Devuelve la lista de grupos con su información y publicaciones.

    Lanza ScrapingError si la respuesta no contiene la tabla de grupos.
    Los grupos cuya ficha no se pudo descargar se omiten; si faltan muchos,
    los controles de calidad de la ingesta rechazarán la corrida.
    """
    url = url or config.SCRAPE_URL
    sesion = sesion or crear_sesion()
    scraping = _parsers()
    # Los parsers originales usan su propia `session` global (sin timeout y
    # con reintentos agresivos); se sustituye por la nuestra.
    scraping.session = sesion

    log.info("Descargando listado de grupos: %s", url)
    respuesta = sesion.get(url, verify=False)
    _revisar_respuesta(respuesta, url)

    sopa = BeautifulSoup(respuesta.text, "html.parser")
    tabla = sopa.find("table", {"id": "grupos"})
    if tabla is None:
        raise ScrapingError(
            "La respuesta no contiene la tabla 'grupos'. El portal puede estar "
            "en mantenimiento o haber cambiado el HTML."
        )

    filas = tabla.find_all("tr")[1:]
    if not filas:
        raise ScrapingError("La tabla de grupos vino vacía.")

    resultados = [r for r in (scraping.procesar_grupo(f) for f in filas) if r]
    if not resultados:
        raise ScrapingError("Ninguna fila del listado pudo procesarse.")

    log.info("%s grupos en el listado; descargando sus fichas…", len(resultados))
    enlaces = [r["enlace_gruplac"] for r in resultados]
    fichas = descargar_fichas(enlaces, scraping.info_grupo_publicaciones, workers=workers)

    completos = []
    for resultado, ficha in zip(resultados, fichas):
        if ficha is not None:
            resultado.update(ficha)
            completos.append(resultado)
    return completos
