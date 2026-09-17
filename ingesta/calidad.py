"""Controles que decide si una corrida puede sustituir a la vigente.

Un scraping puede "terminar bien" y aun así traer basura: el portal devuelve
una página de mantenimiento, cambia el HTML y los selectores dejan de casar, o
la mitad de las peticiones caen por timeout. En todos esos casos el resultado
es un conjunto de datos plausible pero incompleto.

Publicar eso destruiría la versión buena, así que se compara contra la vigente
antes de promover.
"""
from . import config


class ResultadoValidacion:
    def __init__(self, ok, motivos=None):
        self.ok = ok
        self.motivos = motivos or []

    @property
    def motivo(self):
        return "; ".join(self.motivos)

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"<Validacion ok={self.ok} motivos={self.motivos!r}>"


def validar(conteos, conteos_vigentes=None,
            min_grupos=None, min_publicaciones=None, caida_maxima=None):
    """Decide si los `conteos` recién obtenidos son aceptables.

    conteos_vigentes: los de la versión publicada actualmente. Si no hay
    ninguna (primera carga), solo se aplican los mínimos absolutos.
    """
    min_grupos = config.MIN_GRUPOS if min_grupos is None else min_grupos
    min_publicaciones = config.MIN_PUBLICACIONES if min_publicaciones is None else min_publicaciones
    caida_maxima = config.CAIDA_MAXIMA if caida_maxima is None else caida_maxima

    motivos = []
    grupos = conteos.get("grupos", 0)
    publicaciones = conteos.get("publicaciones", 0)

    if grupos < min_grupos:
        motivos.append(f"solo {grupos} grupos, se esperaban al menos {min_grupos}")
    if publicaciones < min_publicaciones:
        motivos.append(f"solo {publicaciones} publicaciones, se esperaban al menos {min_publicaciones}")

    if conteos_vigentes:
        for clave in ("grupos", "publicaciones", "miembros"):
            antes = conteos_vigentes.get(clave, 0)
            ahora = conteos.get(clave, 0)
            if antes <= 0:
                continue
            caida = (antes - ahora) / antes
            if caida > caida_maxima:
                motivos.append(
                    f"{clave} cayó {caida:.0%} respecto a la versión vigente "
                    f"({antes} → {ahora}), por encima del {caida_maxima:.0%} tolerado"
                )

    return ResultadoValidacion(not motivos, motivos)
