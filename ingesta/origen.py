"""De dónde saca los datos el backend, en orden de preferencia.

    1. MongoDB, versión publicada   → lo normal
    2. último snapshot en disco     → si Atlas no responde o no hay URI
    3. Excel de extraccion-         → si nunca hubo snapshot

El tablero nunca se queda sin datos por una caída de Atlas: como cada ingesta
publicada deja su snapshot, el eslabón 2 casi siempre está disponible y trae
exactamente lo mismo que había en la base.

Todas las fuentes devuelven la misma forma de documentos (ver modelo.py), así
que quien consume esto no necesita saber de dónde vinieron.
"""
import logging

from . import config, modelo, respaldo

log = logging.getLogger("ingesta.origen")


class Datos:
    def __init__(self, grupos, miembros, publicaciones, origen, detalle=""):
        self.grupos = grupos
        self.miembros = miembros
        self.publicaciones = publicaciones
        self.origen = origen        # mongodb | respaldo | excel
        self.detalle = detalle

    @property
    def conteos(self):
        return {
            "grupos": len(self.grupos),
            "miembros": len(self.miembros),
            "publicaciones": len(self.publicaciones),
        }

    def __repr__(self):
        return f"<Datos origen={self.origen} {self.conteos}>"


def _desde_mongo(fabrica_repo=None):
    if not config.mongo_configurado():
        raise RuntimeError("MONGODB_URI no está configurada")

    if fabrica_repo is None:
        from .repositorio import Repositorio
        fabrica_repo = Repositorio.desde_uri

    repo = fabrica_repo()
    try:
        repo.ping()
        run = repo.run_activo()
        if not run:
            raise RuntimeError("la base no tiene ninguna versión publicada todavía")
        grupos = repo.leer_grupos()
        if not grupos:
            raise RuntimeError(f"la versión publicada ({run}) no tiene grupos")
        return Datos(grupos, repo.leer_miembros(), repo.leer_publicaciones(),
                     "mongodb", f"versión {run}")
    finally:
        repo.cerrar()


def _desde_respaldo():
    datos = respaldo.cargar_ultimo()
    if not datos:
        raise RuntimeError("no hay snapshots en disco")
    return Datos(
        datos.get("grupos", []), datos.get("miembros", []), datos.get("publicaciones", []),
        "respaldo", f"snapshot {datos.get('run_id', '?')} de {datos.get('creado_en', '?')}",
    )


def _desde_excel():
    grupos, miembros, publicaciones = modelo.desde_excel(config.RES_XLSX, config.MIEM_XLSX)
    return Datos(grupos, miembros, publicaciones, "excel", str(config.RES_XLSX.name))


def obtener(preferir=None, fabrica_repo=None):
    """Recorre la cadena de respaldo y devuelve lo primero que funcione.

    preferir: fuerza una fuente ('mongodb', 'respaldo' o 'excel'). Si esa
    falla, igualmente se prueban las siguientes.
    """
    cadena = [
        ("mongodb", lambda: _desde_mongo(fabrica_repo)),
        ("respaldo", _desde_respaldo),
        ("excel", _desde_excel),
    ]
    if preferir:
        cadena.sort(key=lambda par: par[0] != preferir)

    intentos = []
    for nombre, cargar in cadena:
        try:
            datos = cargar()
            if intentos:
                log.warning(
                    "Datos servidos desde '%s'. Fuentes descartadas: %s",
                    nombre, "; ".join(intentos),
                )
            else:
                log.info("Datos servidos desde '%s' (%s)", nombre, datos.detalle)
            datos.intentos_fallidos = intentos
            return datos
        except Exception as e:
            intentos.append(f"{nombre}: {type(e).__name__}: {e}")
            log.warning("Origen '%s' no disponible: %s", nombre, e)

    raise RuntimeError(
        "Ninguna fuente de datos está disponible. Intentos: " + " | ".join(intentos)
    )
