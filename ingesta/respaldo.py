"""Respaldo en disco: la red de seguridad por debajo de MongoDB.

Cadena completa que usa el backend para obtener datos:

    1. MongoDB, versión publicada  (lo normal)
    2. último snapshot local       (si Atlas no responde)
    3. Excel de `extraccion-/`     (si nunca hubo snapshot)

Cada corrida publicada deja un snapshot comprimido, así que el tablero puede
arrancar sin conexión a Atlas.
"""
import gzip
import json
import shutil
from datetime import datetime, timezone

from . import config

SUFIJO = ".json.gz"


def _dir():
    config.DIR_RESPALDOS.mkdir(parents=True, exist_ok=True)
    return config.DIR_RESPALDOS


def _serializar(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def guardar(run_id, grupos, miembros, publicaciones, conteos=None):
    """Escribe el snapshot de una corrida publicada."""
    destino = _dir() / f"{run_id}{SUFIJO}"
    payload = {
        "run_id": run_id,
        "creado_en": datetime.now(timezone.utc).isoformat(),
        "conteos": conteos or {
            "grupos": len(grupos), "miembros": len(miembros),
            "publicaciones": len(publicaciones),
        },
        "grupos": grupos,
        "miembros": miembros,
        "publicaciones": publicaciones,
    }
    # Se escribe a un temporal y se renombra: si el proceso muere a mitad,
    # no queda un snapshot truncado que luego se lea como válido.
    temporal = destino.with_suffix(".tmp")
    with gzip.open(temporal, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, default=_serializar)
    shutil.move(str(temporal), str(destino))
    purgar()
    return destino


def listar():
    """Snapshots existentes, del más reciente al más antiguo."""
    if not config.DIR_RESPALDOS.exists():
        return []
    return sorted(
        config.DIR_RESPALDOS.glob(f"*{SUFIJO}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def purgar(conservar=None):
    conservar = conservar or config.RESPALDOS_A_CONSERVAR
    sobrantes = listar()[conservar:]
    for p in sobrantes:
        p.unlink(missing_ok=True)
    return [p.name for p in sobrantes]


def cargar_ultimo():
    """Devuelve el snapshot más reciente que se pueda leer entero.

    Si el más nuevo está corrupto se intenta el anterior, en vez de dejar la
    aplicación sin datos por un único archivo dañado.
    """
    for ruta in listar():
        try:
            with gzip.open(ruta, "rt", encoding="utf-8") as fh:
                datos = json.load(fh)
            if "grupos" in datos:
                return datos
        except (OSError, EOFError, json.JSONDecodeError):
            continue
    return None


def info():
    ultimo = listar()
    if not ultimo:
        return {"disponible": False, "cantidad": 0}
    p = ultimo[0]
    return {
        "disponible": True,
        "cantidad": len(ultimo),
        "ultimo": p.name,
        "creado_en": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        "bytes": p.stat().st_size,
    }
