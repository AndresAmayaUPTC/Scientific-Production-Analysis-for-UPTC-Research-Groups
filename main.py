# filename: main.py
from fastapi import FastAPI
from fastapi.responses import Response
import csv
import io
import re
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SCI-UPTC", description="API del tablero de produccion cientifica UPTC")

# Permitir CORS para el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # O restringe a tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Tablero de producción científica ----------
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from ingesta import origen

BASE_DIR = Path(__file__).resolve().parent
RES_XLSX = BASE_DIR / "extraccion-" / "resultados_grupos.xlsx"
MIEM_XLSX = BASE_DIR / "extraccion-" / "miembros_grupos.xlsx"

_demo = {"ready": False, "error": None}

# Las utilidades de normalización viven en ingesta/texto.py para que el
# scraper y el lector de Excel apliquen exactamente las mismas reglas.
# Se reexportan con los nombres de siempre para no tocar el resto del módulo.
from ingesta.texto import (  # noqa: E402
    CIUDAD_COORDS, _TILDES, _norm_txt, _norm_clas, _coords_de,
    _ANIO_PATRONES, _ANIO_MIN, _ANIO_MAX, _extraer_anio,
    _LINEA_RE, _parse_lineas, _anio_formacion,
    _STOPWORDS, _WORD_RE, _ISSN_RE, _contar_palabras,
)


def _load_demo(forzar=False, preferir=None):
    """Carga los datos en memoria y precalcula los agregados del tablero.

    La fuente ya no es el Excel sin más: se pide a `ingesta.origen`, que
    recorre MongoDB → snapshot local → Excel y devuelve la primera que
    responda. Así una caída de Atlas no deja el tablero sin datos.
    """
    if _demo.get("ready") and not forzar:
        return
    try:
        datos = origen.obtener(preferir=preferir)

        grupos_docs = datos.grupos
        miembros_docs = datos.miembros
        pubs_docs = datos.publicaciones

        pubs_df = pd.DataFrame(
            [{
                "grupo": d.get("nombre_grupo", ""),
                "ciudad": d.get("ciudad", ""),
                "tipo": d.get("tipo", ""),
                "avalado": (d.get("avalado") or "").upper(),
                "area": d.get("area", ""),
                "programa": d.get("programa", ""),
                "anio": int(d.get("anio") or 0),
                "publicacion": d.get("texto", ""),
            } for d in pubs_docs],
            columns=["grupo", "ciudad", "tipo", "avalado", "area", "programa", "anio", "publicacion"],
        )
        miem_df = pd.DataFrame(
            [{
                "grupo": d.get("nombre_grupo", ""),
                "integrante": d.get("integrante", ""),
                "estado": d.get("estado", ""),
            } for d in miembros_docs],
            columns=["grupo", "integrante", "estado"],
        )

        if pubs_df.empty:
            raise RuntimeError(f"la fuente '{datos.origen}' no trajo publicaciones")

        g = pubs_df["grupo"]
        ciudad = pubs_df["ciudad"]
        clas_pub = pubs_df["grupo"]  # se rellena desde la ficha, más abajo
        area = pubs_df["area"]
        programa = pubs_df["programa"]
        aval = pubs_df["avalado"]
        tipo = pubs_df["tipo"]
        pub = pubs_df["publicacion"]
        anio = pubs_df["anio"]
        me = miem_df["estado"].map(lambda v: _norm_txt(v).lower()) if not miem_df.empty else pd.Series(dtype=str)

        # --- Fichas de grupo, indexadas por nombre ---
        fichas = {d.get("nombre_grupo", ""): d for d in grupos_docs if d.get("nombre_grupo")}

        miembros_count = miem_df["grupo"].value_counts() if not miem_df.empty else pd.Series(dtype=int)
        pub_count = g.value_counts()

        # Todos los grupos conocidos, tengan o no publicaciones.
        nombres_grupos = sorted(set(fichas) | set(pub_count.index))

        filas_grupo = []
        for nombre in nombres_grupos:
            f = fichas.get(nombre, {})
            filas_grupo.append({
                "grupo": nombre,
                "n_publicaciones": int(pub_count.get(nombre, 0)),
                "ciudad": f.get("ciudad", ""),
                "lider": f.get("lider", ""),
                "clasificacion": f.get("clasificacion") or "Sin clasificar",
                "programa": f.get("programa", ""),
                "anio_formacion": int(f.get("anio_formacion") or 0),
                "n_miembros": int(miembros_count.get(nombre, 0)),
            })
        grupos_df = pd.DataFrame(filas_grupo)

        con_anio_mask = anio > 0
        ultimo = anio[con_anio_mask].groupby(g[con_anio_mask]).max() if con_anio_mask.any() else pd.Series(dtype=int)
        grupos_df["ultimo_anio"] = grupos_df["grupo"].map(ultimo.to_dict()).fillna(0).astype(int)
        grupos_df = grupos_df.sort_values("n_publicaciones", ascending=False)

        # La clasificación de cada publicación sale de la ficha de su grupo.
        clas_por_grupo = {n: (fichas.get(n, {}).get("clasificacion") or "Sin clasificar") for n in nombres_grupos}
        clas = g.map(clas_por_grupo).fillna("Sin clasificar")

        def top(series, n=10):
            vc = series[series != ""].value_counts().head(n)
            return [{"name": str(k), "value": int(v)} for k, v in vc.items()]

        lineas_por_grupo = {n: list(fichas.get(n, {}).get("lineas") or []) for n in nombres_grupos}
        web_por_grupo = {n: _norm_txt(fichas.get(n, {}).get("pagina_web")) for n in nombres_grupos}
        email_por_grupo = {n: _norm_txt(fichas.get(n, {}).get("email")) for n in nombres_grupos}

        # ---- Revistas: nombre en mayúsculas justo antes del ISSN ----
        journal_counts = {}
        con_revista = 0
        for txt in pub.tolist():
            m = _ISSN_RE.search(txt or "")
            if m:
                con_revista += 1
                name = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-")
                if len(name) >= 3:
                    journal_counts[name] = journal_counts.get(name, 0) + 1

        words_titulos = _contar_palabras(pub.tolist())
        words_areas = _contar_palabras(area.tolist())

        # ---- Agregados por ciudad (con coordenadas para el mapa) ----
        grupo_ciudad = {n: fichas.get(n, {}).get("ciudad", "") for n in nombres_grupos}
        ciudad_pub = ciudad[ciudad != ""].value_counts()
        ciudad_grupos = {}
        for cname in grupo_ciudad.values():
            cname = _norm_txt(cname)
            if cname:
                ciudad_grupos[cname] = ciudad_grupos.get(cname, 0) + 1
        ciudad_miem = {}
        for grp_name in (miem_df["grupo"].tolist() if not miem_df.empty else []):
            cname = _norm_txt(grupo_ciudad.get(_norm_txt(grp_name), ""))
            if cname:
                ciudad_miem[cname] = ciudad_miem.get(cname, 0) + 1
        ciudad_stats = []
        for cname, npub in ciudad_pub.items():
            coords = _coords_de(cname)
            ciudad_stats.append({
                "ciudad": cname,
                "grupos": int(ciudad_grupos.get(cname, 0)),
                "publicaciones": int(npub),
                "miembros": int(ciudad_miem.get(cname, 0)),
                "lat": coords[0] if coords else None,
                "lon": coords[1] if coords else None,
            })
        ciudad_stats.sort(key=lambda r: r["publicaciones"], reverse=True)

        # ---- Serie temporal ----
        serie = anio[con_anio_mask].value_counts().sort_index()
        por_anio = [{"anio": int(a), "value": int(v)} for a, v in serie.items()]
        anios_disponibles = [int(a) for a in serie.index]

        summary = {
            "total_publicaciones": int(len(pubs_df)),
            "total_grupos": int(len(nombres_grupos)),
            "total_miembros": int(len(miem_df)),
            "miembros_activos": int((me == "activo").sum()) if len(me) else 0,
            "miembros_inactivos": int((me == "inactivo").sum()) if len(me) else 0,
            "avalados_si": int((aval == "SI").sum()),
            "avalados_no": int((aval == "NO").sum()),
            "por_tipo": top(tipo),
            "por_clasificacion": top(clas),
            "por_ciudad": top(ciudad),
            "por_area": top(area),
            "por_programa": top(programa),
            "por_anio": por_anio,
            "anio_min": anios_disponibles[0] if anios_disponibles else 0,
            "anio_max": anios_disponibles[-1] if anios_disponibles else 0,
            "publicaciones_con_anio": int(con_anio_mask.sum()),
            "top_grupos_publicaciones": [{"name": str(k), "value": int(v)} for k, v in pub_count.head(10).items()],
            "top_grupos_miembros": [{"name": str(k), "value": int(v)} for k, v in miembros_count.head(10).items()] if len(miembros_count) else [],
        }
        _demo.clear()
        _demo.update({
            "ready": True, "error": None,
            "origen": datos.origen,
            "origen_detalle": datos.detalle,
            "origen_intentos_fallidos": getattr(datos, "intentos_fallidos", []),
            "cargado_en": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "grupos": grupos_df.to_dict(orient="records"),
            "pubs": pubs_df,
            "miem": miem_df,
            "ciudades": sorted({c for c in ciudad.unique() if _norm_txt(c)})[:60],
            "clasificaciones": sorted({c for c in clas.unique() if _norm_txt(c)}),
            "tipos": sorted({c for c in tipo.unique() if _norm_txt(c)}),
            "programas": sorted({c for c in programa.unique() if _norm_txt(c)}),
            "anios": anios_disponibles,
            "nombres_grupos": nombres_grupos,
            "lineas_por_grupo": lineas_por_grupo,
            "web_por_grupo": web_por_grupo,
            "email_por_grupo": email_por_grupo,
            "journal_counts": journal_counts,
            "revista_coverage": {"con_revista": con_revista, "total": int(len(pubs_df))},
            "words_titulos": words_titulos,
            "words_areas": words_areas,
            "ciudad_stats": ciudad_stats,
        })
    except Exception as e:
        _demo.clear()
        _demo.update({"ready": False, "error": str(e)})


_load_demo()


def _abrir_repo():
    """Conexión a Mongo bajo demanda. Se abre y cierra por petición: el
    tablero lee de memoria, así que no hace falta mantenerla viva."""
    from ingesta.repositorio import Repositorio
    return Repositorio.desde_uri()


@app.on_event("startup")
def _arrancar_planificador():
    """Programa el scraping periódico si hay Mongo configurado.

    Con `SCRAPE_SCHEDULER=false` se desactiva: es lo que conviene cuando la
    ingesta la dispara un cron externo o hay varias réplicas del backend, para
    que no scrapeen todas a la vez.
    """
    import os
    from ingesta import config as icfg, scheduler

    if os.getenv("SCRAPE_SCHEDULER", "true").lower() != "true":
        return
    if not icfg.mongo_configurado():
        return
    try:
        scheduler.iniciar_en_segundo_plano(
            _abrir_repo,
            al_publicar=lambda r: _load_demo(forzar=True, preferir="mongodb"),
        )
    except Exception as e:  # pragma: no cover - depende del entorno
        print(f"No se pudo iniciar el planificador de ingesta: {e}")


@app.on_event("shutdown")
def _detener_planificador():
    from ingesta import scheduler
    scheduler.detener()


def _error_datos():
    return {"error": _demo.get("error") or "Datos no disponibles"}


def _paginate(items, page, page_size):
    total = len(items)
    page_size = min(max(1, page_size), 100)
    pages = max(1, -(-total // page_size))
    page = min(max(1, page), pages)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


def _ordenar(items, sort, direccion, permitidos, defecto):
    """Ordena una lista de dicts por un campo de la lista blanca."""
    campo = sort if sort in permitidos else defecto
    reverse = str(direccion).lower() != "asc"
    return sorted(
        items,
        key=lambda r: (r.get(campo) is None, _clave_orden(r.get(campo))),
        reverse=reverse,
    )


def _clave_orden(v):
    """Números tal cual; texto en minúsculas para que el orden sea natural."""
    if isinstance(v, (int, float)):
        return v
    return str(v or "").lower()


ORDEN_GRUPOS = {"grupo", "ciudad", "lider", "clasificacion", "n_publicaciones", "n_miembros", "anio_formacion", "ultimo_anio"}
ORDEN_PUBS = {"grupo", "tipo", "avalado", "anio", "publicacion"}
ORDEN_MIEM = {"grupo", "integrante", "estado"}


def _filtrar_grupos(search="", ciudad="", clasificacion="", programa="",
                    sort="n_publicaciones", dir="desc"):
    """Grupos filtrados y ordenados (misma lógica para JSON y CSV)."""
    items = _demo["grupos"]
    s = search.strip().lower()
    if s:
        items = [r for r in items if s in r["grupo"].lower() or s in r["lider"].lower()]
    if ciudad:
        items = [r for r in items if r["ciudad"] == ciudad]
    if clasificacion:
        items = [r for r in items if r["clasificacion"] == clasificacion]
    if programa:
        items = [r for r in items if r["programa"] == programa]
    return _ordenar(items, sort, dir, ORDEN_GRUPOS, "n_publicaciones")


def _rango_anios(df, anio_desde=0, anio_hasta=0):
    """Máscara del rango temporal. Las filas sin año (0) quedan fuera
    en cuanto se pide un rango, porque no se pueden ubicar en el tiempo."""
    mask = pd.Series(True, index=df.index)
    if anio_desde:
        mask &= (df["anio"] >= anio_desde) & (df["anio"] > 0)
    if anio_hasta:
        mask &= (df["anio"] <= anio_hasta) & (df["anio"] > 0)
    return mask


def _filtrar_pubs(search="", grupo="", tipo="", avalado="", programa="",
                  anio_desde=0, anio_hasta=0, sort="grupo", dir="asc"):
    """Publicaciones filtradas con texto completo (misma lógica para JSON y CSV).

    La búsqueda es literal (regex=False): el usuario puede escribir
    paréntesis, '+' o '*' sin romper el endpoint.
    """
    df = _demo["pubs"]
    mask = _rango_anios(df, anio_desde, anio_hasta)
    if grupo:
        mask &= df["grupo"].str.contains(grupo, case=False, na=False, regex=False)
    if tipo:
        mask &= df["tipo"] == tipo
    if avalado:
        mask &= df["avalado"] == avalado.upper()
    if programa:
        mask &= df["programa"] == programa
    if search:
        mask &= df["publicacion"].str.contains(search, case=False, na=False, regex=False)
    sub = df[mask]
    items = [
        {"grupo": r.grupo, "ciudad": r.ciudad, "tipo": r.tipo, "avalado": r.avalado,
         "anio": int(r.anio), "publicacion": r.publicacion}
        for r in sub.itertuples()
    ]
    return _ordenar(items, sort, dir, ORDEN_PUBS, "grupo") if sort else items


def _filtrar_miem(search="", grupo="", estado="", sort="grupo", dir="asc"):
    """Miembros filtrados (misma lógica para JSON y CSV)."""
    df = _demo["miem"]
    mask = pd.Series(True, index=df.index)
    if grupo:
        mask &= df["grupo"].str.contains(grupo, case=False, na=False, regex=False)
    if estado:
        mask &= df["estado"].str.lower() == estado.lower()
    if search:
        mask &= df["integrante"].str.contains(search, case=False, na=False, regex=False)
    sub = df[mask]
    items = [{"grupo": r.grupo, "integrante": r.integrante, "estado": r.estado} for r in sub.itertuples()]
    return _ordenar(items, sort, dir, ORDEN_MIEM, "grupo")


def _csv_response(filename: str, headers: list, rows: list):
    """CSV con BOM y separador ';' para abrir directo en Excel en español."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(headers)
    w.writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/demo/estado")
def demo_estado():
    """Salud de la carga de datos: qué fuente se está sirviendo y por qué."""
    return {
        "ready": bool(_demo.get("ready")),
        "error": _demo.get("error"),
        "publicaciones": _demo.get("summary", {}).get("total_publicaciones", 0),
        "origen": _demo.get("origen"),
        "origen_detalle": _demo.get("origen_detalle"),
        "origen_intentos_fallidos": _demo.get("origen_intentos_fallidos", []),
        "cargado_en": _demo.get("cargado_en"),
    }


@app.post("/demo/recargar")
def demo_recargar(preferir: str = ""):
    """Recarga los datos en memoria recorriendo de nuevo la cadena de origen.

    `preferir` fuerza una fuente concreta (mongodb | respaldo | excel); si esa
    falla, se sigue probando el resto igualmente.
    """
    _load_demo(forzar=True, preferir=preferir or None)
    if not _demo.get("ready"):
        return _error_datos()
    return {
        "ok": True,
        "origen": _demo.get("origen"),
        "publicaciones": _demo["summary"]["total_publicaciones"],
    }


# ---------- Administración de la ingesta ----------

@app.get("/admin/ingesta/estado")
def ingesta_estado():
    """Estado del scraping periódico y de la base: última corrida, versión
    publicada, próxima ejecución y snapshots disponibles."""
    from ingesta import config as icfg, respaldo, scheduler

    salida = {
        "origen_en_uso": _demo.get("origen"),
        "mongo_configurado": icfg.mongo_configurado(),
        "base_datos": icfg.MONGODB_DB,
        "intervalo_horas": icfg.INTERVALO_HORAS,
        "planificador_activo": scheduler.activo(),
        "proxima_ejecucion": scheduler.proxima_ejecucion(),
        "respaldos": respaldo.info(),
        "mongo": None,
    }
    if icfg.mongo_configurado():
        try:
            repo = _abrir_repo()
            try:
                repo.ping()
                pendiente, motivo = scheduler.decidir_arranque(
                    repo, icfg.INTERVALO_HORAS, icfg.EJECUTAR_AL_ARRANCAR
                )
                salida["mongo"] = {
                    "conectado": True,
                    "run_activo": repo.run_activo(),
                    "conteos": repo.conteos_activos(),
                    "ultima_ejecucion": repo.ultima_ejecucion(),
                    "ultima_descarga_gruplac": repo.ultima_publicacion(origen="scraper"),
                }
                salida["datos_atrasados"] = pendiente
                salida["motivo"] = motivo
            finally:
                repo.cerrar()
        except Exception as e:
            salida["mongo"] = {"conectado": False, "error": f"{type(e).__name__}: {e}"}
    return salida


@app.get("/admin/ingesta/historial")
def ingesta_historial(limite: int = 10):
    """Últimas corridas, con su estado y por qué se descartaron las que no
    llegaron a publicarse."""
    from ingesta import config as icfg
    if not icfg.mongo_configurado():
        return {"error": "MONGODB_URI no está configurada"}
    try:
        repo = _abrir_repo()
        try:
            return {"items": repo.historial(min(max(1, limite), 50))}
        finally:
            repo.cerrar()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@app.post("/admin/ingesta/ejecutar")
def ingesta_ejecutar(origen_datos: str = "scraper"):
    """Lanza una ingesta ahora mismo, sin esperar al planificador.

    origen_datos: 'scraper' (GrupLac) o 'excel' (siembra desde los .xlsx).
    Si la corrida no supera los controles de calidad se descarta y el tablero
    sigue con la versión anterior.
    """
    from ingesta import config as icfg, pipeline
    if not icfg.mongo_configurado():
        return {"error": "MONGODB_URI no está configurada"}
    try:
        repo = _abrir_repo()
        try:
            repo.crear_indices()
            if origen_datos == "excel":
                resultado = pipeline.sembrar_desde_excel(repo)
            else:
                resultado = pipeline.ejecutar(repo)
        finally:
            repo.cerrar()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    if resultado.ok:
        _load_demo(forzar=True)
    return resultado.as_dict()


@app.get("/demo/summary")
def demo_summary():
    if not _demo.get("ready"):
        return _error_datos()
    return _demo["summary"]


@app.get("/demo/filtros")
def demo_filtros():
    if not _demo.get("ready"):
        return _error_datos()
    return {
        "ciudades": _demo["ciudades"],
        "clasificaciones": _demo["clasificaciones"],
        "tipos": _demo["tipos"],
        "programas": _demo["programas"],
        "grupos": _demo["nombres_grupos"],
        "anios": _demo["anios"],
    }


@app.get("/demo/grupos")
def demo_grupos(search: str = "", ciudad: str = "", clasificacion: str = "", programa: str = "",
                sort: str = "n_publicaciones", dir: str = "desc", page: int = 1, page_size: int = 20):
    if not _demo.get("ready"):
        return _error_datos()
    return _paginate(_filtrar_grupos(search, ciudad, clasificacion, programa, sort, dir), page, page_size)


@app.get("/demo/grupos.csv")
def demo_grupos_csv(search: str = "", ciudad: str = "", clasificacion: str = "", programa: str = "",
                    sort: str = "n_publicaciones", dir: str = "desc"):
    if not _demo.get("ready"):
        return _error_datos()
    items = _filtrar_grupos(search, ciudad, clasificacion, programa, sort, dir)
    return _csv_response(
        "sciuptc_grupos.csv",
        ["Grupo", "Ciudad", "Lider", "Clasificacion", "Programa", "Ano formacion", "Publicaciones", "Miembros", "Ultimo ano"],
        [[r["grupo"], r["ciudad"], r["lider"], r["clasificacion"], r["programa"],
          r["anio_formacion"] or "", r["n_publicaciones"], r["n_miembros"], r["ultimo_anio"] or ""] for r in items],
    )


@app.get("/demo/publicaciones")
def demo_publicaciones(search: str = "", grupo: str = "", tipo: str = "", avalado: str = "",
                       programa: str = "", anio_desde: int = 0, anio_hasta: int = 0,
                       sort: str = "grupo", dir: str = "asc", page: int = 1, page_size: int = 20):
    if not _demo.get("ready"):
        return _error_datos()
    items = _filtrar_pubs(search, grupo, tipo, avalado, programa, anio_desde, anio_hasta, sort, dir)
    # En JSON se trunca para la tabla; el CSV lleva el texto completo.
    cortos = [
        {**r, "publicacion": (r["publicacion"][:300] + "…") if len(r["publicacion"]) > 300 else r["publicacion"]}
        for r in items
    ]
    return _paginate(cortos, page, page_size)


@app.get("/demo/publicaciones.csv")
def demo_publicaciones_csv(search: str = "", grupo: str = "", tipo: str = "", avalado: str = "",
                           programa: str = "", anio_desde: int = 0, anio_hasta: int = 0,
                           sort: str = "grupo", dir: str = "asc"):
    if not _demo.get("ready"):
        return _error_datos()
    items = _filtrar_pubs(search, grupo, tipo, avalado, programa, anio_desde, anio_hasta, sort, dir)
    return _csv_response(
        "sciuptc_publicaciones.csv",
        ["Grupo", "Ciudad", "Tipo", "Avalado", "Ano", "Publicacion"],
        [[r["grupo"], r["ciudad"], r["tipo"], r["avalado"], r["anio"] or "", r["publicacion"]] for r in items],
    )


@app.get("/demo/miembros")
def demo_miembros(search: str = "", grupo: str = "", estado: str = "",
                  sort: str = "grupo", dir: str = "asc", page: int = 1, page_size: int = 20):
    if not _demo.get("ready"):
        return _error_datos()
    return _paginate(_filtrar_miem(search, grupo, estado, sort, dir), page, page_size)


@app.get("/demo/miembros.csv")
def demo_miembros_csv(search: str = "", grupo: str = "", estado: str = "",
                      sort: str = "grupo", dir: str = "asc"):
    if not _demo.get("ready"):
        return _error_datos()
    items = _filtrar_miem(search, grupo, estado, sort, dir)
    return _csv_response(
        "sciuptc_miembros.csv",
        ["Grupo", "Integrante", "Estado"],
        [[r["grupo"], r["integrante"], r["estado"]] for r in items],
    )


@app.get("/demo/ciudades.csv")
def demo_ciudades_csv():
    if not _demo.get("ready"):
        return _error_datos()
    return _csv_response(
        "sciuptc_ciudades.csv",
        ["Ciudad", "Grupos", "Publicaciones", "Miembros"],
        [[c["ciudad"], c["grupos"], c["publicaciones"], c["miembros"]] for c in _demo["ciudad_stats"]],
    )


@app.get("/demo/nube")
def demo_nube(fuente: str = "titulos", limite: int = 80):
    """Palabras más frecuentes para la nube de palabras.

    fuente: 'titulos' (texto de publicaciones) o 'areas' (áreas de conocimiento).
    """
    if not _demo.get("ready"):
        return _error_datos()
    counter = _demo["words_areas"] if fuente == "areas" else _demo["words_titulos"]
    limite = min(max(1, limite), 200)
    return {
        "fuente": "areas" if fuente == "areas" else "titulos",
        "items": [{"text": w, "value": int(c)} for w, c in counter.most_common(limite)],
    }


@app.get("/demo/ciudades")
def demo_ciudades():
    """Agregados por ciudad, con coordenadas para el mapa."""
    if not _demo.get("ready"):
        return _error_datos()
    return {"items": _demo["ciudad_stats"]}


@app.get("/demo/revistas")
def demo_revistas(limite: int = 25):
    """Revistas/fuentes más frecuentes (nombre extraído antes del ISSN)."""
    if not _demo.get("ready"):
        return _error_datos()
    limite = min(max(1, limite), 100)
    ranked = sorted(_demo["journal_counts"].items(), key=lambda kv: kv[1], reverse=True)[:limite]
    return {
        "items": [{"name": name, "value": int(n)} for name, n in ranked],
        "con_revista": _demo["revista_coverage"]["con_revista"],
        "total_publicaciones": _demo["revista_coverage"]["total"],
    }


@app.get("/demo/serie")
def demo_serie(grupo: str = "", tipo: str = "", programa: str = "", avalado: str = ""):
    """Publicaciones por año, opcionalmente acotadas a un grupo/tipo/programa."""
    if not _demo.get("ready"):
        return _error_datos()
    df = _demo["pubs"]
    mask = df["anio"] > 0
    if grupo:
        mask &= df["grupo"] == grupo
    if tipo:
        mask &= df["tipo"] == tipo
    if programa:
        mask &= df["programa"] == programa
    if avalado:
        mask &= df["avalado"] == avalado.upper()
    serie = df[mask]["anio"].value_counts().sort_index()
    return {"items": [{"anio": int(a), "value": int(v)} for a, v in serie.items()]}


@app.get("/demo/grupo")
def demo_grupo(nombre: str = ""):
    """Detalle de un grupo: ficha + agregados + muestra de productos y miembros."""
    if not _demo.get("ready"):
        return _error_datos()
    target = _norm_txt(nombre)
    if not target:
        return {"error": "Indica el parámetro 'nombre' del grupo."}
    match = next((n for n in _demo["nombres_grupos"] if n.lower() == target.lower()), None)
    if not match:
        candidatos = [n for n in _demo["nombres_grupos"] if target.lower() in n.lower()][:5]
        return {"error": f"Grupo no encontrado: {nombre}", "sugerencias": candidatos}

    pubs = _demo["pubs"]
    miem = _demo["miem"]
    gpubs = pubs[pubs["grupo"] == match]
    gmiem = miem[miem["grupo"] == match]

    def _top_list(series, n=8):
        vc = series[series != ""].value_counts().head(n)
        return [{"name": str(k), "value": int(v)} for k, v in vc.items()]

    ficha = next((r for r in _demo["grupos"] if r["grupo"] == match), {})
    si = int((gpubs["avalado"] == "SI").sum())
    no = int((gpubs["avalado"] == "NO").sum())
    serie = gpubs[gpubs["anio"] > 0]["anio"].value_counts().sort_index()
    # Las publicaciones más recientes primero: es lo que se quiere ver en la ficha.
    recientes = gpubs.sort_values("anio", ascending=False)
    return {
        "grupo": match,
        "ciudad": ficha.get("ciudad", ""),
        "lider": ficha.get("lider", ""),
        "clasificacion": ficha.get("clasificacion", ""),
        "programa": ficha.get("programa", ""),
        "anio_formacion": ficha.get("anio_formacion", 0),
        "ultimo_anio": ficha.get("ultimo_anio", 0),
        "web": _demo["web_por_grupo"].get(match, ""),
        "email": _demo["email_por_grupo"].get(match, ""),
        "lineas": _demo["lineas_por_grupo"].get(match, []),
        "n_publicaciones": int(len(gpubs)),
        "n_miembros": int(len(gmiem)),
        "avalados_si": si,
        "avalados_no": no,
        "por_tipo": _top_list(gpubs["tipo"]),
        "top_areas": _top_list(gpubs["area"]),
        "por_anio": [{"anio": int(a), "value": int(v)} for a, v in serie.items()],
        "publicaciones": [
            {"tipo": r.tipo, "avalado": r.avalado, "anio": int(r.anio),
             "publicacion": (r.publicacion[:300] + "…") if len(r.publicacion) > 300 else r.publicacion}
            for r in recientes.itertuples()
        ][:15],
        "miembros": [
            {"integrante": r.integrante, "estado": r.estado} for r in gmiem.itertuples()
        ][:200],
    }
