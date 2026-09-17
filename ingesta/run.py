"""Interfaz de línea de comandos de la ingesta.

    python -m ingesta.run estado      # a qué apunta la base y cómo fue la última corrida
    python -m ingesta.run sembrar     # carga inicial desde los Excel de extraccion-
    python -m ingesta.run scrapear    # una pasada de scraping (para cron)
    python -m ingesta.run indices     # crea los índices
    python -m ingesta.run historial   # últimas ejecuciones
    python -m ingesta.run respaldos   # snapshots en disco

`scrapear` es el comando pensado para un cron externo o un Cron Job de Render.
Devuelve código de salida 1 si la corrida no llegó a publicarse, para que el
programador lo marque como fallo.
"""
import argparse
import json
import logging
import sys

from . import config, pipeline, respaldo
from .repositorio import Repositorio


def _log(verboso=False):
    logging.basicConfig(
        level=logging.DEBUG if verboso else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _repo():
    return Repositorio.desde_uri()


def cmd_estado(args):
    repo = _repo()
    try:
        repo.ping()
        salida = {
            "conectado": True,
            "base_datos": repo.db.name,
            "run_activo": repo.run_activo(),
            "conteos": repo.conteos_activos(),
            "ultima_ejecucion": repo.ultima_ejecucion(),
            "respaldos": respaldo.info(),
        }
    finally:
        repo.cerrar()
    print(json.dumps(salida, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_indices(args):
    repo = _repo()
    try:
        repo.crear_indices()
        print(f"Índices creados en {repo.db.name}")
    finally:
        repo.cerrar()
    return 0


def cmd_sembrar(args):
    repo = _repo()
    try:
        repo.crear_indices()
        resultado = pipeline.sembrar_desde_excel(repo)
        print(json.dumps(resultado.as_dict(), indent=2, ensure_ascii=False))
    finally:
        repo.cerrar()
    return 0 if resultado.ok else 1


def cmd_scrapear(args):
    repo = _repo()
    try:
        repo.crear_indices()
        resultado = pipeline.ejecutar(repo)
        print(json.dumps(resultado.as_dict(), indent=2, ensure_ascii=False))
    finally:
        repo.cerrar()
    return 0 if resultado.ok else 1


def cmd_historial(args):
    repo = _repo()
    try:
        print(json.dumps(repo.historial(args.limite), indent=2, ensure_ascii=False, default=str))
    finally:
        repo.cerrar()
    return 0


def cmd_respaldos(args):
    print(json.dumps({
        "directorio": str(config.DIR_RESPALDOS),
        "info": respaldo.info(),
        "archivos": [p.name for p in respaldo.listar()],
    }, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ingesta", description="Ingesta de datos del GrupLac")
    parser.add_argument("-v", "--verboso", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("estado", help="estado de la conexión y de la última corrida").set_defaults(fn=cmd_estado)
    sub.add_parser("indices", help="crea los índices de las colecciones").set_defaults(fn=cmd_indices)
    sub.add_parser("sembrar", help="carga inicial desde los Excel").set_defaults(fn=cmd_sembrar)
    sub.add_parser("scrapear", help="una pasada de scraping").set_defaults(fn=cmd_scrapear)
    p_hist = sub.add_parser("historial", help="últimas ejecuciones")
    p_hist.add_argument("--limite", type=int, default=10)
    p_hist.set_defaults(fn=cmd_historial)
    sub.add_parser("respaldos", help="snapshots guardados en disco").set_defaults(fn=cmd_respaldos)

    args = parser.parse_args(argv)
    _log(args.verboso)

    if args.comando != "respaldos" and not config.mongo_configurado():
        print(
            "Falta MONGODB_URI.\n"
            "  1. Copia .env.example a .env\n"
            "  2. Pon ahí la cadena de conexión del cluster de Atlas\n"
            "  3. Vuelve a ejecutar este comando",
            file=sys.stderr,
        )
        return 2

    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
