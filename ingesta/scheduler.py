"""Ejecución periódica de la ingesta.

Dos formas de usarlo, según dónde se despliegue:

  - **Dentro del backend** (`iniciar_en_segundo_plano`): un hilo de APScheduler
    lanza la ingesta cada `SCRAPE_INTERVAL_HOURS`. Sirve para un despliegue
    de un solo proceso.
  - **Como tarea externa** (`python -m ingesta.run`): una sola pasada y salir,
    para cron, un Cron Job de Render o GitHub Actions. Es lo preferible si hay
    varias réplicas del backend, porque evita que todas scrapeen a la vez.

En ambos casos se registra el resultado en la colección `ejecuciones`.
"""
import logging

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from . import config, pipeline

log = logging.getLogger("ingesta.scheduler")

_scheduler = None
ID_TAREA = "ingesta_gruplac"


def _tarea(fabrica_repo, al_publicar=None):
    repo = None
    try:
        repo = fabrica_repo()
        resultado = pipeline.ejecutar(repo)
        log.info("Ingesta periódica: %s", resultado)
        # Quien sirve los datos (el backend) los tiene en memoria: hay que
        # avisarle, o seguiría mostrando la versión anterior hasta reiniciar.
        if resultado.ok and al_publicar is not None:
            try:
                al_publicar(resultado)
            except Exception:
                log.exception("La versión %s se publicó, pero falló la recarga", resultado.run_id)
        return resultado
    except Exception as e:
        # Una excepción aquí no debe tumbar el planificador: se registra y
        # se espera al siguiente disparo.
        log.exception("La ingesta periódica falló por completo: %s", e)
    finally:
        if repo is not None:
            try:
                repo.cerrar()
            except Exception:
                pass


def _a_utc(momento):
    """Mongo devuelve las fechas sin zona; se asumen UTC, que es como se
    escribieron."""
    if momento is None:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def decidir_arranque(repo, horas, modo="auto"):
    """¿Hay que lanzar una ingesta nada más arrancar? Devuelve (bool, motivo).

    En modo 'auto' se mira el estado real de los datos en vez de un simple
    interruptor:

      - la base no tiene ninguna versión publicada  → sí
      - solo tiene una siembra desde los Excel      → sí (esos datos son una
        foto antigua; nunca se ha descargado del GrupLac)
      - la última descarga es más vieja que el intervalo → sí
      - en cualquier otro caso                      → no
    """
    if modo == "true":
        return True, "SCRAPE_ON_STARTUP=true"
    if modo == "false":
        return False, "SCRAPE_ON_STARTUP=false"

    if repo.run_activo() is None:
        return True, "la base no tiene ninguna versión publicada"

    ultima = repo.ultima_publicacion(origen="scraper")
    if not ultima:
        return True, "todavía no se ha descargado nada del GrupLac (los datos vienen de los Excel)"

    terminada = _a_utc(ultima.get("terminada_en"))
    if terminada is None:
        return True, "la última descarga no tiene fecha de fin registrada"

    antiguedad = datetime.now(timezone.utc) - terminada
    if antiguedad > timedelta(hours=horas):
        return True, f"la última descarga fue hace {antiguedad.total_seconds() / 3600:.1f} h"

    restante = timedelta(hours=horas) - antiguedad
    return False, f"los datos están al día; siguiente descarga en {restante.total_seconds() / 3600:.1f} h"


def iniciar_en_segundo_plano(fabrica_repo, horas=None, ejecutar_ya=None, al_publicar=None):
    """Arranca el planificador. `al_publicar(resultado)` se llama tras cada
    ingesta publicada, para que el backend recargue sus datos en memoria."""
    global _scheduler
    if _scheduler is not None:
        log.info("El planificador ya estaba activo")
        return _scheduler

    horas = config.INTERVALO_HORAS if horas is None else horas
    modo = config.EJECUTAR_AL_ARRANCAR if ejecutar_ya is None else ejecutar_ya
    if isinstance(modo, bool):
        modo = "true" if modo else "false"

    # La decisión se toma antes de arrancar el planificador: si la base no se
    # puede consultar, se programa igual y se deja constancia del motivo.
    try:
        repo = fabrica_repo()
        try:
            ejecutar_ya, motivo = decidir_arranque(repo, horas, modo)
        finally:
            repo.cerrar()
    except Exception as e:
        ejecutar_ya, motivo = False, f"no se pudo consultar el estado de la base ({e})"

    _scheduler = BackgroundScheduler(timezone="America/Bogota")
    _scheduler.add_job(
        _tarea,
        "interval",
        hours=horas,
        args=[fabrica_repo, al_publicar],
        id=ID_TAREA,
        # Si el proceso estuvo caído y se acumularon disparos, se ejecuta uno
        # solo en vez de encadenar varios scrapings seguidos.
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    log.info("Ingesta programada cada %s horas", horas)

    if ejecutar_ya:
        log.info("Se lanza una ingesta al arrancar: %s", motivo)
        _scheduler.add_job(_tarea, args=[fabrica_repo, al_publicar], id=f"{ID_TAREA}_inicial")
    else:
        log.info("No se lanza ingesta al arrancar: %s", motivo)

    return _scheduler


def detener():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def proxima_ejecucion():
    if _scheduler is None:
        return None
    tarea = _scheduler.get_job(ID_TAREA)
    return tarea.next_run_time.isoformat() if tarea and tarea.next_run_time else None


def activo():
    return _scheduler is not None and _scheduler.running
