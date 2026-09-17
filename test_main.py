# Pruebas del backend del tablero.
#   .venv/Scripts/python -m pytest -q
import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


# ---------- Extracción de año ----------

@pytest.mark.parametrize("texto,esperado", [
    # Artículo: el año va después del ISSN.
    ("Publicado en revista especializada: Algo, HELIYON ISSN: 2405-8440, 2020 vol:6 fasc: 2020", 2020),
    # Libro: el año va antes del ISBN.
    ("Libro resultado de investigación : Titulo España, 2015, ISBN: 3659081485, Ed. editorial", 2015),
    # Capítulo: hay un tramo intermedio entre el año y el ISBN.
    ("Capítulo de libro : Titulo Colombia, 2020, Libro Experiencias, ISBN: 9789588966335, Vol.", 2020),
    ("Sin ninguna fecha reconocible", 0),
    ("", 0),
    (None, 0),
])
def test_extraer_anio(texto, esperado):
    assert main._extraer_anio(texto) == esperado


def test_extraer_anio_ignora_valores_imposibles():
    assert main._extraer_anio("ISSN: 1234-5678, 1780 vol:1") == 0
    assert main._extraer_anio("ISSN: 1234-5678, 2099 vol:1") == 0


def test_no_toma_digitos_del_isbn_como_anio():
    """El ISBN contiene tramos como '2013' que no son el año de edición."""
    assert main._extraer_anio("Titulo Colombia, 2004, ISBN: 978-2013-660-201-3, Ed. Uptc") == 2004


# ---------- Normalización ----------

def test_norm_txt_limpia_marcadores_vacios():
    assert main._norm_txt("  Hola  ") == "Hola"
    assert main._norm_txt("nan") == ""
    assert main._norm_txt("-") == ""
    assert main._norm_txt(None) == ""
    assert main._norm_txt(float("nan")) == ""


def test_norm_clas_usa_primera_palabra():
    assert main._norm_clas("A1 reconocido") == "A1"
    assert main._norm_clas("") == "Sin clasificar"


def test_parse_lineas():
    txt = "1. - AUTOMATIZACION\n2. - ENERGIAS Y MEDIO AMBIENTE"
    assert main._parse_lineas(txt) == ["AUTOMATIZACION", "ENERGIAS Y MEDIO AMBIENTE"]
    assert main._parse_lineas("") == []


def test_anio_formacion():
    assert main._anio_formacion("1992 - 9") == 1992
    assert main._anio_formacion("sin fecha") == 0


def test_coords_de_ignora_tildes():
    assert main._coords_de("BOYACÁ - TUNJA") == main._coords_de("BOYACA - TUNJA")
    assert main._coords_de("Ciudad Inventada") is None


# ---------- Paginación y orden ----------

def test_paginate_acota_la_pagina_al_rango_valido():
    datos = list(range(10))
    assert main._paginate(datos, page=99, page_size=3)["page"] == 4
    assert main._paginate(datos, page=0, page_size=3)["page"] == 1
    assert main._paginate([], page=1, page_size=10)["pages"] == 1


def test_ordenar_solo_acepta_campos_de_la_lista_blanca():
    items = [{"a": 2, "b": "x"}, {"a": 1, "b": "y"}]
    ordenado = main._ordenar(items, "campo_inventado", "asc", {"a"}, "a")
    assert [r["a"] for r in ordenado] == [1, 2]  # cayó al campo por defecto


def test_ordenar_texto_es_insensible_a_mayusculas():
    items = [{"n": "beta"}, {"n": "Alfa"}]
    assert [r["n"] for r in main._ordenar(items, "n", "asc", {"n"}, "n")] == ["Alfa", "beta"]


# ---------- Filtros ----------

def test_busqueda_con_caracteres_de_regex_no_lanza():
    """Regresión: sin regex=False, 'C++ (x)' rompía el endpoint con re.error."""
    for termino in ["C++ (nuevo)", "[*", "a)b", "?", "\\"]:
        assert isinstance(main._filtrar_pubs(search=termino), list)
        assert isinstance(main._filtrar_miem(search=termino), list)


def test_filtro_por_rango_de_anios_excluye_los_sin_anio():
    res = main._filtrar_pubs(anio_desde=2020, anio_hasta=2020)
    assert res, "deberían existir publicaciones de 2020"
    assert all(r["anio"] == 2020 for r in res)


def test_filtro_de_grupos_por_texto():
    todos = main._filtrar_grupos()
    assert len(todos) > 0
    alguno = todos[0]["grupo"]
    filtrado = main._filtrar_grupos(search=alguno[:8])
    assert any(r["grupo"] == alguno for r in filtrado)


# ---------- Endpoints ----------

def test_estado():
    d = client.get("/demo/estado").json()
    assert d["ready"] is True
    assert d["publicaciones"] > 0


def test_summary_trae_serie_temporal():
    d = client.get("/demo/summary").json()
    assert d["por_anio"], "la serie anual no debería venir vacía"
    assert d["anio_min"] <= d["anio_max"]
    assert 0 < d["publicaciones_con_anio"] <= d["total_publicaciones"]
    anios = [p["anio"] for p in d["por_anio"]]
    assert anios == sorted(anios), "la serie debe venir ordenada por año"


def test_filtros_expone_las_dimensiones_nuevas():
    d = client.get("/demo/filtros").json()
    for clave in ("ciudades", "clasificaciones", "tipos", "programas", "grupos", "anios"):
        assert clave in d, f"falta {clave}"


def test_busqueda_con_parentesis_responde_200():
    r = client.get("/demo/publicaciones", params={"search": "C++ (nuevo)"})
    assert r.status_code == 200
    assert "items" in r.json()


def test_publicaciones_ordenadas_por_anio_desc():
    d = client.get("/demo/publicaciones", params={"sort": "anio", "dir": "desc", "page_size": 20}).json()
    anios = [r["anio"] for r in d["items"]]
    assert anios == sorted(anios, reverse=True)


def test_ciudades_traen_coordenadas():
    items = client.get("/demo/ciudades").json()["items"]
    ubicadas = [c for c in items if c["lat"] is not None]
    assert len(ubicadas) >= 5
    for c in ubicadas:
        assert -5 < c["lat"] < 14, "latitud fuera de Colombia"
        assert -80 < c["lon"] < -66, "longitud fuera de Colombia"


def test_grupo_inexistente_devuelve_error_con_sugerencias():
    d = client.get("/demo/grupo", params={"nombre": "no-existe-este-grupo"}).json()
    assert "error" in d
    assert "sugerencias" in d


def test_ficha_de_grupo_completa():
    nombre = client.get("/demo/grupos", params={"page_size": 1}).json()["items"][0]["grupo"]
    d = client.get("/demo/grupo", params={"nombre": nombre}).json()
    for clave in ("por_anio", "lineas", "programa", "anio_formacion", "ultimo_anio", "por_tipo"):
        assert clave in d, f"falta {clave} en la ficha"
    assert d["n_publicaciones"] > 0
    # Las publicaciones de la ficha llegan de la más reciente a la más antigua.
    anios = [p["anio"] for p in d["publicaciones"]]
    assert anios == sorted(anios, reverse=True)


def test_csv_lleva_bom_y_punto_y_coma():
    r = client.get("/demo/grupos.csv", params={"page_size": 5})
    assert r.status_code == 200
    texto = r.content.decode("utf-8")
    assert texto.startswith("﻿"), "Excel necesita el BOM para leer las tildes"
    assert ";" in texto.splitlines()[0]


def test_serie_filtrada_por_grupo():
    nombre = client.get("/demo/grupos", params={"page_size": 1}).json()["items"][0]["grupo"]
    d = client.get("/demo/serie", params={"grupo": nombre}).json()
    assert "items" in d
    assert all(p["anio"] > 0 for p in d["items"])
