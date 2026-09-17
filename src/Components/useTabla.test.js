import { renderHook, act, waitFor } from "@testing-library/react";
import { useTabla } from "./useTabla";

const pagina = (items, extra = {}) => ({
  ok: true,
  status: 200,
  json: async () => ({ items, total: items.length, page: 1, pages: 1, ...extra }),
});

const urls = () => global.fetch.mock.calls.map((c) => c[0]);

beforeEach(() => {
  jest.useFakeTimers();
  global.fetch = jest.fn().mockResolvedValue(pagina([{ grupo: "A" }]));
});

afterEach(() => {
  jest.useRealTimers();
  delete global.fetch;
});

const montar = () =>
  renderHook(() => useTabla("/demo/grupos", { search: "", ciudad: "" }, { sort: "grupo", dir: "asc" }));

test("no consulta hasta que la vista se activa", async () => {
  const { result } = montar();
  act(() => { jest.advanceTimersByTime(500); });
  expect(global.fetch).not.toHaveBeenCalled();

  act(() => { result.current.activar(true); });
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
});

test("agrupa las pulsaciones seguidas en una sola consulta", async () => {
  const { result } = montar();
  act(() => { result.current.activar(true); });
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

  act(() => { result.current.setFiltro("search", "b"); });
  act(() => { result.current.setFiltro("search", "bi"); });
  act(() => { result.current.setFiltro("search", "bio"); });
  act(() => { jest.advanceTimersByTime(400); });

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(urls().pop()).toContain("search=bio");
});

test("paginar mantiene los filtros con los que se pintó la tabla", async () => {
  // Regresión: antes se enviaban los filtros del formulario, de modo que
  // escribir sin aplicar y pulsar "Siguiente" traía la página 2 de otra búsqueda.
  const { result } = montar();
  act(() => { result.current.activar(true); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());

  act(() => { result.current.setFiltro("search", "aplicado"); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(urls().pop()).toContain("search=aplicado"));

  // El usuario sigue escribiendo pero no espera a que se aplique...
  act(() => { result.current.setFiltro("search", "a-medio-escribir"); });
  act(() => { result.current.irPagina(2); });

  await waitFor(() => {
    const u = urls().pop();
    expect(u).toContain("page=2");
    expect(u).toContain("search=aplicado");
    expect(u).not.toContain("a-medio-escribir");
  });
});

test("cambiar de filtro vuelve a la primera página", async () => {
  const { result } = montar();
  act(() => { result.current.activar(true); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());

  act(() => { result.current.irPagina(3); });
  await waitFor(() => expect(urls().pop()).toContain("page=3"));

  act(() => { result.current.setFiltro("ciudad", "TUNJA"); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(urls().pop()).toContain("page=1"));
});

test("ordenar reinicia la página y viaja al servidor", async () => {
  const { result } = montar();
  act(() => { result.current.activar(true); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());

  act(() => { result.current.setOrden("n_publicaciones", "desc"); });
  await waitFor(() => {
    const u = urls().pop();
    expect(u).toContain("sort=n_publicaciones");
    expect(u).toContain("dir=desc");
    expect(u).toContain("page=1");
  });
});

test("un error del backend deja la tabla vacía y con mensaje", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => ({ error: "Datos no disponibles" }),
  });
  const { result } = montar();
  act(() => { result.current.activar(true); });

  await waitFor(() => expect(result.current.error).toBe("Datos no disponibles"));
  expect(result.current.data.items).toEqual([]);
  expect(result.current.cargando).toBe(false);
});

test("paramsExport lleva los filtros aplicados y el orden", async () => {
  const { result } = montar();
  act(() => { result.current.activar(true); });
  act(() => { result.current.setFiltro("ciudad", "TUNJA"); });
  act(() => { jest.advanceTimersByTime(400); });

  await waitFor(() => expect(result.current.paramsExport.ciudad).toBe("TUNJA"));
  expect(result.current.paramsExport.sort).toBe("grupo");
});

test("limpiar devuelve los filtros a su estado inicial", async () => {
  const { result } = montar();
  act(() => { result.current.activar(true); });
  act(() => { result.current.setFiltro("search", "algo"); });
  act(() => { jest.advanceTimersByTime(400); });
  await waitFor(() => expect(result.current.hayFiltros).toBe(true));

  act(() => { result.current.limpiar(); });
  await waitFor(() => expect(result.current.hayFiltros).toBe(false));
});
