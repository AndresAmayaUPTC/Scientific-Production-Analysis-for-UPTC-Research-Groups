"""Orquestación de una ingesta completa.

    obtener datos → escribir con run_id propio → validar → publicar o descartar

Ningún fallo en las tres primeras etapas toca los datos que el tablero está
sirviendo: el puntero de versión activa solo se mueve en la última.
"""
import logging
import traceback
import uuid
from datetime import datetime, timezone

from . import calidad, config, modelo, respaldo

log = logging.getLogger("ingesta")


def nuevo_run_id():
    """Identificador único de corrida.

    Lleva sufijo aleatorio además de la marca de tiempo: con resolución de
    segundos, dos ingestas lanzadas a la vez (el planificador y una manual,
    por ejemplo) compartirían id y sus documentos se mezclarían en la misma
    versión.
    """
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{marca}-{uuid.uuid4().hex[:6]}"


class Resultado:
    def __init__(self, ok, run_id, estado, conteos=None, motivo=None, error=None):
        self.ok = ok
        self.run_id = run_id
        self.estado = estado          # publicada | descartada | fallida
        self.conteos = conteos or {}
        self.motivo = motivo
        self.error = error

    def as_dict(self):
        return {
            "ok": self.ok, "run_id": self.run_id, "estado": self.estado,
            "conteos": self.conteos, "motivo": self.motivo, "error": self.error,
        }

    def __repr__(self):
        return f"<Ingesta {self.estado} run={self.run_id} {self.conteos}>"


def ejecutar(repo, obtener_datos=None, origen="scraper", guardar_respaldo=True):
    """Corre una ingesta completa contra `repo`.

    obtener_datos: callable que devuelve (grupos, miembros, publicaciones).
                   Por defecto, el scraping del GrupLac.
    """
    if obtener_datos is None:
        obtener_datos = _scrapear

    run_id = nuevo_run_id()
    vigentes = repo.conteos_activos()
    repo.iniciar_ejecucion(run_id, origen=origen)
    log.info("Ingesta %s iniciada (origen=%s). Versión vigente: %s", run_id, origen, vigentes)

    # --- 1. Obtener ---
    try:
        grupos, miembros, publicaciones = obtener_datos()
    except Exception as e:
        detalle = f"{type(e).__name__}: {e}"
        log.error("Ingesta %s falló al obtener datos: %s", run_id, detalle)
        log.debug(traceback.format_exc())
        repo.finalizar_ejecucion(run_id, "fallida", error=detalle)
        return Resultado(False, run_id, "fallida", error=detalle)

    # --- 2. Escribir bajo su propio run_id ---
    try:
        conteos = repo.escribir_lote(run_id, grupos, miembros, publicaciones)
    except Exception as e:
        detalle = f"{type(e).__name__}: {e}"
        log.error("Ingesta %s falló al escribir: %s", run_id, detalle)
        repo.descartar(run_id, "error de escritura", error=detalle)
        return Resultado(False, run_id, "fallida", error=detalle)

    # --- 3. Validar contra la versión vigente ---
    veredicto = calidad.validar(conteos, vigentes if any(vigentes.values()) else None)
    if not veredicto.ok:
        log.warning("Ingesta %s descartada: %s. Se conserva la versión anterior.", run_id, veredicto.motivo)
        repo.descartar(run_id, veredicto.motivo)
        return Resultado(False, run_id, "descartada", conteos, motivo=veredicto.motivo)

    # --- 4. Publicar ---
    repo.publicar(run_id, conteos)
    log.info("Ingesta %s publicada: %s", run_id, conteos)

    if guardar_respaldo:
        try:
            respaldo.guardar(run_id, grupos, miembros, publicaciones, conteos)
        except Exception as e:
            # Un respaldo fallido no invalida la ingesta: los datos ya están
            # publicados en Mongo, que es el origen principal.
            log.warning("No se pudo guardar el respaldo de %s: %s", run_id, e)

    try:
        purgadas = repo.purgar_ejecuciones_viejas()
        if purgadas:
            log.info("Ejecuciones purgadas: %s", purgadas)
    except Exception as e:
        log.warning("No se pudieron purgar ejecuciones viejas: %s", e)

    return Resultado(True, run_id, "publicada", conteos)


def _scrapear():
    """Scraping del GrupLac. Se importa aquí dentro para que el resto del
    módulo no dependa de requests/bs4 cuando solo se siembra desde Excel."""
    from .scraper import obtener_grupos
    return modelo.desde_scraper(obtener_grupos())


def sembrar_desde_excel(repo, ruta_resultados=None, ruta_miembros=None):
    """Carga inicial a partir de los Excel del repositorio.

    Útil para dejar la base operativa desde el minuto uno, sin depender de que
    el portal del GrupLac responda.
    """
    ruta_resultados = ruta_resultados or config.RES_XLSX
    ruta_miembros = ruta_miembros or config.MIEM_XLSX

    def cargar():
        return modelo.desde_excel(ruta_resultados, ruta_miembros)

    return ejecutar(repo, obtener_datos=cargar, origen="excel")
