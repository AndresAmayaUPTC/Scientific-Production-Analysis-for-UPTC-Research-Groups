import React, { useCallback, useEffect, useState } from "react";
import { getJSON, downloadCSV, nf } from "./api";
import { useTabla } from "./useTabla";
import { BarList, Donut, SerieAnual, WordCloud, MapaCiudades, Th, Pager, Skeleton } from "./charts";
import "./dashboard.css";

const F_GRUPOS = { search: "", ciudad: "", clasificacion: "", programa: "" };
const F_PUBS = { search: "", tipo: "", avalado: "", programa: "", anio_desde: "", anio_hasta: "" };
const F_MIEM = { search: "", estado: "" };

const Aviso = ({ children }) => (children ? <div className="dash-error">{children}</div> : null);

/** Encabezado común de las tablas: contador, filtros y exportación. */
const Barra = ({ children }) => <div className="dash-toolbar">{children}</div>;

const Dashboard = ({
  view = "resumen",
  onSelectView = () => {},
  selectedGroup = "",
  onSelectGroup = () => {},
}) => {
  const [summary, setSummary] = useState(null);
  const [filtros, setFiltros] = useState({
    ciudades: [], clasificaciones: [], tipos: [], programas: [], grupos: [], anios: [],
  });
  const [loadError, setLoadError] = useState(null);

  const grupos = useTabla("/demo/grupos", F_GRUPOS, { sort: "n_publicaciones", dir: "desc" });
  const pubs = useTabla("/demo/publicaciones", F_PUBS, { sort: "anio", dir: "desc" });
  const miem = useTabla("/demo/miembros", F_MIEM, { sort: "grupo", dir: "asc" });

  // Vistas con datos propios
  const [grupoDetail, setGrupoDetail] = useState(null);
  const [grupoLoading, setGrupoLoading] = useState(false);
  const [grupoError, setGrupoError] = useState(null);
  const [gPick, setGPick] = useState("");
  const [nube, setNube] = useState([]);
  const [nubeFuente, setNubeFuente] = useState("titulos");
  const [nubeCargando, setNubeCargando] = useState(false);
  const [ciudades, setCiudades] = useState(null);
  const [revistas, setRevistas] = useState(null);
  const [revistasMeta, setRevistasMeta] = useState({ con_revista: 0, total_publicaciones: 0 });
  const [mapaError, setMapaError] = useState(null);
  const [mapaMetrica, setMapaMetrica] = useState("publicaciones");
  const [ciudadSel, setCiudadSel] = useState("");

  // Comparador (hasta 3 grupos lado a lado)
  const [comp, setComp] = useState(["", "", ""]);
  const [compData, setCompData] = useState([]);
  const [compLoading, setCompLoading] = useState(false);
  const [compError, setCompError] = useState(null);

  useEffect(() => {
    let cancelado = false;
    Promise.all([getJSON("/demo/summary"), getJSON("/demo/filtros")])
      .then(([s, f]) => {
        if (cancelado) return;
        setSummary(s);
        setFiltros((prev) => ({ ...prev, ...f }));
        setLoadError(null);
      })
      .catch((e) => !cancelado && setLoadError(e.message || String(e)));
    return () => { cancelado = true; };
  }, []);

  // Carga perezosa: cada vista pide sus datos la primera vez que se abre.
  const { activar: activarGrupos } = grupos;
  const { activar: activarPubs } = pubs;
  const { activar: activarMiem } = miem;
  useEffect(() => {
    if (view === "total") activarGrupos(true);
    if (view === "publicaciones") activarPubs(true);
    if (view === "miembros") activarMiem(true);
  }, [view, activarGrupos, activarPubs, activarMiem]);

  useEffect(() => {
    if (view !== "mapa" || ciudades) return undefined;
    let cancelado = false;
    Promise.all([getJSON("/demo/ciudades"), getJSON("/demo/revistas", { limite: 20 })])
      .then(([c, r]) => {
        if (cancelado) return;
        setCiudades(c.items || []);
        setRevistas(r.items || []);
        setRevistasMeta({ con_revista: r.con_revista, total_publicaciones: r.total_publicaciones });
        setMapaError(null);
      })
      .catch((e) => !cancelado && setMapaError(e.message || String(e)));
    return () => { cancelado = true; };
  }, [view, ciudades]);

  useEffect(() => {
    if (view !== "nube") return undefined;
    let cancelado = false;
    setNubeCargando(true);
    getJSON("/demo/nube", { fuente: nubeFuente, limite: 90 })
      .then((d) => !cancelado && setNube(d.items || []))
      .catch(() => !cancelado && setNube([]))
      .finally(() => !cancelado && setNubeCargando(false));
    return () => { cancelado = true; };
  }, [view, nubeFuente]);

  useEffect(() => {
    if (view !== "unico" || !selectedGroup) return undefined;
    let cancelado = false;
    setGrupoLoading(true);
    setGrupoError(null);
    getJSON("/demo/grupo", { nombre: selectedGroup })
      .then((d) => !cancelado && setGrupoDetail(d))
      .catch((e) => {
        if (cancelado) return;
        const extra = e.sugerencias?.length ? ` ¿Quisiste decir: ${e.sugerencias.join(", ")}?` : "";
        setGrupoError((e.message || String(e)) + extra);
        setGrupoDetail(null);
      })
      .finally(() => !cancelado && setGrupoLoading(false));
    return () => { cancelado = true; };
  }, [view, selectedGroup]);

  const elegirGrupo = () => {
    const name = gPick.trim();
    if (!name) return;
    const exact = filtros.grupos.find((g) => g.toLowerCase() === name.toLowerCase());
    onSelectGroup(exact || name);
  };

  const { reemplazarFiltros: filtrarPubs } = pubs;
  const buscarPalabra = useCallback((w) => {
    filtrarPubs({ search: w });
    onSelectView("publicaciones");
  }, [filtrarPubs, onSelectView]);

  const filtrarPorAnio = useCallback((anio) => {
    filtrarPubs({ anio_desde: String(anio), anio_hasta: String(anio) });
    onSelectView("publicaciones");
  }, [filtrarPubs, onSelectView]);

  const setCompSlot = (i, v) => setComp((c) => c.map((x, j) => (j === i ? v : x)));
  const llenarPrimerHueco = (name) => {
    const i = comp.findIndex((c) => !c.trim());
    setCompSlot(i === -1 ? 2 : i, name);
  };

  /**
   * Saca un solo grupo de la comparación y deja los demás intactos.
   * Los huecos se compactan al final para que los campos vacíos queden
   * siempre a la derecha, listos para escribir otro nombre.
   */
  const quitarSlot = (i) => {
    const fuera = comp[i].trim().toLowerCase();
    setComp((c) => {
      const restantes = c.filter((_, j) => j !== i);
      return [...restantes, ""].slice(0, 3);
    });
    if (fuera) {
      setCompData((d) => d.filter((x) => x.grupo.toLowerCase() !== fuera));
    }
    setCompError(null);
  };

  const quitarGrupo = (nombre) => {
    const i = comp.findIndex((c) => c.trim().toLowerCase() === nombre.toLowerCase());
    if (i === -1) {
      setCompData((d) => d.filter((x) => x.grupo !== nombre));
      return;
    }
    quitarSlot(i);
  };

  const comparar = async () => {
    const names = comp.map((s) => s.trim()).filter(Boolean);
    const uniq = [...new Set(names.map((n) => n.toLowerCase()))]
      .map((l) => names.find((n) => n.toLowerCase() === l))
      .slice(0, 3);
    if (uniq.length < 2) {
      setCompError("Elige al menos 2 grupos distintos para comparar.");
      setCompData([]);
      return;
    }
    const resolved = uniq.map((n) => filtros.grupos.find((g) => g.toLowerCase() === n.toLowerCase()) || n);
    setCompLoading(true);
    setCompError(null);
    try {
      const ds = await Promise.all(resolved.map((n) => getJSON("/demo/grupo", { nombre: n })));
      setCompData(ds);
    } catch (e) {
      const extra = e.sugerencias?.length ? ` ¿Quisiste decir: ${e.sugerencias.join(", ")}?` : "";
      setCompError((e.message || String(e)) + extra);
      setCompData([]);
    } finally {
      setCompLoading(false);
    }
  };

  const limpiarComparador = () => {
    setComp(["", "", ""]);
    setCompData([]);
    setCompError(null);
  };

  const pctAval = (d) => (d.avalados_si + d.avalados_no ? Math.round((100 * d.avalados_si) / (d.avalados_si + d.avalados_no)) : 0);
  // Con una sola columna no hay nada que destacar: resaltarla sería engañoso.
  const bestIdx = (vals) => (vals.length < 2 ? -1 : vals.indexOf(Math.max(...vals)));

  if (loadError) {
    return (
      <div className="dash">
        <Aviso>No se pudieron cargar los datos: {loadError}</Aviso>
        <button className="dash-btn-dark" onClick={() => window.location.reload()}>Reintentar</button>
      </div>
    );
  }
  if (!summary) {
    return <div className="dash"><Skeleton filas={6} /></div>;
  }

  const kpis = [
    { label: "Publicaciones", value: summary.total_publicaciones },
    { label: "Grupos", value: summary.total_grupos },
    { label: "Miembros", value: summary.total_miembros },
    { label: "Miembros activos", value: summary.miembros_activos },
    { label: "Avalados SÍ", value: summary.avalados_si },
    { label: "Avalados NO", value: summary.avalados_no },
  ];

  const listaGrupos = (
    <datalist id="dash-grupos-list">
      {filtros.grupos.map((g) => <option key={g} value={g} />)}
    </datalist>
  );

  return (
    <div className="dash">
      {view === "resumen" && (
        <>
          <div className="dash-kpis">
            {kpis.map((k) => (
              <div className="dash-kpi" key={k.label}>
                <div className="dash-kpi-value">{nf(k.value)}</div>
                <div className="dash-kpi-label">{k.label}</div>
              </div>
            ))}
          </div>

          <div className="dash-card" style={{ marginBottom: "1.2em" }}>
            <h4>Publicaciones por año ({summary.anio_min}–{summary.anio_max})</h4>
            <SerieAnual items={summary.por_anio} onPickAnio={filtrarPorAnio} />
            <p className="dash-muted" style={{ margin: "0.6em 0 0" }}>
              El año se extrae del texto del registro; se identificó en {nf(summary.publicaciones_con_anio)} de{" "}
              {nf(summary.total_publicaciones)} publicaciones ({Math.round((100 * summary.publicaciones_con_anio) / summary.total_publicaciones)}%).
            </p>
          </div>

          <div className="dash-grid">
            <div><h4>Por tipo de publicación</h4><BarList items={summary.por_tipo} color="#1f6feb" /></div>
            <div><h4>Productos avalados</h4><Donut si={summary.avalados_si} no={summary.avalados_no} labelSi="Avalados SÍ" labelNo="Avalados NO" /></div>
            <div><h4>Por programa nacional de CTeI</h4><BarList items={summary.por_programa} color="#0d9488" /></div>
            <div><h4>Por clasificación</h4><BarList items={summary.por_clasificacion} color="#7c3aed" /></div>
            <div><h4>Por ciudad</h4><BarList items={summary.por_ciudad} color="#059669" /></div>
            <div><h4>Top áreas de conocimiento</h4><BarList items={summary.por_area?.slice(0, 8)} color="#0284c7" /></div>
            <div><h4>Top grupos por publicaciones</h4><BarList items={summary.top_grupos_publicaciones} color="#d97706" /></div>
            <div><h4>Top grupos por miembros</h4><BarList items={summary.top_grupos_miembros} color="#be123c" /></div>
          </div>
        </>
      )}

      {view === "total" && (
        <div>
          <h3>Grupos ({nf(grupos.data.total)})</h3>
          <Barra>
            <input
              className="dash-field dash-field-grow"
              placeholder="Buscar grupo o líder..."
              value={grupos.filtros.search}
              onChange={(e) => grupos.setFiltro("search", e.target.value)}
            />
            <select className="dash-field" value={grupos.filtros.ciudad} onChange={(e) => grupos.setFiltro("ciudad", e.target.value)}>
              <option value="">Todas las ciudades</option>
              {filtros.ciudades.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select className="dash-field" value={grupos.filtros.clasificacion} onChange={(e) => grupos.setFiltro("clasificacion", e.target.value)}>
              <option value="">Todas las clasificaciones</option>
              {filtros.clasificaciones.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select className="dash-field" value={grupos.filtros.programa} onChange={(e) => grupos.setFiltro("programa", e.target.value)}>
              <option value="">Todos los programas</option>
              {filtros.programas.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            {grupos.hayFiltros && <button className="dash-btn" onClick={grupos.limpiar}>Limpiar</button>}
            <button className="dash-btn" onClick={() => downloadCSV("/demo/grupos.csv", grupos.paramsExport)} title="Descarga todos los grupos filtrados (sin paginar)">
              Exportar CSV
            </button>
            {grupos.cargando && <span className="dash-muted">Actualizando…</span>}
          </Barra>

          <Aviso>{grupos.error}</Aviso>
          {grupos.cargando && grupos.data.items.length === 0 ? <Skeleton /> : (
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <Th campo="grupo" orden={grupos.orden} onOrden={grupos.setOrden}>Grupo</Th>
                    <Th campo="ciudad" orden={grupos.orden} onOrden={grupos.setOrden}>Ciudad</Th>
                    <Th campo="lider" orden={grupos.orden} onOrden={grupos.setOrden}>Líder</Th>
                    <Th campo="clasificacion" orden={grupos.orden} onOrden={grupos.setOrden}>Clas.</Th>
                    <Th campo="anio_formacion" orden={grupos.orden} onOrden={grupos.setOrden} num>Desde</Th>
                    <Th campo="n_publicaciones" orden={grupos.orden} onOrden={grupos.setOrden} num>Pub.</Th>
                    <Th campo="n_miembros" orden={grupos.orden} onOrden={grupos.setOrden} num>Miemb.</Th>
                    <Th campo="ultimo_anio" orden={grupos.orden} onOrden={grupos.setOrden} num>Última</Th>
                  </tr>
                </thead>
                <tbody>
                  {grupos.data.items.length === 0 && !grupos.cargando && (
                    <tr><td colSpan={8} className="dash-muted">Ningún grupo coincide con los filtros.</td></tr>
                  )}
                  {grupos.data.items.map((g, i) => (
                    <tr key={`${g.grupo}-${i}`}>
                      <td>
                        <button className="dash-link" title="Ver ficha del grupo"
                          onClick={() => { onSelectGroup(g.grupo); setGPick(g.grupo); onSelectView("unico"); }}>
                          {g.grupo}
                        </button>
                      </td>
                      <td>{g.ciudad}</td>
                      <td>{g.lider}</td>
                      <td>{g.clasificacion}</td>
                      <td className="num">{g.anio_formacion || "—"}</td>
                      <td className="num">{nf(g.n_publicaciones)}</td>
                      <td className="num">{nf(g.n_miembros)}</td>
                      <td className="num">{g.ultimo_anio || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={grupos.data.page} pages={grupos.data.pages} total={grupos.data.total} onPage={grupos.irPagina} cargando={grupos.cargando} />
        </div>
      )}

      {view === "unico" && (
        <div>
          <h3>Grupo único</h3>
          <Barra>
            <input
              className="dash-field dash-field-grow"
              list="dash-grupos-list"
              placeholder="Escribe para buscar un grupo…"
              value={gPick}
              onChange={(e) => setGPick(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") elegirGrupo(); }}
            />
            {listaGrupos}
            <button className="dash-btn-dark" onClick={elegirGrupo}>Ver ficha</button>
            {selectedGroup && <span className="dash-chip">Viendo: <strong>{selectedGroup}</strong></span>}
          </Barra>

          {!selectedGroup && (
            <div className="dash-state">
              <p style={{ marginTop: 0 }}>Elige un grupo para ver su ficha: productos, miembros, avalados, líneas y evolución anual.</p>
              <p className="dash-muted" style={{ marginBottom: "0.5em" }}>Accesos rápidos:</p>
              <div className="dash-toolbar" style={{ marginBottom: 0 }}>
                {(summary.top_grupos_publicaciones || []).slice(0, 5).map((g) => (
                  <button key={g.name} className="dash-btn" onClick={() => { setGPick(g.name); onSelectGroup(g.name); }}>{g.name}</button>
                ))}
              </div>
            </div>
          )}

          {selectedGroup && grupoLoading && <Skeleton filas={6} />}
          <Aviso>{grupoError}</Aviso>

          {selectedGroup && grupoDetail && !grupoLoading && (
            <>
              <div style={{ display: "flex", gap: "0.6em", alignItems: "baseline", flexWrap: "wrap" }}>
                <h2 style={{ margin: "0.2em 0" }}>{grupoDetail.grupo}</h2>
                <span className="dash-tag-clas">{grupoDetail.clasificacion}</span>
              </div>
              <p className="dash-muted" style={{ marginTop: "0.2em" }}>
                {grupoDetail.ciudad || "Ciudad sin registrar"} · Líder: {grupoDetail.lider || "—"}
                {grupoDetail.anio_formacion ? ` · Formado en ${grupoDetail.anio_formacion}` : ""}
                {grupoDetail.email ? <> · <a href={`mailto:${grupoDetail.email}`}>{grupoDetail.email}</a></> : null}
                {grupoDetail.web ? <> · <a href={grupoDetail.web} target="_blank" rel="noreferrer">Sitio web</a></> : null}
              </p>
              {grupoDetail.programa && <p className="dash-muted" style={{ marginTop: 0 }}>Programa nacional: {grupoDetail.programa}</p>}

              <div className="dash-kpis">
                {[
                  { label: "Publicaciones", value: grupoDetail.n_publicaciones },
                  { label: "Miembros", value: grupoDetail.n_miembros },
                  { label: "Avalados SÍ", value: grupoDetail.avalados_si },
                  { label: "Avalados NO", value: grupoDetail.avalados_no },
                  { label: "Última publicación", value: grupoDetail.ultimo_anio || "—", crudo: true },
                ].map((k) => (
                  <div className="dash-kpi" key={k.label}>
                    <div className="dash-kpi-value">{k.crudo ? k.value : nf(k.value)}</div>
                    <div className="dash-kpi-label">{k.label}</div>
                  </div>
                ))}
              </div>

              <div className="dash-card" style={{ marginBottom: "1.2em" }}>
                <h4>Evolución anual del grupo</h4>
                <SerieAnual items={grupoDetail.por_anio} color="#7c3aed" height={160} />
              </div>

              <div className="dash-grid">
                <div><h4>Productos avalados</h4><Donut si={grupoDetail.avalados_si} no={grupoDetail.avalados_no} labelSi="Avalados SÍ" labelNo="Avalados NO" /></div>
                <div><h4>Por tipo de publicación</h4><BarList items={grupoDetail.por_tipo} color="#1f6feb" /></div>
                <div><h4>Top áreas del grupo</h4><BarList items={grupoDetail.top_areas} color="#0284c7" /></div>
              </div>

              {grupoDetail.lineas?.length > 0 && (
                <>
                  <h4>Líneas de investigación ({grupoDetail.lineas.length})</h4>
                  <div className="dash-tags" style={{ marginBottom: "1.2em" }}>
                    {grupoDetail.lineas.map((l) => <span className="dash-tag" key={l}>{l}</span>)}
                  </div>
                </>
              )}

              <h4>Publicaciones más recientes ({nf(grupoDetail.n_publicaciones)} en total)</h4>
              <ul className="dash-pub-list">
                {grupoDetail.publicaciones.map((p, i) => (
                  <li key={i}>
                    <div className="dash-tags" style={{ marginBottom: "0.3em" }}>
                      <span className="dash-tag">{p.tipo || "—"}</span>
                      <span className={`dash-tag${p.avalado === "SI" ? " dash-tag-ok" : ""}`}>Avalado: {p.avalado || "—"}</span>
                      <span className="dash-tag">{p.anio || "año no identificado"}</span>
                    </div>
                    {p.publicacion}
                  </li>
                ))}
              </ul>

              <h4>Miembros ({nf(grupoDetail.n_miembros)})</h4>
              <div className="dash-scroll-box">
                <table className="dash-table" style={{ minWidth: 0 }}>
                  <thead><tr><th>Integrante</th><th>Estado</th></tr></thead>
                  <tbody>
                    {grupoDetail.miembros.map((m, i) => (
                      <tr key={i}><td>{m.integrante}</td><td>{m.estado}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {view === "mapa" && (
        <div>
          <h3>Mapa de revistas y presencia territorial</h3>
          <Aviso>{mapaError}</Aviso>
          <p className="dash-muted" style={{ marginTop: 0 }}>
            {nf(revistasMeta.con_revista)} de {nf(revistasMeta.total_publicaciones)} publicaciones identifican su revista o fuente (ISSN).
          </p>

          {!ciudades && !mapaError && <Skeleton filas={6} />}

          {ciudades && (
            <div className="dash-grid" style={{ gridTemplateColumns: "minmax(280px, 420px) 1fr" }}>
              <div className="dash-card">
                <Barra>
                  <span className="dash-muted">Tamaño del punto:</span>
                  {[["publicaciones", "Publicaciones"], ["grupos", "Grupos"], ["miembros", "Miembros"]].map(([k, l]) => (
                    <button key={k} className={mapaMetrica === k ? "dash-btn-dark" : "dash-btn"} onClick={() => setMapaMetrica(k)}>{l}</button>
                  ))}
                </Barra>
                <MapaCiudades items={ciudades} metrica={mapaMetrica} seleccion={ciudadSel} onPick={setCiudadSel} />
                {ciudadSel && (
                  <p className="dash-muted" style={{ marginBottom: 0 }}>
                    <strong>{ciudadSel}</strong> — clic de nuevo en el punto para quitar la selección.
                  </p>
                )}
              </div>
              <div>
                <h4>Top revistas y fuentes</h4>
                <BarList items={revistas} color="#7c3aed" />
              </div>
            </div>
          )}

          <Barra>
            <h4 style={{ margin: 0 }}>Detalle por ciudad</h4>
            <button className="dash-btn" onClick={() => downloadCSV("/demo/ciudades.csv")}>Exportar CSV</button>
          </Barra>
          <div className="dash-table-wrap">
            <table className="dash-table">
              <thead><tr><th>Ciudad</th><th className="num">Grupos</th><th className="num">Publicaciones</th><th className="num">Miembros</th></tr></thead>
              <tbody>
                {(ciudades || []).map((c, i) => (
                  <tr key={i} style={ciudadSel === c.ciudad ? { background: "#fff8e1" } : undefined}>
                    <td>{c.ciudad}</td>
                    <td className="num">{nf(c.grupos)}</td>
                    <td className="num">{nf(c.publicaciones)}</td>
                    <td className="num">{nf(c.miembros)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {view === "nube" && (
        <div>
          <h3>Nube de palabras</h3>
          <Barra>
            <span className="dash-muted">Fuente:</span>
            <button className={nubeFuente === "titulos" ? "dash-btn-dark" : "dash-btn"} onClick={() => setNubeFuente("titulos")}>Títulos de productos</button>
            <button className={nubeFuente === "areas" ? "dash-btn-dark" : "dash-btn"} onClick={() => setNubeFuente("areas")}>Áreas de conocimiento</button>
            <span className="dash-muted">Clic en una palabra para buscar publicaciones que la contengan.</span>
          </Barra>
          {nubeCargando ? <Skeleton filas={4} /> : <WordCloud items={nube} onPick={buscarPalabra} />}
        </div>
      )}

      {view === "comparar" && (
        <div>
          <h3>Comparador de grupos (hasta 3)</h3>
          <Barra>
            {["A", "B", "C (opcional)"].map((tag, i) => (
              <div className="dash-slot" key={tag}>
                <input
                  className="dash-field"
                  list="dash-grupos-list"
                  placeholder={`Grupo ${tag}…`}
                  value={comp[i]}
                  onChange={(e) => setCompSlot(i, e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") comparar(); }}
                />
                {comp[i] && (
                  <button
                    className="dash-slot-x"
                    onClick={() => quitarSlot(i)}
                    title={`Quitar el grupo ${tag}`}
                    aria-label={`Quitar el grupo ${tag} de la comparación`}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
            {listaGrupos}
            <button className="dash-btn-dark" onClick={comparar} disabled={compLoading}>Comparar</button>
            {(compData.length > 0 || comp.some(Boolean)) && <button className="dash-btn" onClick={limpiarComparador}>Limpiar</button>}
          </Barra>
          <Barra>
            <span className="dash-muted">Sugeridos:</span>
            {(summary.top_grupos_publicaciones || []).slice(0, 5).map((g) => (
              <button key={g.name} className="dash-btn" onClick={() => llenarPrimerHueco(g.name)}>{g.name}</button>
            ))}
          </Barra>

          {compLoading && <Skeleton filas={5} />}
          <Aviso>{compError}</Aviso>

          {compData.length === 1 && !compLoading && (
            <p className="dash-muted">
              Queda un solo grupo en la comparación. Escribe otro nombre en un campo libre y pulsa Comparar.
            </p>
          )}

          {compData.length > 0 && !compLoading && (
            <>
              <div className="dash-table-wrap" style={{ marginBottom: "1.2em" }}>
                <table className="dash-table">
                  <thead>
                    <tr>
                      <th>Indicador</th>
                      {compData.map((d) => (
                        <th key={d.grupo}>
                          <div className="dash-col-head">
                            <span>{d.grupo}</span>
                            <button
                              className="dash-slot-x"
                              onClick={() => quitarGrupo(d.grupo)}
                              title={`Quitar ${d.grupo} de la comparación`}
                              aria-label={`Quitar ${d.grupo} de la comparación`}
                            >
                              ×
                            </button>
                          </div>
                          <div style={{ fontWeight: 400, fontSize: "0.75rem", color: "#555" }}>{d.clasificacion}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td><strong>Ciudad</strong></td>{compData.map((d) => <td key={d.grupo}>{d.ciudad || "—"}</td>)}</tr>
                    <tr><td><strong>Líder</strong></td>{compData.map((d) => <td key={d.grupo}>{d.lider || "—"}</td>)}</tr>
                    <tr><td><strong>Formado en</strong></td>{compData.map((d) => <td key={d.grupo}>{d.anio_formacion || "—"}</td>)}</tr>
                    <tr>
                      <td><strong>Publicaciones</strong></td>
                      {compData.map((d, i) => (
                        <td key={d.grupo} className={i === bestIdx(compData.map((x) => x.n_publicaciones)) ? "dash-comp-best" : undefined}>
                          {nf(d.n_publicaciones)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Miembros</strong></td>
                      {compData.map((d, i) => (
                        <td key={d.grupo} className={i === bestIdx(compData.map((x) => x.n_miembros)) ? "dash-comp-best" : undefined}>
                          {nf(d.n_miembros)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Última publicación</strong></td>
                      {compData.map((d, i) => (
                        <td key={d.grupo} className={i === bestIdx(compData.map((x) => x.ultimo_anio || 0)) ? "dash-comp-best" : undefined}>
                          {d.ultimo_anio || "—"}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>% avalados</strong></td>
                      {compData.map((d) => (
                        <td key={d.grupo}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5em" }}>
                            <div className="dash-bar-track" style={{ height: 12, minWidth: 60 }}>
                              <div className="dash-bar-fill" style={{ width: `${pctAval(d)}%`, background: "#059669" }} />
                            </div>
                            <strong>{pctAval(d)}%</strong>
                          </div>
                          <span className="dash-muted">{nf(d.avalados_si)} de {nf(d.avalados_si + d.avalados_no)}</span>
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Tipo destacado</strong></td>
                      {compData.map((d) => <td key={d.grupo}>{d.por_tipo[0] ? `${d.por_tipo[0].name} (${nf(d.por_tipo[0].value)})` : "—"}</td>)}
                    </tr>
                    <tr>
                      <td><strong>Área destacada</strong></td>
                      {compData.map((d) => <td key={d.grupo}>{d.top_areas[0] ? `${d.top_areas[0].name} (${nf(d.top_areas[0].value)})` : "—"}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>

              <h4>Evolución anual (misma escala vertical por grupo)</h4>
              <div className="dash-grid">
                {compData.map((d, i) => (
                  <div className="dash-card" key={d.grupo}>
                    <h5 style={{ margin: "0 0 0.5em" }}>{d.grupo}</h5>
                    <SerieAnual items={d.por_anio} color={["#1f6feb", "#7c3aed", "#d97706"][i]} height={150} />
                  </div>
                ))}
              </div>

              <h4>Productos por tipo (misma escala)</h4>
              <div className="dash-grid">
                {(() => {
                  const commonMax = Math.max(1, ...compData.flatMap((d) => d.por_tipo.map((t) => t.value)));
                  return compData.map((d) => (
                    <div key={d.grupo}>
                      <h5 style={{ margin: "0 0 0.5em" }}>{d.grupo}</h5>
                      <BarList items={d.por_tipo} color="#1f6feb" max={commonMax} />
                    </div>
                  ));
                })()}
              </div>

              <h4>Avalados por grupo</h4>
              <div className="dash-grid">
                {compData.map((d) => (
                  <div key={d.grupo}>
                    <h5 style={{ margin: "0 0 0.5em" }}>{d.grupo}</h5>
                    <Donut si={d.avalados_si} no={d.avalados_no} labelSi="Avalados SÍ" labelNo="Avalados NO" />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {view === "publicaciones" && (
        <div>
          <h3>Publicaciones ({nf(pubs.data.total)})</h3>
          <Barra>
            <input
              className="dash-field dash-field-grow"
              placeholder="Buscar en publicación..."
              value={pubs.filtros.search}
              onChange={(e) => pubs.setFiltro("search", e.target.value)}
            />
            <select className="dash-field" value={pubs.filtros.tipo} onChange={(e) => pubs.setFiltro("tipo", e.target.value)}>
              <option value="">Todos los tipos</option>
              {filtros.tipos.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select className="dash-field" value={pubs.filtros.avalado} onChange={(e) => pubs.setFiltro("avalado", e.target.value)}>
              <option value="">Avalados: todos</option>
              <option value="SI">SÍ</option>
              <option value="NO">NO</option>
            </select>
            <select className="dash-field" value={pubs.filtros.programa} onChange={(e) => pubs.setFiltro("programa", e.target.value)}>
              <option value="">Todos los programas</option>
              {filtros.programas.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select className="dash-field" value={pubs.filtros.anio_desde} onChange={(e) => pubs.setFiltro("anio_desde", e.target.value)} title="Año desde">
              <option value="">Año desde</option>
              {filtros.anios.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <select className="dash-field" value={pubs.filtros.anio_hasta} onChange={(e) => pubs.setFiltro("anio_hasta", e.target.value)} title="Año hasta">
              <option value="">Año hasta</option>
              {filtros.anios.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            {pubs.hayFiltros && <button className="dash-btn" onClick={pubs.limpiar}>Limpiar</button>}
            <button className="dash-btn" onClick={() => downloadCSV("/demo/publicaciones.csv", pubs.paramsExport)} title="Descarga todas las publicaciones filtradas (texto completo)">
              Exportar CSV
            </button>
            {pubs.cargando && <span className="dash-muted">Actualizando…</span>}
          </Barra>

          {(pubs.filtros.anio_desde || pubs.filtros.anio_hasta) && (
            <p className="dash-muted" style={{ marginTop: 0 }}>
              Al filtrar por año se excluyen las publicaciones cuyo año no se pudo identificar en el texto.
            </p>
          )}

          <Aviso>{pubs.error}</Aviso>
          {pubs.cargando && pubs.data.items.length === 0 ? <Skeleton /> : (
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <Th campo="grupo" orden={pubs.orden} onOrden={pubs.setOrden}>Grupo</Th>
                    <Th campo="tipo" orden={pubs.orden} onOrden={pubs.setOrden}>Tipo</Th>
                    <Th campo="avalado" orden={pubs.orden} onOrden={pubs.setOrden}>Avalado</Th>
                    <Th campo="anio" orden={pubs.orden} onOrden={pubs.setOrden} num>Año</Th>
                    <Th campo="publicacion" orden={pubs.orden} onOrden={pubs.setOrden}>Publicación</Th>
                  </tr>
                </thead>
                <tbody>
                  {pubs.data.items.length === 0 && !pubs.cargando && (
                    <tr><td colSpan={5} className="dash-muted">Ninguna publicación coincide con los filtros.</td></tr>
                  )}
                  {pubs.data.items.map((p, i) => (
                    <tr key={i}>
                      <td>
                        <button className="dash-link" onClick={() => { onSelectGroup(p.grupo); setGPick(p.grupo); onSelectView("unico"); }}>
                          {p.grupo}
                        </button>
                      </td>
                      <td>{p.tipo}</td>
                      <td>{p.avalado}</td>
                      <td className="num">{p.anio || "—"}</td>
                      <td>{p.publicacion}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={pubs.data.page} pages={pubs.data.pages} total={pubs.data.total} onPage={pubs.irPagina} cargando={pubs.cargando} />
        </div>
      )}

      {view === "miembros" && (
        <div>
          <h3>Miembros ({nf(miem.data.total)})</h3>
          <Barra>
            <input
              className="dash-field dash-field-grow"
              placeholder="Buscar integrante o grupo..."
              value={miem.filtros.search}
              onChange={(e) => miem.setFiltro("search", e.target.value)}
            />
            <select className="dash-field" value={miem.filtros.estado} onChange={(e) => miem.setFiltro("estado", e.target.value)}>
              <option value="">Todos los estados</option>
              <option value="activo">Activo</option>
              <option value="inactivo">Inactivo</option>
            </select>
            {miem.hayFiltros && <button className="dash-btn" onClick={miem.limpiar}>Limpiar</button>}
            <button className="dash-btn" onClick={() => downloadCSV("/demo/miembros.csv", miem.paramsExport)} title="Descarga todos los miembros filtrados (sin paginar)">
              Exportar CSV
            </button>
            {miem.cargando && <span className="dash-muted">Actualizando…</span>}
          </Barra>

          <Aviso>{miem.error}</Aviso>
          {miem.cargando && miem.data.items.length === 0 ? <Skeleton /> : (
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <Th campo="grupo" orden={miem.orden} onOrden={miem.setOrden}>Grupo</Th>
                    <Th campo="integrante" orden={miem.orden} onOrden={miem.setOrden}>Integrante</Th>
                    <Th campo="estado" orden={miem.orden} onOrden={miem.setOrden}>Estado</Th>
                  </tr>
                </thead>
                <tbody>
                  {miem.data.items.length === 0 && !miem.cargando && (
                    <tr><td colSpan={3} className="dash-muted">Ningún miembro coincide con los filtros.</td></tr>
                  )}
                  {miem.data.items.map((m, i) => (
                    <tr key={i}>
                      <td>
                        <button className="dash-link" onClick={() => { onSelectGroup(m.grupo); setGPick(m.grupo); onSelectView("unico"); }}>
                          {m.grupo}
                        </button>
                      </td>
                      <td>{m.integrante}</td>
                      <td>{m.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pager page={miem.data.page} pages={miem.data.pages} total={miem.data.total} onPage={miem.irPagina} cargando={miem.cargando} />
        </div>
      )}
    </div>
  );
};

export default Dashboard;
