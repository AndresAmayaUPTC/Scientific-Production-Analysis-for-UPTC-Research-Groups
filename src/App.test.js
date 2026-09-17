import { render, screen } from "@testing-library/react";
import Sidebar from "./Components/Sidebar";
import { VIEWS, viewById } from "./Components/views";

test("el menú lateral ofrece todas las vistas del tablero", () => {
  render(<Sidebar activeView="resumen" onSelectView={() => {}} />);
  VIEWS.forEach((v) => {
    expect(screen.getByText(v.label)).toBeInTheDocument();
  });
});

test("la vista activa se marca para accesibilidad", () => {
  render(<Sidebar activeView="mapa" onSelectView={() => {}} />);
  expect(screen.getByText("Mapa Revistas")).toHaveAttribute("aria-current", "page");
});

test("viewById cae en la primera vista ante un id desconocido", () => {
  expect(viewById("no-existe").id).toBe(VIEWS[0].id);
  expect(viewById("mapa").id).toBe("mapa");
});
