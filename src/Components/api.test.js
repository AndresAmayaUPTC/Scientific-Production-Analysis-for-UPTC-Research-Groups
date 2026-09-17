import { getJSON, getPaged } from "./api";

const respuesta = (body, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
});

afterEach(() => {
  delete global.fetch;
});

describe("getJSON", () => {
  test("devuelve el cuerpo cuando la respuesta es correcta", async () => {
    global.fetch = jest.fn().mockResolvedValue(respuesta({ total: 3 }));
    await expect(getJSON("/demo/summary")).resolves.toEqual({ total: 3 });
  });

  test("convierte el {error} del backend en excepción", async () => {
    // Regresión: antes este cuerpo llegaba tal cual a la tabla y el render
    // reventaba al hacer .items.map() sobre undefined.
    global.fetch = jest.fn().mockResolvedValue(respuesta({ error: "Datos no disponibles" }));
    await expect(getJSON("/demo/grupos")).rejects.toThrow("Datos no disponibles");
  });

  test("conserva las sugerencias que acompañan al error", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      respuesta({ error: "Grupo no encontrado", sugerencias: ["GRIDSE"] })
    );
    await expect(getJSON("/demo/grupo")).rejects.toMatchObject({ sugerencias: ["GRIDSE"] });
  });

  test("informa con claridad cuando el backend no responde", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(getJSON("/demo/summary")).rejects.toThrow(/No se pudo conectar/);
  });

  test("informa el código cuando el servidor falla", async () => {
    global.fetch = jest.fn().mockResolvedValue(respuesta(null, false, 500));
    await expect(getJSON("/demo/summary")).rejects.toThrow(/500/);
  });

  test("omite de la URL los parámetros vacíos", async () => {
    global.fetch = jest.fn().mockResolvedValue(respuesta({}));
    await getJSON("/demo/grupos", { search: "bio", ciudad: "", page: 2, tipo: undefined });
    const url = global.fetch.mock.calls[0][0];
    expect(url).toContain("search=bio");
    expect(url).toContain("page=2");
    expect(url).not.toContain("ciudad=");
    expect(url).not.toContain("tipo=");
  });
});

describe("getPaged", () => {
  test("normaliza la forma aunque el backend devuelva campos sueltos", async () => {
    global.fetch = jest.fn().mockResolvedValue(respuesta({ items: [{ a: 1 }] }));
    await expect(getPaged("/demo/grupos")).resolves.toEqual({
      items: [{ a: 1 }], total: 0, page: 1, pages: 1,
    });
  });

  test("nunca devuelve items undefined", async () => {
    global.fetch = jest.fn().mockResolvedValue(respuesta({}));
    const d = await getPaged("/demo/grupos");
    expect(Array.isArray(d.items)).toBe(true);
  });
});
