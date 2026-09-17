import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import Dashboard from "./Dashboard";

// Respuestas mínimas pero realistas del backend, con la forma que devuelve main.py.
const SUMMARY = {
  total_publicaciones: 18464, total_grupos: 152, total_miembros: 2000,
  miembros_activos: 1500, avalados_si: 10058, avalados_no: 8406,
  por_tipo: [{ name: "Artículos publicados", value: 11676 }],
  por_clasificacion: [{ name: "A1", value: 900 }],
  por_ciudad: [{ name: "BOYACÁ - TUNJA", value: 14413 }],
  por_area: [{ name: "Educación", value: 500 }],
  por_programa: [{ name: "Ciencias Básicas", value: 2734 }],
  por_anio: [{ anio: 2019, value: 839 }, { anio: 2020, value: 1051 }],
  anio_min: 2019, anio_max: 2020, publicaciones_con_anio: 17760,
  top_grupos_publicaciones: [{ name: "GRIDSE", value: 300 }],
  top_grupos_miembros: [{ name: "GRIDSE", value: 40 }],
};

const FILTROS = {
  ciudades: ["BOYACÁ - TUNJA"], clasificaciones: ["A1"], tipos: ["Artículos publicados"],
  programas: ["Ciencias Básicas"], grupos: ["GRIDSE"], anios: [2019, 2020],
};

const GRUPO = {
  grupo: "GRIDSE", ciudad: "BOYACÁ - TUNJA", lider: "Ana Ruiz", clasificacion: "A1",
  programa: "Ciencias Básicas", anio_formacion: 1992, ultimo_anio: 2020,
  web: "", email: "gridse@uptc.edu.co", lineas: ["AUTOMATIZACIÓN Y CONTROL"],
  n_publicaciones: 300, n_miembros: 40, avalados_si: 200, avalados_no: 100,
  por_tipo: [{ name: "Artículos publicados", value: 250 }],
  top_areas: [{ name: "Ingeniería", value: 120 }],
  por_anio: [{ anio: 2020, value: 30 }],
  publicaciones: [{ tipo: "Artículos publicados", avalado: "SI", anio: 2020, publicacion: "Un título" }],
  miembros: [{ integrante: "Ana Ruiz", estado: "Activo" }],
};

const RUTAS = {
  "/demo/summary": SUMMARY,
  "/demo/filtros": FILTROS,
  "/demo/grupo": GRUPO,
  "/demo/grupos": { items: [{ grupo: "GRIDSE", ciudad: "BOYACÁ - TUNJA", lider: "Ana Ruiz", clasificacion: "A1", anio_formacion: 1992, n_publicaciones: 300, n_miembros: 40, ultimo_anio: 2020 }], total: 1, page: 1, pages: 1 },
  "/demo/publicaciones": { items: [{ grupo: "GRIDSE", tipo: "Artículos publicados", avalado: "SI", anio: 2020, publicacion: "Un título" }], total: 1, page: 1, pages: 1 },
  "/demo/miembros": { items: [{ grupo: "GRIDSE", integrante: "Ana Ruiz", estado: "Activo" }], total: 1, page: 1, pages: 1 },
  "/demo/ciudades": { items: [{ ciudad: "BOYACÁ - TUNJA", grupos: 100, publicaciones: 14413, miembros: 900, lat: 5.53, lon: -73.36 }] },
  "/demo/revistas": { items: [{ name: "HELIYON", value: 40 }], con_revista: 9000, total_publicaciones: 18464 },
  "/demo/nube": { items: [{ text: "energia", value: 300 }] },
};

// Las rutas comparten prefijo ("/demo/grupo" y "/demo/grupos"), así que se
// prueba primero la más larga; si no, la lista de grupos recibiría una ficha.
const resolver = (url) =>
  Object.keys(RUTAS)
    .sort((a, b) => b.length - a.length)
    .find((r) => String(url).includes(`${r}?`) || String(url).endsWith(r));

const responder = (url) => {
  // La ficha se devuelve a nombre del grupo solicitado, para poder comparar
  // dos grupos distintos y distinguirlos en la tabla.
  const pedido = String(url).match(/\/demo\/grupo\?nombre=([^&]+)/);
  if (pedido) {
    const nombre = decodeURIComponent(pedido[1]);
    return Promise.resolve({
      ok: true, status: 200,
      json: async () => ({ ...GRUPO, grupo: nombre }),
    });
  }
  return Promise.resolve({ ok: true, status: 200, json: async () => RUTAS[resolver(url)] ?? {} });
};

beforeEach(() => {
  global.fetch = jest.fn(responder);
});

afterEach(() => {
  delete global.fetch;
});

const pintar = (props = {}) =>
  render(<Dashboard view="resumen" onSelectView={() => {}} onSelectGroup={() => {}} {...props} />);

test("el resumen muestra los indicadores y la serie por año", async () => {
  pintar();
  expect(await screen.findByText("18.464")).toBeInTheDocument();
  expect(screen.getByText(/Publicaciones por año/)).toBeInTheDocument();
  expect(screen.getByText(/Por programa nacional/)).toBeInTheDocument();
});

test("cada sección se pinta sin romperse", async () => {
  const vistas = [
    ["total", /Grupos \(/],
    ["unico", /Grupo único/],
    ["mapa", /Mapa de revistas/],
    ["nube", /Nube de palabras/],
    ["comparar", /Comparador de grupos/],
    ["publicaciones", /Publicaciones \(/],
    ["miembros", /Miembros \(/],
  ];
  for (const [view, titulo] of vistas) {
    const { unmount } = pintar({ view });
    expect(await screen.findByText(titulo)).toBeInTheDocument();
    unmount();
  }
});

test("un fallo al cargar muestra el aviso en vez de una pantalla vacía", async () => {
  global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  pintar();
  expect(await screen.findByText(/No se pudieron cargar los datos/)).toBeInTheDocument();
  expect(screen.getByText("Reintentar")).toBeInTheDocument();
});

test("la ficha de grupo muestra líneas, contacto y evolución", async () => {
  pintar({ view: "unico", selectedGroup: "GRIDSE" });
  expect(await screen.findByText("AUTOMATIZACIÓN Y CONTROL")).toBeInTheDocument();
  expect(screen.getByText("gridse@uptc.edu.co")).toBeInTheDocument();
  expect(screen.getByText(/Evolución anual del grupo/)).toBeInTheDocument();
  expect(screen.getByText(/Formado en 1992/)).toBeInTheDocument();
});

test("un grupo inexistente explica el error y ofrece sugerencias", async () => {
  global.fetch = jest.fn((url) => {
    if (String(url).includes("/demo/grupo?")) {
      return Promise.resolve({
        ok: true, status: 200,
        json: async () => ({ error: "Grupo no encontrado: XYZ", sugerencias: ["GRIDSE"] }),
      });
    }
    return responder(url);
  });
  pintar({ view: "unico", selectedGroup: "XYZ" });
  expect(await screen.findByText(/Grupo no encontrado/)).toBeInTheDocument();
  expect(screen.getByText(/GRIDSE/)).toBeInTheDocument();
});

test("la tabla de grupos ordena al pulsar un encabezado", async () => {
  pintar({ view: "total" });
  await screen.findByText("Ana Ruiz");
  fireEvent.click(screen.getByRole("button", { name: /Miemb/ }));
  await waitFor(() => {
    const urls = global.fetch.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("sort=n_miembros"))).toBe(true);
  });
});

test("al filtrar por año se advierte que quedan fuera las publicaciones sin año", async () => {
  pintar({ view: "publicaciones" });
  await screen.findByText("Un título");
  fireEvent.change(screen.getByTitle("Año desde"), { target: { value: "2020" } });
  expect(await screen.findByText(/no se pudo identificar/)).toBeInTheDocument();
});

describe("comparador", () => {
  const elegirDos = async () => {
    const campos = screen.getAllByPlaceholderText(/^Grupo /);
    fireEvent.change(campos[0], { target: { value: "GRIDSE" } });
    fireEvent.change(campos[1], { target: { value: "OTRO" } });
    fireEvent.click(screen.getByRole("button", { name: "Comparar" }));
    await screen.findByText("Indicador");
  };

  test("cada campo con contenido ofrece su propio botón de quitar", async () => {
    pintar({ view: "comparar" });
    await screen.findByText(/Comparador de grupos/);
    expect(screen.queryAllByRole("button", { name: /Quitar el grupo/ })).toHaveLength(0);

    fireEvent.change(screen.getAllByPlaceholderText(/^Grupo /)[0], { target: { value: "GRIDSE" } });
    expect(screen.getAllByRole("button", { name: /Quitar el grupo A/ })).toHaveLength(1);
  });

  test("quitar un campo deja intactos los demás", async () => {
    pintar({ view: "comparar" });
    await screen.findByText(/Comparador de grupos/);
    const campos = screen.getAllByPlaceholderText(/^Grupo /);
    fireEvent.change(campos[0], { target: { value: "PRIMERO" } });
    fireEvent.change(campos[1], { target: { value: "SEGUNDO" } });

    fireEvent.click(screen.getByRole("button", { name: /Quitar el grupo A/ }));

    // El hueco se compacta: SEGUNDO sube al primer campo y el resto queda libre.
    const despues = screen.getAllByPlaceholderText(/^Grupo /);
    expect(despues[0]).toHaveValue("SEGUNDO");
    expect(despues[1]).toHaveValue("");
    expect(despues[2]).toHaveValue("");
  });

  test("quitar una columna del resultado conserva la otra", async () => {
    pintar({ view: "comparar" });
    await screen.findByText(/Comparador de grupos/);
    await elegirDos();
    expect(screen.getAllByRole("columnheader")).toHaveLength(3); // Indicador + 2 grupos

    fireEvent.click(screen.getByRole("button", { name: /Quitar GRIDSE de la comparación/ }));

    await waitFor(() => expect(screen.getAllByRole("columnheader")).toHaveLength(2));
    expect(screen.getByText(/Queda un solo grupo/)).toBeInTheDocument();
    // El grupo que sigue en pie no se tocó.
    expect(screen.getAllByPlaceholderText(/^Grupo /)[0]).toHaveValue("OTRO");
  });

  test("con una sola columna no se destaca ningún valor como mejor", async () => {
    const { container } = pintar({ view: "comparar" });
    await screen.findByText(/Comparador de grupos/);
    await elegirDos();
    expect(container.querySelectorAll(".dash-comp-best").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Quitar GRIDSE de la comparación/ }));
    await waitFor(() => expect(container.querySelectorAll(".dash-comp-best")).toHaveLength(0));
  });

  test("Limpiar sigue vaciando todo de una vez", async () => {
    pintar({ view: "comparar" });
    await screen.findByText(/Comparador de grupos/);
    await elegirDos();

    fireEvent.click(screen.getByRole("button", { name: "Limpiar" }));

    await waitFor(() => expect(screen.queryByText("Indicador")).not.toBeInTheDocument());
    screen.getAllByPlaceholderText(/^Grupo /).forEach((c) => expect(c).toHaveValue(""));
  });
});

test("el mapa deja alternar la métrica del tamaño de los puntos", async () => {
  const { container } = pintar({ view: "mapa" });
  await screen.findByText("HELIYON");
  expect(container.querySelectorAll("circle").length).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Miembros" }));
  expect(container.querySelector("circle")).toBeInTheDocument();
});
