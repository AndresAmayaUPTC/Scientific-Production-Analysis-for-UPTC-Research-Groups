// Comportamiento del botón "Volver a la aplicación" del centro de ayuda
// (public/help.html). Se carga el HTML real y se ejecuta su script en jsdom.
import fs from "fs";
import path from "path";

const html = fs.readFileSync(path.join(__dirname, "..", "public", "help.html"), "utf8");
const cuerpo = html.match(/<body[^>]*>([\s\S]*)<\/body>/i)[1];
const script = [...cuerpo.matchAll(/<script>([\s\S]*?)<\/script>/gi)].map((m) => m[1]).join("\n");

let asignado;

function cargarAyuda(url) {
  window.history.replaceState(null, "", url);
  document.body.innerHTML = cuerpo.replace(/<script>[\s\S]*?<\/script>/gi, "");
  // eslint-disable-next-line no-new-func
  new Function(script)();
}

beforeEach(() => {
  jest.useFakeTimers();
  window.close = jest.fn();
  window.history.back = jest.fn();
  Element.prototype.scrollIntoView = jest.fn();
  asignado = undefined;
  // jsdom no navega: se intercepta la asignación a location.href.
  delete window.location;
  const real = new URL("http://localhost/");
  window.location = {
    get search() { return real.search; },
    get href() { return real.href; },
    set href(v) { asignado = v; },
  };
});

afterEach(() => {
  jest.useRealTimers();
});

// window.location está reemplazado, así que la URL de la prueba se fija aquí.
function abrir(query) {
  const real = new URL(`http://localhost/help.html${query}`);
  Object.defineProperty(window.location, "search", { get: () => real.search, configurable: true });
  cargarAyuda(`/help.html${query}`);
}

const boton = () => document.getElementById("back-btn");

test("abierta desde la app, Volver cierra la pestaña", () => {
  abrir("?origen=app");
  const evento = new MouseEvent("click", { bubbles: true, cancelable: true });
  boton().dispatchEvent(evento);

  expect(window.close).toHaveBeenCalledTimes(1);
  expect(evento.defaultPrevented).toBe(true);
  expect(window.history.back).not.toHaveBeenCalled();
});

test("si el navegador no deja cerrarla, lleva a la aplicación", () => {
  abrir("?origen=app");
  boton().click();
  expect(asignado).toBeUndefined();

  jest.advanceTimersByTime(300);
  expect(asignado).toBe("/mainview");
});

test("abierta en la misma pestaña, Volver retrocede y no intenta cerrar", () => {
  abrir("");
  Object.defineProperty(window.history, "length", { value: 3, configurable: true });
  boton().click();

  expect(window.close).not.toHaveBeenCalled();
  expect(window.history.back).toHaveBeenCalledTimes(1);
});

test("los enlaces del menú no añaden entradas al historial", () => {
  // Con una sola entrada de historial el navegador permite cerrar la pestaña.
  abrir("?origen=app");
  const push = jest.spyOn(window.history, "pushState");
  const replace = jest.spyOn(window.history, "replaceState");
  const enlace = document.querySelector('a[href="#FAQ"]');
  const evento = new MouseEvent("click", { bubbles: true, cancelable: true });

  enlace.dispatchEvent(evento);

  expect(evento.defaultPrevented).toBe(true);
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  expect(push).not.toHaveBeenCalled();
  expect(replace).toHaveBeenCalledWith(null, "", "#FAQ");
});
