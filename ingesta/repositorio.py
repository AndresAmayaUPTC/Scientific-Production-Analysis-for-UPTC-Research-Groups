"""Acceso a MongoDB con publicación por versiones.

Idea central: una ejecución del scraper NUNCA pisa los datos vigentes.

    1. Cada corrida escribe sus documentos etiquetados con su propio `run_id`.
    2. Solo si termina completa y pasa los controles de calidad, se mueve el
       puntero `meta.activo` a ese `run_id`.
    3. Las lecturas siempre filtran por el `run_id` activo.

Así, si el scraping falla a mitad, se corta la red o el portal devuelve una
página vacía, el tablero sigue sirviendo la última versión buena. El scraper
anterior hacía `delete_many({})` ANTES de descargar nada, de modo que
cualquier fallo dejaba la base vacía y la aplicación sin datos.
"""
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient

from . import config


def ahora():
    return datetime.now(timezone.utc)


class Repositorio:
    """Envoltura fina sobre la base. Recibe un cliente ya construido para
    poder inyectar `mongomock` en las pruebas."""

    def __init__(self, cliente, nombre_db=None):
        self.cliente = cliente
        self.db = cliente[nombre_db or config.MONGODB_DB]
        self.grupos = self.db[config.COL_GRUPOS]
        self.miembros = self.db[config.COL_MIEMBROS]
        self.publicaciones = self.db[config.COL_PUBLICACIONES]
        self.ejecuciones = self.db[config.COL_EJECUCIONES]
        self.meta = self.db[config.COL_META]

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    @classmethod
    def desde_uri(cls, uri=None, nombre_db=None, **kwargs):
        uri = uri or config.MONGODB_URI
        if not uri:
            raise RuntimeError(
                "Falta MONGODB_URI. Copia .env.example a .env y pon ahí la cadena "
                "de conexión del cluster de Atlas."
            )
        kwargs.setdefault("serverSelectionTimeoutMS", 8000)
        return cls(MongoClient(uri, **kwargs), nombre_db)

    def crear_indices(self):
        """Índices que sostienen las consultas del tablero."""
        self.grupos.create_index([("run_id", ASCENDING), ("nombre_grupo", ASCENDING)])
        self.grupos.create_index([("run_id", ASCENDING), ("ciudad", ASCENDING)])
        self.miembros.create_index([("run_id", ASCENDING), ("nombre_grupo", ASCENDING)])
        self.publicaciones.create_index([("run_id", ASCENDING), ("nombre_grupo", ASCENDING)])
        self.publicaciones.create_index([("run_id", ASCENDING), ("anio", ASCENDING)])
        self.publicaciones.create_index([("run_id", ASCENDING), ("tipo", ASCENDING)])
        self.ejecuciones.create_index([("run_id", ASCENDING)], unique=True)

    def ping(self):
        self.cliente.admin.command("ping")
        return True

    # ------------------------------------------------------------------
    # Puntero de versión activa
    # ------------------------------------------------------------------
    def run_activo(self):
        doc = self.meta.find_one({"_id": "activo"})
        return doc.get("run_id") if doc else None

    def _promover(self, run_id):
        self.meta.update_one(
            {"_id": "activo"},
            {"$set": {"run_id": run_id, "promovido_en": ahora()}},
            upsert=True,
        )

    # ------------------------------------------------------------------
    # Escritura de una ejecución
    # ------------------------------------------------------------------
    def iniciar_ejecucion(self, run_id, origen="scraper"):
        self.ejecuciones.insert_one({
            "run_id": run_id,
            "origen": origen,
            "estado": "en_curso",
            "iniciada_en": ahora(),
            "terminada_en": None,
            "conteos": {},
            "error": None,
            "motivo_rechazo": None,
        })

    def escribir_lote(self, run_id, grupos, miembros, publicaciones):
        """Vuelca los documentos de una corrida, etiquetados con su run_id."""
        def etiquetar(docs):
            return [{**d, "run_id": run_id} for d in docs]

        if grupos:
            self.grupos.insert_many(etiquetar(grupos))
        if miembros:
            self.miembros.insert_many(etiquetar(miembros))
        if publicaciones:
            self.publicaciones.insert_many(etiquetar(publicaciones))

        return {
            "grupos": self.grupos.count_documents({"run_id": run_id}),
            "miembros": self.miembros.count_documents({"run_id": run_id}),
            "publicaciones": self.publicaciones.count_documents({"run_id": run_id}),
        }

    def finalizar_ejecucion(self, run_id, estado, conteos=None, error=None, motivo_rechazo=None):
        self.ejecuciones.update_one(
            {"run_id": run_id},
            {"$set": {
                "estado": estado,
                "terminada_en": ahora(),
                "conteos": conteos or {},
                "error": error,
                "motivo_rechazo": motivo_rechazo,
            }},
        )

    def publicar(self, run_id, conteos):
        """Marca la ejecución como vigente. Es el único punto donde el
        tablero empieza a ver los datos nuevos."""
        self.finalizar_ejecucion(run_id, "publicada", conteos)
        self._promover(run_id)

    def descartar(self, run_id, motivo, error=None):
        """Deja la ejecución registrada pero sin publicar, y borra sus
        documentos para no acumular basura. El puntero activo no se toca."""
        self.finalizar_ejecucion(run_id, "descartada", error=error, motivo_rechazo=motivo)
        self.borrar_run(run_id)

    def borrar_run(self, run_id):
        for col in (self.grupos, self.miembros, self.publicaciones):
            col.delete_many({"run_id": run_id})

    def purgar_ejecuciones_viejas(self, conservar=None):
        """Conserva las N publicadas más recientes (la activa entre ellas)
        y borra los documentos de las demás."""
        conservar = conservar or config.EJECUCIONES_A_CONSERVAR
        publicadas = list(self.ejecuciones.find(
            {"estado": "publicada"}, {"run_id": 1}
        ).sort("terminada_en", -1))
        a_conservar = {d["run_id"] for d in publicadas[:conservar]}
        activo = self.run_activo()
        if activo:
            a_conservar.add(activo)

        borradas = []
        for d in publicadas[conservar:]:
            if d["run_id"] in a_conservar:
                continue
            self.borrar_run(d["run_id"])
            self.ejecuciones.update_one({"run_id": d["run_id"]}, {"$set": {"estado": "purgada"}})
            borradas.append(d["run_id"])
        return borradas

    # ------------------------------------------------------------------
    # Lectura (siempre sobre la versión activa)
    # ------------------------------------------------------------------
    def _filtro(self, run_id=None):
        rid = run_id or self.run_activo()
        return {"run_id": rid} if rid else {"run_id": "__ninguna__"}

    def leer_grupos(self, run_id=None):
        return list(self.grupos.find(self._filtro(run_id), {"_id": 0}))

    def leer_miembros(self, run_id=None):
        return list(self.miembros.find(self._filtro(run_id), {"_id": 0}))

    def leer_publicaciones(self, run_id=None):
        return list(self.publicaciones.find(self._filtro(run_id), {"_id": 0}))

    def conteos_activos(self):
        f = self._filtro()
        return {
            "grupos": self.grupos.count_documents(f),
            "miembros": self.miembros.count_documents(f),
            "publicaciones": self.publicaciones.count_documents(f),
        }

    def ultima_ejecucion(self):
        return self.ejecuciones.find_one({}, {"_id": 0}, sort=[("iniciada_en", -1)])

    def ultima_publicacion(self, origen=None):
        """Última corrida que llegó a publicarse. Con `origen` se acota a un
        tipo concreto ('scraper' o 'excel'), que es como se distingue una
        siembra desde los Excel de una descarga real del GrupLac."""
        filtro = {"estado": "publicada"}
        if origen:
            filtro["origen"] = origen
        return self.ejecuciones.find_one(filtro, {"_id": 0}, sort=[("terminada_en", -1)])

    def historial(self, limite=10):
        return list(self.ejecuciones.find({}, {"_id": 0}).sort("iniciada_en", -1).limit(limite))

    def cerrar(self):
        self.cliente.close()
