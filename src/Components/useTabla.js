import { useCallback, useEffect, useMemo, useState } from "react";
import { getPaged, VACIO } from "./api";

const RETARDO_MS = 350;
const TAM_PAGINA = 15;

/**
 * Estado de una tabla paginada del tablero.
 *
 * Distingue dos juegos de filtros:
 *  - `filtros`: lo que el usuario está escribiendo ahora mismo.
 *  - `aplicados`: los que produjeron los datos en pantalla.
 * Paginar usa SIEMPRE `aplicados`. Antes se usaban los del formulario, así
 * que escribir en el buscador y pulsar "Siguiente" devolvía la página 2 de
 * una búsqueda distinta a la que se estaba viendo.
 *
 * Los cambios de filtro se aplican solos tras una pausa breve, de modo que
 * cambiar un desplegable ya no exige pulsar un botón aparte.
 */
export function useTabla(path, filtrosIniciales, ordenInicial) {
  const [filtros, setFiltros] = useState(filtrosIniciales);
  const [aplicados, setAplicados] = useState(filtrosIniciales);
  const [orden, setOrdenEstado] = useState(ordenInicial);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(VACIO);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);
  const [activa, setActiva] = useState(false);

  const claveFiltros = JSON.stringify(filtros);

  useEffect(() => {
    const t = setTimeout(() => {
      setAplicados(JSON.parse(claveFiltros));
      setPage(1);
    }, RETARDO_MS);
    return () => clearTimeout(t);
  }, [claveFiltros]);

  const claveAplicados = JSON.stringify(aplicados);
  const claveOrden = JSON.stringify(orden);

  useEffect(() => {
    if (!activa) return undefined;
    let cancelado = false;
    setCargando(true);
    getPaged(path, { ...JSON.parse(claveAplicados), ...JSON.parse(claveOrden), page, page_size: TAM_PAGINA })
      .then((d) => {
        if (cancelado) return;
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (cancelado) return;
        setError(e.message || String(e));
        setData(VACIO);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [activa, path, claveAplicados, claveOrden, page]);

  const setFiltro = useCallback((clave, valor) => {
    setFiltros((f) => ({ ...f, [clave]: valor }));
  }, []);

  /** Reemplaza los filtros de golpe (p. ej. al llegar desde la nube de palabras). */
  const reemplazarFiltros = useCallback((nuevos) => {
    setFiltros((f) => ({ ...f, ...nuevos }));
  }, []);

  const setOrden = useCallback((sort, dir) => {
    setOrdenEstado({ sort, dir });
    setPage(1);
  }, []);

  const limpiar = useCallback(() => setFiltros(filtrosIniciales), [filtrosIniciales]);

  // Parámetros exactos con los que se pintó la tabla: el CSV debe exportar
  // justo eso, no lo que quedó a medio escribir en el formulario.
  const paramsExport = useMemo(
    () => ({ ...aplicados, ...orden }),
    [aplicados, orden]
  );

  const hayFiltros = useMemo(
    () => Object.entries(filtros).some(([k, v]) => v !== filtrosIniciales[k]),
    [filtros, filtrosIniciales]
  );

  return {
    data, cargando, error,
    filtros, setFiltro, reemplazarFiltros, limpiar, hayFiltros,
    orden, setOrden,
    page, irPagina: setPage,
    activar: setActiva,
    paramsExport,
  };
}
