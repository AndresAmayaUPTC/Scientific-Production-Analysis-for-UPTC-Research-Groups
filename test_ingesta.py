"""Pruebas de la ingesta: versionado, calidad, respaldo y cadena de origen.

Se usa `mongomock` para ejercitar el repositorio de verdad (inserciones,
consultas, punteros) sin depender de un Atlas real.
"""
import gzip
import json

import mongomock
import pytest

from ingesta import calidad, modelo, pipeline, respaldo
from ingesta.repositorio import Repositorio


@pytest.fixture
def repo():
    return Repositorio(mongomock.MongoClient(), "pruebas")


@pytest.fixture
def respaldos_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr("ingesta.config.DIR_RESPALDOS", tmp_path)
    monkeypatch.setattr("ingesta.respaldo.config.DIR_RESPALDOS", tmp_path)
    return tmp_path


def datos_falsos(n_grupos=120, pubs_por_grupo=60):
    grupos, miembros, publicaciones = [], [], []
    for i in range(n_grupos):
        nombre = f"GRUPO {i:03d}"
        grupos.append(modelo._doc_grupo(
            nombre, ciudad="BOYACÁ - TUNJA", lider="Líder", clasificacion="A1",
            programa="Ciencias Básicas", anio_formacion=1995,
        ))
        miembros.append(modelo._doc_miembro(nombre, f"Integrante {i}", "Activo"))
        for j in range(pubs_por_grupo):
            publicaciones.append(modelo._doc_publicacion(
                nombre, "BOYACÁ - TUNJA", "Artículos publicados", "SI", "Área", "Programa",
                f"Titulo {j} REVISTA X ISSN: 1234-5678, 2020 vol:1",
            ))
    return grupos, miembros, publicaciones


# ----------------------------------------------------------------------
# Versionado: una corrida no pisa a la anterior
# ----------------------------------------------------------------------

def test_primera_ingesta_publica_y_deja_puntero(repo):
    resultado = pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)

    assert resultado.ok
    assert resultado.estado == "publicada"
    assert repo.run_activo() == resultado.run_id
    assert repo.conteos_activos()["grupos"] == 120


def test_una_corrida_fallida_no_toca_los_datos_vigentes(repo):
    """Regresión del fallo de raíz: el scraper anterior hacía delete_many()
    ANTES de descargar, así que cualquier error dejaba la base vacía."""
    bueno = pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)
    conteos_antes = repo.conteos_activos()

    def explota():
        raise ConnectionError("el portal no responde")

    malo = pipeline.ejecutar(repo, obtener_datos=explota, guardar_respaldo=False)

    assert not malo.ok
    assert malo.estado == "fallida"
    assert "ConnectionError" in malo.error
    # Lo importante: el tablero sigue viendo exactamente lo mismo.
    assert repo.run_activo() == bueno.run_id
    assert repo.conteos_activos() == conteos_antes
    assert len(repo.leer_grupos()) == 120


def test_una_corrida_truncada_se_descarta_y_no_se_publica(repo):
    """El portal responde, pero solo devuelve un puñado de grupos."""
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)
    activo_antes = repo.run_activo()

    def a_medias():
        return datos_falsos(n_grupos=5, pubs_por_grupo=2)

    resultado = pipeline.ejecutar(repo, obtener_datos=a_medias, guardar_respaldo=False)

    assert not resultado.ok
    assert resultado.estado == "descartada"
    assert "grupos" in resultado.motivo
    assert repo.run_activo() == activo_antes
    assert repo.conteos_activos()["grupos"] == 120


def test_los_documentos_de_una_corrida_descartada_se_limpian(repo):
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)
    resultado = pipeline.ejecutar(
        repo, obtener_datos=lambda: datos_falsos(3, 1), guardar_respaldo=False
    )
    # No debe quedar basura de la corrida rechazada.
    assert repo.grupos.count_documents({"run_id": resultado.run_id}) == 0


def test_una_caida_brusca_frente_a_la_version_vigente_se_rechaza(repo):
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)

    def mitad():
        # Supera los mínimos absolutos, pero pierde el 40 % de las publicaciones.
        return datos_falsos(n_grupos=110, pubs_por_grupo=36)

    resultado = pipeline.ejecutar(repo, obtener_datos=mitad, guardar_respaldo=False)
    assert resultado.estado == "descartada"
    assert "cayó" in resultado.motivo


def test_una_segunda_corrida_buena_releva_a_la_primera(repo):
    primera = pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)
    segunda = pipeline.ejecutar(
        repo, obtener_datos=lambda: datos_falsos(130, 60), guardar_respaldo=False
    )

    assert segunda.ok
    assert repo.run_activo() == segunda.run_id != primera.run_id
    assert repo.conteos_activos()["grupos"] == 130


def test_purga_conserva_las_ejecuciones_recientes(repo):
    for n in (120, 121, 122, 123):
        pipeline.ejecutar(repo, obtener_datos=lambda n=n: datos_falsos(n, 60), guardar_respaldo=False)

    repo.purgar_ejecuciones_viejas(conservar=2)

    vivos = {d["run_id"] for d in repo.ejecuciones.find({"estado": "publicada"})}
    assert repo.run_activo() in vivos
    assert repo.grupos.count_documents({"run_id": repo.run_activo()}) == 123


# ----------------------------------------------------------------------
# Controles de calidad
# ----------------------------------------------------------------------

def test_validar_acepta_conteos_sanos():
    assert calidad.validar({"grupos": 152, "publicaciones": 18000, "miembros": 9000})


def test_validar_rechaza_por_debajo_del_minimo():
    v = calidad.validar({"grupos": 3, "publicaciones": 10})
    assert not v
    assert len(v.motivos) == 2


def test_validar_sin_version_previa_solo_exige_minimos():
    v = calidad.validar({"grupos": 152, "publicaciones": 18000}, conteos_vigentes=None)
    assert v.ok


def test_validar_tolera_una_caida_pequena():
    v = calidad.validar(
        {"grupos": 150, "publicaciones": 17500, "miembros": 9000},
        {"grupos": 152, "publicaciones": 18000, "miembros": 9100},
    )
    assert v.ok


def test_validar_ignora_conteos_vigentes_en_cero():
    v = calidad.validar(
        {"grupos": 152, "publicaciones": 18000, "miembros": 0},
        {"grupos": 152, "publicaciones": 18000, "miembros": 0},
    )
    assert v.ok


# ----------------------------------------------------------------------
# Respaldo en disco
# ----------------------------------------------------------------------

def test_guardar_y_recuperar_snapshot(respaldos_tmp):
    g, m, p = datos_falsos(10, 2)
    respaldo.guardar("20260101T000000Z", g, m, p)

    datos = respaldo.cargar_ultimo()
    assert datos["run_id"] == "20260101T000000Z"
    assert len(datos["grupos"]) == 10
    assert len(datos["publicaciones"]) == 20


def test_un_snapshot_corrupto_no_deja_sin_datos(respaldos_tmp):
    """Si el más nuevo está dañado se cae al anterior en vez de fallar."""
    g, m, p = datos_falsos(10, 2)
    respaldo.guardar("20260101T000000Z", g, m, p)

    malo = respaldos_tmp / "20260102T000000Z.json.gz"
    malo.write_bytes(b"esto no es gzip valido")

    datos = respaldo.cargar_ultimo()
    assert datos is not None
    assert datos["run_id"] == "20260101T000000Z"


def test_purga_de_snapshots_conserva_los_ultimos(respaldos_tmp, monkeypatch):
    monkeypatch.setattr("ingesta.respaldo.config.RESPALDOS_A_CONSERVAR", 2)
    g, m, p = datos_falsos(10, 1)
    for i in range(5):
        respaldo.guardar(f"2026010{i}T000000Z", g, m, p)
    assert len(respaldo.listar()) == 2


def test_el_snapshot_no_queda_a_medias_si_falla_la_escritura(respaldos_tmp):
    g, m, p = datos_falsos(5, 1)
    respaldo.guardar("20260101T000000Z", g, m, p)
    # No debe quedar ningún .tmp del proceso de escritura.
    assert list(respaldos_tmp.glob("*.tmp")) == []


def test_ingesta_publicada_deja_snapshot(repo, respaldos_tmp):
    resultado = pipeline.ejecutar(repo, obtener_datos=datos_falsos)
    assert resultado.ok
    datos = respaldo.cargar_ultimo()
    assert datos["run_id"] == resultado.run_id


def test_ingesta_descartada_no_deja_snapshot(repo, respaldos_tmp):
    pipeline.ejecutar(repo, obtener_datos=lambda: datos_falsos(3, 1), guardar_respaldo=True)
    assert respaldo.cargar_ultimo() is None


# ----------------------------------------------------------------------
# Cadena de origen del backend
# ----------------------------------------------------------------------

def test_origen_usa_mongo_cuando_hay_version_publicada(repo, monkeypatch):
    from ingesta import origen
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, guardar_respaldo=False)
    monkeypatch.setattr("ingesta.config.MONGODB_URI", "mongodb://fake")
    monkeypatch.setattr("ingesta.origen.config.MONGODB_URI", "mongodb://fake")

    repo.cerrar = lambda: None
    datos = origen.obtener(fabrica_repo=lambda: repo)

    assert datos.origen == "mongodb"
    assert datos.conteos["grupos"] == 120


def test_origen_cae_al_respaldo_si_mongo_no_responde(respaldos_tmp, monkeypatch):
    from ingesta import origen
    g, m, p = datos_falsos(120, 2)
    respaldo.guardar("20260101T000000Z", g, m, p)
    monkeypatch.setattr("ingesta.config.MONGODB_URI", "mongodb://fake")
    monkeypatch.setattr("ingesta.origen.config.MONGODB_URI", "mongodb://fake")

    def cae():
        raise ConnectionError("Atlas no responde")

    datos = origen.obtener(fabrica_repo=cae)

    assert datos.origen == "respaldo"
    assert datos.conteos["grupos"] == 120
    assert any("mongodb" in t for t in datos.intentos_fallidos)


def test_origen_cae_al_excel_si_no_hay_nada_mas(respaldos_tmp, monkeypatch):
    from ingesta import origen
    monkeypatch.setattr("ingesta.config.MONGODB_URI", "")
    monkeypatch.setattr("ingesta.origen.config.MONGODB_URI", "")

    datos = origen.obtener()

    assert datos.origen == "excel"
    assert datos.conteos["grupos"] > 100
    assert datos.conteos["publicaciones"] > 10000


def test_origen_vacio_en_mongo_no_se_sirve_como_bueno(repo, respaldos_tmp, monkeypatch):
    """Una base recién creada, sin versión publicada, no debe considerarse
    una fuente válida: hay que seguir a la siguiente de la cadena.

    Usa `respaldos_tmp` para no leer los snapshots reales del proyecto: sin
    aislar, este test cambia de resultado según lo que haya en `respaldos/`.
    """
    from ingesta import origen
    monkeypatch.setattr("ingesta.config.MONGODB_URI", "mongodb://fake")
    monkeypatch.setattr("ingesta.origen.config.MONGODB_URI", "mongodb://fake")
    repo.cerrar = lambda: None

    datos = origen.obtener(fabrica_repo=lambda: repo)

    assert datos.origen == "excel"


# ----------------------------------------------------------------------
# Arranque: decidir si toca scrapear ya
# ----------------------------------------------------------------------

def _envejecer(repo, run_id, horas):
    """Retrasa la fecha de fin de una corrida para simular el paso del tiempo."""
    from datetime import datetime, timedelta, timezone
    repo.ejecuciones.update_one(
        {"run_id": run_id},
        {"$set": {"terminada_en": datetime.now(timezone.utc) - timedelta(hours=horas)}},
    )


def test_base_vacia_dispara_ingesta_al_arrancar(repo):
    from ingesta import scheduler
    hay, motivo = scheduler.decidir_arranque(repo, horas=24)
    assert hay
    assert "ninguna versión publicada" in motivo


def test_solo_sembrada_desde_excel_dispara_scraping(repo):
    """Sembrar desde los Excel deja la base servible, pero esos datos son una
    foto antigua: al arrancar hay que ir al GrupLac igualmente."""
    from ingesta import scheduler
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="excel", guardar_respaldo=False)

    hay, motivo = scheduler.decidir_arranque(repo, horas=24)
    assert hay
    assert "GrupLac" in motivo


def test_descarga_reciente_no_vuelve_a_scrapear(repo):
    from ingesta import scheduler
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="scraper", guardar_respaldo=False)

    hay, motivo = scheduler.decidir_arranque(repo, horas=24)
    assert not hay
    assert "al día" in motivo


def test_descarga_vieja_vuelve_a_scrapear(repo):
    from ingesta import scheduler
    r = pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="scraper", guardar_respaldo=False)
    _envejecer(repo, r.run_id, horas=30)

    hay, motivo = scheduler.decidir_arranque(repo, horas=24)
    assert hay
    assert "30" in motivo


def test_una_corrida_fallida_no_cuenta_como_descarga_reciente(repo):
    """Si el último scraping falló, los datos siguen atrasados aunque haya
    quedado registro de la corrida."""
    from ingesta import scheduler
    r = pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="scraper", guardar_respaldo=False)
    _envejecer(repo, r.run_id, horas=30)
    pipeline.ejecutar(repo, obtener_datos=lambda: (_ for _ in ()).throw(ConnectionError("caído")),
                      guardar_respaldo=False)

    hay, _ = scheduler.decidir_arranque(repo, horas=24)
    assert hay


def test_los_modos_explicitos_mandan_sobre_el_estado(repo):
    from ingesta import scheduler
    pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="scraper", guardar_respaldo=False)

    assert scheduler.decidir_arranque(repo, 24, modo="true")[0] is True
    assert scheduler.decidir_arranque(repo, 24, modo="false")[0] is False


def test_decidir_arranque_admite_fechas_sin_zona(repo):
    """Mongo devuelve datetimes sin tzinfo; no debe reventar al restarlos."""
    from datetime import datetime, timedelta
    from ingesta import scheduler
    r = pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="scraper", guardar_respaldo=False)
    repo.ejecuciones.update_one(
        {"run_id": r.run_id},
        {"$set": {"terminada_en": datetime.utcnow() - timedelta(hours=48)}},
    )

    hay, motivo = scheduler.decidir_arranque(repo, horas=24)
    assert hay
    assert "48" in motivo


# ----------------------------------------------------------------------
# Normalización de documentos
# ----------------------------------------------------------------------

def test_desde_scraper_aplana_las_tres_colecciones():
    crudo = [{
        "titulo": "GRIDSE",
        "Departamento": "BOYACÁ", "Ciudad": "TUNJA",
        "Líder": "Ana Ruiz", "Clasificación": "A1 reconocido",
        "Año y mes de formación": "1992 - 9",
        "Programa nacional de ciencia y tecnología": "Ciencias Básicas",
        "Líneas de investigación": ["AUTOMATIZACIÓN"],
        "miembros": [{"Nombre del integrante": "Ana Ruiz", "Estado": "Activo"}],
        "Artículos publicados": [["Un título REVISTA ISSN: 1234-5678, 2020 vol:1"]],
        "Artículos publicados sin chulo": [["Otro título ISSN: 1234-5678, 2019 vol:2"]],
    }]
    grupos, miembros, publicaciones = modelo.desde_scraper(crudo)

    assert len(grupos) == 1
    assert grupos[0]["ciudad"] == "BOYACÁ - TUNJA"   # igual que en el Excel
    assert grupos[0]["clasificacion"] == "A1"
    assert grupos[0]["anio_formacion"] == 1992
    assert len(miembros) == 1
    assert {p["avalado"] for p in publicaciones} == {"SI", "NO"}
    assert {p["anio"] for p in publicaciones} == {2019, 2020}


def test_desde_scraper_ignora_grupos_sin_nombre():
    grupos, _, _ = modelo.desde_scraper([{"titulo": ""}, {"titulo": "   "}])
    assert grupos == []


def test_desde_excel_produce_la_misma_forma():
    from ingesta import config as icfg
    grupos, miembros, publicaciones = modelo.desde_excel(icfg.RES_XLSX, icfg.MIEM_XLSX)

    assert len(grupos) > 100
    assert len(publicaciones) > 10000
    assert set(grupos[0]) == set(modelo._doc_grupo("x"))
    assert all("anio" in p and "texto" in p for p in publicaciones[:20])


def test_escribir_lote_etiqueta_todo_con_el_run_id(repo):
    g, m, p = datos_falsos(5, 2)
    conteos = repo.escribir_lote("RUN-1", g, m, p)

    assert conteos == {"grupos": 5, "miembros": 5, "publicaciones": 10}
    assert repo.grupos.count_documents({"run_id": "RUN-1"}) == 5
    # Sin puntero activo, las lecturas no devuelven nada: los datos aún no
    # están publicados.
    assert repo.leer_grupos() == []


# ----------------------------------------------------------------------
# Portal caído
# ----------------------------------------------------------------------

class _RespuestaFalsa:
    def __init__(self, status_code):
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        raise AssertionError("no debería llegar aquí para códigos de portal caído")


@pytest.mark.parametrize("codigo", [403, 404, 500, 502, 503, 504])
def test_portal_caido_da_un_mensaje_accionable(codigo):
    """Ocurrió de verdad: SCienTI devolvió 404 de JBoss y 503 del balanceador.
    El error debe explicar que es del portal, no del scraper."""
    from ingesta.scraper import PortalNoDisponible, _revisar_respuesta

    with pytest.raises(PortalNoDisponible) as exc:
        _revisar_respuesta(_RespuestaFalsa(codigo), "https://scienti.minciencias.gov.co/x")

    mensaje = str(exc.value)
    assert str(codigo) in mensaje
    assert "no se han tocado" in mensaje


def test_una_respuesta_correcta_pasa_el_control():
    from ingesta.scraper import _revisar_respuesta

    class Ok:
        status_code = 200
        def raise_for_status(self):
            return None

    assert _revisar_respuesta(Ok(), "https://x") is None


def test_el_portal_caido_deja_los_datos_intactos(repo):
    """Recorrido completo del incidente real, de principio a fin."""
    from ingesta.scraper import PortalNoDisponible

    pipeline.ejecutar(repo, obtener_datos=datos_falsos, origen="excel", guardar_respaldo=False)
    activo_antes = repo.run_activo()
    conteos_antes = repo.conteos_activos()

    def portal_caido():
        raise PortalNoDisponible("El portal SCienTI respondió 503")

    resultado = pipeline.ejecutar(repo, obtener_datos=portal_caido, guardar_respaldo=False)

    assert resultado.estado == "fallida"
    assert "PortalNoDisponible" in resultado.error
    assert repo.run_activo() == activo_antes
    assert repo.conteos_activos() == conteos_antes


# ----------------------------------------------------------------------
# Descarga de fichas: concurrencia y reintentos
# ----------------------------------------------------------------------

def _ficha(enlace):
    return {"titulo": f"GRUPO {enlace}", "miembros": []}


class _PortalInestable:
    """Simula un portal que corta las primeras N peticiones de ciertas fichas."""

    def __init__(self, fallos_por_enlace):
        self.fallos = dict(fallos_por_enlace)
        self.llamadas = []

    def __call__(self, enlace):
        self.llamadas.append(enlace)
        if self.fallos.get(enlace, 0) > 0:
            self.fallos[enlace] -= 1
            return {}  # así responde info_grupo_publicaciones cuando falla
        return _ficha(enlace)


def test_ficha_valida_exige_titulo():
    from ingesta.scraper import _ficha_valida
    assert _ficha_valida({"titulo": "GRIDSE"})
    assert not _ficha_valida({})
    assert not _ficha_valida(None)
    # Página de error del portal: responde 200 pero sin encabezado de grupo.
    assert not _ficha_valida({"miembros": []})
    assert not _ficha_valida({"titulo": "   "})


def test_las_fichas_fallidas_se_recuperan_en_los_reintentos():
    from ingesta.scraper import descargar_fichas
    portal = _PortalInestable({"b": 1, "d": 2})
    esperas = []

    fichas = descargar_fichas(list("abcde"), portal, workers=2, rondas=3,
                              pausa=3, pausa_ronda=30, dormir=esperas.append)

    assert [f["titulo"] for f in fichas] == [f"GRUPO {x}" for x in "abcde"]
    # b se recupera en la ronda 1; d necesita la ronda 2. No hace falta la 3.
    assert portal.llamadas.count("b") == 2
    assert portal.llamadas.count("d") == 3
    assert portal.llamadas.count("a") == 1


def test_los_reintentos_esperan_y_la_espera_crece():
    from ingesta.scraper import descargar_fichas
    portal = _PortalInestable({"a": 9, "b": 9})
    esperas = []

    descargar_fichas(["a", "b"], portal, workers=1, rondas=3,
                     pausa=3, pausa_ronda=30, dormir=esperas.append)

    # Cada ronda: espera creciente y luego 3 s entre las dos fichas.
    assert esperas == [30, 3, 60, 3, 120, 3]


def test_una_ficha_que_nunca_responde_queda_en_none():
    from ingesta.scraper import descargar_fichas
    portal = _PortalInestable({"b": 99})

    fichas = descargar_fichas(["a", "b", "c"], portal, workers=2, rondas=2,
                              pausa=0, pausa_ronda=0, dormir=lambda s: None)

    assert fichas[0]["titulo"] == "GRUPO a"
    assert fichas[1] is None
    assert fichas[2]["titulo"] == "GRUPO c"
    assert portal.llamadas.count("b") == 3  # 1 pasada + 2 rondas


def test_una_excepcion_del_parser_cuenta_como_fallo_y_se_reintenta():
    from ingesta.scraper import descargar_fichas
    estado = {"n": 0}

    def explota_una_vez(enlace):
        estado["n"] += 1
        if estado["n"] == 1:
            raise AttributeError("HTML inesperado")
        return _ficha(enlace)

    fichas = descargar_fichas(["a"], explota_una_vez, workers=1, rondas=1,
                              pausa=0, pausa_ronda=0, dormir=lambda s: None)
    assert fichas[0]["titulo"] == "GRUPO a"


def test_sin_fallos_no_hay_esperas():
    from ingesta.scraper import descargar_fichas
    esperas = []
    descargar_fichas(list("abc"), _PortalInestable({}), workers=3,
                     dormir=esperas.append)
    assert esperas == []


def test_la_concurrencia_de_la_primera_pasada_respeta_workers():
    import threading
    import time as _t
    from ingesta.scraper import descargar_fichas
    activas, pico, cerrojo = [0], [0], threading.Lock()

    def lenta(enlace):
        with cerrojo:
            activas[0] += 1
            pico[0] = max(pico[0], activas[0])
        _t.sleep(0.02)
        with cerrojo:
            activas[0] -= 1
        return _ficha(enlace)

    descargar_fichas([str(i) for i in range(12)], lenta, workers=3, rondas=0)
    assert pico[0] <= 3


def test_la_sesion_aplica_timeout_por_defecto(monkeypatch):
    """requests no tiene timeout por defecto; el adaptador debe imponerlo."""
    from ingesta.scraper import crear_sesion
    capturado = {}

    def falso_send(self, request, **kwargs):
        capturado["timeout"] = kwargs.get("timeout")
        raise RuntimeError("corte")

    monkeypatch.setattr("requests.adapters.HTTPAdapter.send", falso_send)
    s = crear_sesion(timeout=17)
    with pytest.raises(RuntimeError):
        s.get("https://example.invalid/")
    assert capturado["timeout"] == 17


def test_obtener_grupos_omite_los_que_no_se_pudieron_descargar(monkeypatch):
    """Flujo completo del scraper con un portal simulado: listado de 3 grupos,
    una ficha que nunca responde."""
    from ingesta import scraper

    html = (
        '<table id="grupos"><tr><th>h</th></tr>'
        + "".join(
            f'<tr><td>{i}</td><td>x</td><td><a href="?nro={i}">G{i}</a></td><td>L</td></tr>'
            for i in (1, 2, 3)
        )
        + "</table>"
    )

    class Resp:
        status_code = 200
        text = html
        def raise_for_status(self):
            pass

    class Sesion:
        def get(self, url, **kw):
            return Resp()

    def ficha(enlace):
        return {} if enlace.endswith("=2") else {"titulo": enlace[-1], "miembros": []}

    parsers = scraper._parsers()
    monkeypatch.setattr(parsers, "info_grupo_publicaciones", ficha)
    monkeypatch.setattr("ingesta.config.SCRAPE_RETRY_ROUND_PAUSE", 0)
    monkeypatch.setattr("ingesta.config.SCRAPE_RETRY_PAUSE", 0)

    grupos = scraper.obtener_grupos(url="http://x", sesion=Sesion(), workers=2)

    assert [g["titulo"] for g in grupos] == ["1", "3"]


# ----------------------------------------------------------------------
# Recarga del backend tras una ingesta programada
# ----------------------------------------------------------------------

def test_la_tarea_programada_avisa_al_publicar(repo, respaldos_tmp, monkeypatch):
    """Regresión: la descarga programada publicaba, pero el backend seguía
    sirviendo la versión anterior desde memoria hasta reiniciarse."""
    from ingesta import scheduler
    monkeypatch.setattr("ingesta.pipeline._scrapear", datos_falsos)
    repo.cerrar = lambda: None
    avisos = []

    resultado = scheduler._tarea(lambda: repo, al_publicar=avisos.append)

    assert resultado.ok
    assert avisos == [resultado]


def test_la_tarea_programada_no_avisa_si_se_descarta(repo, respaldos_tmp, monkeypatch):
    from ingesta import scheduler
    monkeypatch.setattr("ingesta.pipeline._scrapear", lambda: datos_falsos(3, 1))
    repo.cerrar = lambda: None
    avisos = []

    resultado = scheduler._tarea(lambda: repo, al_publicar=avisos.append)

    assert resultado.estado == "descartada"
    assert avisos == []


def test_un_fallo_en_la_recarga_no_rompe_la_tarea(repo, respaldos_tmp, monkeypatch):
    from ingesta import scheduler
    monkeypatch.setattr("ingesta.pipeline._scrapear", datos_falsos)
    repo.cerrar = lambda: None

    def rompe(_):
        raise RuntimeError("recarga fallida")

    resultado = scheduler._tarea(lambda: repo, al_publicar=rompe)
    assert resultado.ok  # la versión quedó publicada igualmente


# ----------------------------------------------------------------------
# Limpieza del texto que llega del GrupLac
# ----------------------------------------------------------------------

def test_limpiar_registro_quita_el_relleno_de_guiones_bajos():
    """El parser convierte los tramos de 3+ espacios en " _ ". Ese relleno se
    veía en el tablero y dejaba el año de los libros ilegible."""
    from ingesta.texto import limpiar_registro
    crudo = ("; _ 2. - Libro resultado de investigación : INFANCIA Y RURALIDAD _ Colombia, "
             "_ 2024, _ ISBN: 978-958-660-850-3, _ Ed. editorial uptc")
    limpio = limpiar_registro(crudo)

    assert " _ " not in limpio
    assert limpio.startswith("2. - Libro")
    assert "Colombia, 2024, ISBN:" in limpio


def test_el_anio_de_los_libros_se_lee_tras_la_limpieza():
    from ingesta import modelo
    crudo = "; _ 1. - Libro resultado de investigación : Algo _ Colombia, _ 2015, _ ISBN: 3659081485"
    doc = modelo._doc_publicacion("G", "TUNJA", "Libros publicados", "SI", "", "", crudo)
    assert doc["anio"] == 2015
    assert " _ " not in doc["texto"]


def test_limpiar_registro_no_toca_un_texto_ya_limpio():
    from ingesta.texto import limpiar_registro
    t = "Publicado en revista especializada: Algo, HELIYON ISSN: 2405-8440, 2020 vol:6"
    assert limpiar_registro(t) == t
