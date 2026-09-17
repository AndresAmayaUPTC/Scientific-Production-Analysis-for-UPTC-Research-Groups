import { render, screen, fireEvent } from "@testing-library/react";
import { BarList, Donut, SerieAnual, WordCloud, MapaCiudades, Th, Pager } from "./charts";

describe("BarList", () => {
  test("muestra un aviso en vez de romperse cuando no hay datos", () => {
    render(<BarList items={[]} />);
    expect(screen.getByText("Sin datos")).toBeInTheDocument();
    render(<BarList items={undefined} />);
  });

  test("pinta cada elemento con su valor formateado", () => {
    render(<BarList items={[{ name: "Artículos", value: 11676 }]} />);
    expect(screen.getByText("Artículos")).toBeInTheDocument();
    expect(screen.getByText("11.676")).toBeInTheDocument();
  });
});

describe("Donut", () => {
  test("calcula el porcentaje", () => {
    render(<Donut si={75} no={25} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  test("no divide por cero cuando todo está en cero", () => {
    render(<Donut si={0} no={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});

describe("SerieAnual", () => {
  test("avisa cuando ninguna publicación tiene año", () => {
    render(<SerieAnual items={[]} />);
    expect(screen.getByText(/Sin datos con año/)).toBeInTheDocument();
  });

  test("rellena con cero los años sin publicaciones", () => {
    // 2018 y 2020 con datos: el hueco de 2019 debe existir como barra vacía.
    const { container } = render(
      <SerieAnual items={[{ anio: 2018, value: 5 }, { anio: 2020, value: 7 }]} />
    );
    const barras = container.querySelectorAll("rect");
    expect(barras).toHaveLength(3);
    const titulos = [...barras].map((r) => r.querySelector("title").textContent);
    expect(titulos).toEqual([
      "2018: 5 publicaciones",
      "2019: 0 publicaciones",
      "2020: 7 publicaciones",
    ]);
  });

  test("las etiquetas de años no se superponen al final del eje", () => {
    // Caso real: 1959–2026 marcaba 2025 (múltiplo del paso) y 2026 (último),
    // y los dos textos quedaban uno encima del otro.
    const items = [];
    for (let a = 1959; a <= 2026; a++) items.push({ anio: a, value: a - 1950 });
    const { container } = render(<SerieAnual items={items} />);

    const etiquetas = [...container.querySelectorAll("svg > text")]
      .filter((t) => /^\d{4}$/.test(t.textContent));
    const xs = etiquetas.map((t) => Number(t.getAttribute("x")));

    expect(etiquetas[etiquetas.length - 1].textContent).toBe("2026");
    expect(etiquetas.map((t) => t.textContent)).not.toContain("2025");
    for (let i = 1; i < xs.length; i++) {
      expect(xs[i] - xs[i - 1]).toBeGreaterThanOrEqual(34);
    }
  });

  test("con pocos años se etiquetan todos", () => {
    const items = [2020, 2021, 2022, 2023].map((anio) => ({ anio, value: 1 }));
    const { container } = render(<SerieAnual items={items} />);
    const textos = [...container.querySelectorAll("svg > text")].map((t) => t.textContent);
    expect(textos).toEqual(expect.arrayContaining(["2020", "2021", "2022", "2023"]));
  });

  test("permite filtrar al hacer clic en un año", () => {
    const onPick = jest.fn();
    const { container } = render(
      <SerieAnual items={[{ anio: 2021, value: 3 }]} onPickAnio={onPick} />
    );
    fireEvent.click(container.querySelector("rect"));
    expect(onPick).toHaveBeenCalledWith(2021);
  });
});

describe("WordCloud", () => {
  test("no revienta cuando todas las palabras tienen la misma frecuencia", () => {
    render(<WordCloud items={[{ text: "agua", value: 4 }, { text: "suelo", value: 4 }]} />);
    expect(screen.getByText("agua")).toBeInTheDocument();
  });

  test("avisa al pulsar una palabra", () => {
    const onPick = jest.fn();
    render(<WordCloud items={[{ text: "energia", value: 9 }]} onPick={onPick} />);
    fireEvent.click(screen.getByText("energia"));
    expect(onPick).toHaveBeenCalledWith("energia");
  });
});

describe("MapaCiudades", () => {
  const ciudades = [
    { ciudad: "BOYACÁ - TUNJA", publicaciones: 14413, grupos: 100, miembros: 900, lat: 5.53, lon: -73.36 },
    { ciudad: "SIN UBICAR", publicaciones: 62, grupos: 1, miembros: 2, lat: null, lon: null },
  ];

  test("ignora las ciudades sin coordenadas", () => {
    const { container } = render(<MapaCiudades items={ciudades} />);
    expect(container.querySelectorAll("circle")).toHaveLength(1);
  });

  test("avisa cuando ninguna ciudad se puede ubicar", () => {
    render(<MapaCiudades items={[ciudades[1]]} />);
    expect(screen.getByText(/Sin ciudades ubicables/)).toBeInTheDocument();
  });

  test("alterna la selección al pulsar el mismo punto", () => {
    const onPick = jest.fn();
    const { container } = render(
      <MapaCiudades items={ciudades} seleccion="BOYACÁ - TUNJA" onPick={onPick} />
    );
    fireEvent.click(container.querySelector("circle"));
    expect(onPick).toHaveBeenCalledWith("");
  });
});

describe("Th", () => {
  const render1 = (orden, onOrden) =>
    render(<table><thead><tr><Th campo="anio" orden={orden} onOrden={onOrden}>Año</Th></tr></thead></table>);

  test("al pulsar una columna inactiva ordena descendente", () => {
    const onOrden = jest.fn();
    render1({ sort: "grupo", dir: "asc" }, onOrden);
    fireEvent.click(screen.getByRole("button"));
    expect(onOrden).toHaveBeenCalledWith("anio", "desc");
  });

  test("al volver a pulsar la columna activa invierte el sentido", () => {
    const onOrden = jest.fn();
    render1({ sort: "anio", dir: "desc" }, onOrden);
    fireEvent.click(screen.getByRole("button"));
    expect(onOrden).toHaveBeenCalledWith("anio", "asc");
  });

  test("expone el sentido a los lectores de pantalla", () => {
    render1({ sort: "anio", dir: "asc" }, jest.fn());
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
  });
});

describe("Pager", () => {
  test("desactiva los extremos", () => {
    render(<Pager page={1} pages={1} total={0} onPage={jest.fn()} />);
    expect(screen.getByText(/Anterior/)).toBeDisabled();
    expect(screen.getByText(/Siguiente/)).toBeDisabled();
  });

  test("se bloquea mientras carga", () => {
    render(<Pager page={2} pages={5} total={70} onPage={jest.fn()} cargando />);
    expect(screen.getByText(/Siguiente/)).toBeDisabled();
  });
});
