// Mapa único de vistas del tablero. El Sidebar las pinta y MainView
// pasa la vista activa al dashboard, que decide qué sección renderiza.
// Antes existía además una fila de pestañas dentro del dashboard con
// casi las mismas entradas; se eliminó para no tener dos menús que compiten.
export const VIEWS = [
  { id: "resumen", label: "Resumen general" },
  { id: "total", label: "Total Grupos" },
  { id: "unico", label: "Grupo Unico" },
  { id: "mapa", label: "Mapa Revistas" },
  { id: "nube", label: "Nube de palabras" },
  { id: "comparar", label: "Comparador" },
  { id: "publicaciones", label: "Publicaciones" },
  { id: "miembros", label: "Miembros" },
];

export const viewById = (id) => VIEWS.find((v) => v.id === id) || VIEWS[0];
