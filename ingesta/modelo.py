"""Forma de los documentos que consume el tablero.

Tres colecciones planas en vez del documento anidado que usaba el scraper
anterior (un grupo con sus publicaciones dentro). Plano permite paginar,
filtrar por año y contar sin traer publicaciones enteras a memoria.

    grupos:        un documento por grupo
    miembros:      un documento por integrante
    publicaciones: un documento por producto

Hay dos orígenes que producen exactamente esta forma:
  - `desde_scraper()`  a partir de lo que devuelve el scraping del GrupLac
  - `desde_excel()`    a partir de los .xlsx de `extraccion-/`
El segundo permite sembrar la base sin esperar a un scraping correcto.
"""
from .texto import (
    _anio_formacion, _extraer_anio, _norm_clas, _norm_txt, _parse_lineas,
    limpiar_registro,
)

TIPOS_PUBLICACION = [
    "Artículos publicados",
    "Otros artículos publicados",
    "Libros publicados",
    "Capítulos de libro publicados",
]


def _doc_grupo(nombre, **campos):
    """Documento de grupo con todas las claves presentes, aunque vengan vacías,
    para que el tablero no tenga que comprobar la existencia de cada una."""
    return {
        "nombre_grupo": nombre,
        "ciudad": campos.get("ciudad", ""),
        "lider": campos.get("lider", ""),
        "clasificacion": campos.get("clasificacion", "Sin clasificar"),
        "programa": campos.get("programa", ""),
        "area_conocimiento": campos.get("area_conocimiento", ""),
        "anio_formacion": campos.get("anio_formacion", 0),
        "pagina_web": campos.get("pagina_web", ""),
        "email": campos.get("email", ""),
        "lineas": campos.get("lineas", []),
    }


def _doc_publicacion(grupo, ciudad, tipo, avalado, area, programa, texto):
    texto = limpiar_registro(texto)
    return {
        "nombre_grupo": grupo,
        "ciudad": ciudad,
        "tipo": tipo,
        "avalado": avalado,
        "area": area,
        "programa": programa,
        "anio": _extraer_anio(texto),
        "texto": texto,
    }


def _doc_miembro(grupo, integrante, estado):
    return {
        "nombre_grupo": grupo,
        "integrante": integrante,
        "estado": estado,
    }


# ----------------------------------------------------------------------
# Origen 1: salida del scraper
# ----------------------------------------------------------------------
def desde_scraper(resultados):
    """Aplana la lista de grupos del scraper en las tres colecciones."""
    grupos, miembros, publicaciones = [], [], []

    for r in resultados or []:
        nombre = _norm_txt(r.get("titulo") or r.get("nombre_grupo"))
        if not nombre:
            continue
        ciudad = _norm_txt(r.get("Ciudad") or r.get("ciudad"))
        departamento = _norm_txt(r.get("Departamento") or r.get("departamento"))
        # El Excel guarda "DEPARTAMENTO - CIUDAD"; se reproduce para que el
        # mapa y los filtros casen con los datos históricos.
        ciudad_full = f"{departamento} - {ciudad}" if departamento and ciudad else (ciudad or departamento)
        programa = _norm_txt(r.get("Programa nacional de ciencia y tecnología") or r.get("programa"))
        area = _norm_txt(r.get("Área de conocimiento") or r.get("area_conocimiento"))

        lineas = r.get("Líneas de investigación") or r.get("lineas_investigacion") or []
        if isinstance(lineas, str):
            lineas = _parse_lineas(lineas)

        grupos.append(_doc_grupo(
            nombre,
            ciudad=ciudad_full,
            lider=_norm_txt(r.get("Líder") or r.get("lider")),
            clasificacion=_norm_clas(r.get("Clasificación") or r.get("clasificacion")),
            programa=programa,
            area_conocimiento=area,
            anio_formacion=_anio_formacion(r.get("Año y mes de formación") or r.get("año_mes_formacion")),
            pagina_web=_norm_txt(r.get("Página web") or r.get("pagina_web")),
            email=_norm_txt(r.get("E-mail") or r.get("email")),
            lineas=[l for l in (_norm_txt(x) for x in lineas) if l],
        ))

        for m in r.get("miembros", []) or []:
            integrante = _norm_txt(m.get("Nombre del integrante") or m.get("nombre_integrante"))
            if integrante:
                miembros.append(_doc_miembro(
                    nombre, integrante, _norm_txt(m.get("Estado") or m.get("estado")) or "Desconocido"
                ))

        # El scraper separa cada tipo en dos claves: avalados y "sin chulo".
        for tipo in TIPOS_PUBLICACION:
            for clave, avalado in ((tipo, "SI"), (f"{tipo} sin chulo", "NO")):
                for pub in r.get(clave, []) or []:
                    texto = "; ".join(pub) if isinstance(pub, (list, tuple)) else _norm_txt(pub)
                    if texto:
                        publicaciones.append(
                            _doc_publicacion(nombre, ciudad_full, tipo, avalado, area, programa, texto)
                        )

    return grupos, miembros, publicaciones


# ----------------------------------------------------------------------
# Origen 2: los Excel de extraccion-
# ----------------------------------------------------------------------
def desde_excel(ruta_resultados, ruta_miembros):
    """Lee los .xlsx y produce la misma forma de documentos.

    Sirve para sembrar la base la primera vez y como origen de emergencia si
    el portal del GrupLac lleva tiempo caído.
    """
    import pandas as pd

    res = pd.read_excel(ruta_resultados, sheet_name=0)
    mie = pd.read_excel(ruta_miembros, sheet_name=0)

    publicaciones = []
    fichas = {}
    for fila in res.itertuples(index=False):
        nombre = _norm_txt(fila[0])
        if not nombre:
            continue
        ciudad = _norm_txt(fila[2])
        area = _norm_txt(fila[8])
        programa = _norm_txt(fila[9])
        if nombre not in fichas:
            fichas[nombre] = _doc_grupo(
                nombre,
                ciudad=ciudad,
                lider=_norm_txt(fila[3]),
                clasificacion=_norm_clas(fila[7]),
                programa=programa,
                area_conocimiento=area,
                anio_formacion=_anio_formacion(fila[1]),
                pagina_web=_norm_txt(fila[5]),
                email=_norm_txt(fila[6]),
                lineas=_parse_lineas(fila[12]),
            )
        texto = _norm_txt(fila[15])
        if texto:
            publicaciones.append(_doc_publicacion(
                nombre, ciudad, _norm_txt(fila[14]),
                _norm_txt(fila[13]).upper(), area, programa, texto,
            ))

    miembros = []
    for fila in mie.itertuples(index=False):
        grupo = _norm_txt(fila[0])
        integrante = _norm_txt(fila[1])
        if grupo and integrante:
            miembros.append(_doc_miembro(grupo, integrante, _norm_txt(fila[2]) or "Desconocido"))

    return list(fichas.values()), miembros, publicaciones
