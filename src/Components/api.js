// Acceso al backend. La URL sale del entorno para que la app funcione
// desplegada y no solo contra localhost (CRA expone REACT_APP_*).
export const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

/**
 * GET que devuelve JSON y convierte en excepción tanto los fallos de red
 * como los `{"error": ...}` que responde el backend cuando los datos no
 * cargaron. Sin esto, un error del servidor llegaba a la tabla como
 * `undefined` y rompía el render entero.
 */
export async function getJSON(path, params = {}) {
  const limpio = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
  );
  const qs = new URLSearchParams(limpio).toString();
  const url = `${API}${path}${qs ? `?${qs}` : ""}`;

  let res;
  try {
    res = await fetch(url);
  } catch (e) {
    throw new Error("No se pudo conectar con el servidor de datos. ¿Está encendido el backend?");
  }
  if (!res.ok) {
    throw new Error(`El servidor respondió ${res.status} al pedir ${path}`);
  }
  let data;
  try {
    data = await res.json();
  } catch (e) {
    throw new Error(`Respuesta ilegible del servidor en ${path}`);
  }
  if (data && data.error) {
    const err = new Error(data.error);
    err.sugerencias = data.sugerencias || [];
    throw err;
  }
  return data;
}

/** Igual que getJSON pero para listas paginadas: garantiza la forma esperada. */
export async function getPaged(path, params) {
  const d = await getJSON(path, params);
  return {
    items: Array.isArray(d.items) ? d.items : [],
    total: d.total || 0,
    page: d.page || 1,
    pages: d.pages || 1,
  };
}

export const VACIO = { items: [], total: 0, page: 1, pages: 1 };

/** Descarga un CSV respetando los filtros aplicados. */
export function downloadCSV(path, params = {}) {
  const limpio = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== "" && v !== null && v !== undefined)
  );
  const q = new URLSearchParams(limpio);
  const a = document.createElement("a");
  a.href = `${API}${path}?${q}`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export const nf = (n) => Number(n || 0).toLocaleString("es-CO");
