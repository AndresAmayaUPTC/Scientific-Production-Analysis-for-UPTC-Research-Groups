import React, { useState } from "react";
import { nf } from "./api";

export const COLORS = ["#1f6feb", "#7c3aed", "#059669", "#d97706", "#be123c", "#0284c7", "#6d28d9", "#0d9488"];

/** Barras horizontales. `max` opcional permite comparar listas en la misma escala. */
export const BarList = ({ items, color, max }) => {
  if (!items || items.length === 0) return <p className="dash-muted">Sin datos</p>;
  const scale = max || Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="dash-bars">
      {items.map((it, idx) => (
        <div className="dash-bar-row" key={`${it.name}-${idx}`}>
          <span className="dash-bar-name" title={it.name}>{it.name}</span>
          <div className="dash-bar-track">
            <div
              className="dash-bar-fill"
              style={{
                width: `${Math.max(3, Math.round((it.value / scale) * 100))}%`,
                background: color || COLORS[0],
              }}
            />
          </div>
          <strong className="dash-bar-value">{nf(it.value)}</strong>
        </div>
      ))}
    </div>
  );
};

export const Donut = ({ si = 0, no = 0, labelSi = "Sí", labelNo = "No" }) => {
  const total = si + no || 1;
  const f = si / total;
  const C = 2 * Math.PI * 40;
  const pct = Math.round(f * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1em", flexWrap: "wrap" }}>
      <svg width="120" height="120" viewBox="0 0 100 100" role="img" aria-label={`${labelSi}: ${pct}%`}>
        <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="14" />
        <circle
          cx="50" cy="50" r="40" fill="none" stroke="#059669" strokeWidth="14"
          strokeDasharray={`${(f * C).toFixed(1)} ${C.toFixed(1)}`}
          transform="rotate(-90 50 50)" strokeLinecap="round"
        />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="central" fontSize="18" fontWeight="800" fill="#181818">
          {pct}%
        </text>
      </svg>
      <div style={{ fontSize: "0.9rem", display: "flex", flexDirection: "column", gap: "0.3em" }}>
        <span><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#059669", marginRight: "0.4em" }} />{labelSi}: <strong>{nf(si)}</strong></span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "#e5e7eb", marginRight: "0.4em" }} />{labelNo}: <strong>{nf(no)}</strong></span>
      </div>
    </div>
  );
};

/**
 * Serie de publicaciones por año: columnas + línea de tendencia.
 * Los años sin datos se rellenan en 0 para que los huecos se vean como
 * huecos y no como una serie continua falsa.
 */
export const SerieAnual = ({ items, color = "#1f6feb", height = 190, onPickAnio }) => {
  const [hover, setHover] = useState(null);
  if (!items || items.length === 0) return <p className="dash-muted">Sin datos con año identificable</p>;

  const min = items[0].anio;
  const max = items[items.length - 1].anio;
  const mapa = new Map(items.map((d) => [d.anio, d.value]));
  const serie = [];
  for (let a = min; a <= max; a++) serie.push({ anio: a, value: mapa.get(a) || 0 });

  const W = 720;
  const H = height;
  const padL = 44, padR = 10, padT = 12, padB = 28;
  const iw = W - padL - padR;
  const ih = H - padT - padB;
  const maxV = Math.max(...serie.map((d) => d.value), 1);
  const bw = iw / serie.length;
  const x = (i) => padL + i * bw;
  const y = (v) => padT + ih - (v / maxV) * ih;

  const linea = serie.map((d, i) => `${x(i) + bw / 2},${y(d.value)}`).join(" ");
  const ticksY = [0, Math.round(maxV / 2), maxV];
  // Con muchos años, etiquetar todos es ilegible: se marca uno de cada N.
  const paso = Math.max(1, Math.ceil(serie.length / 12));
  // El último año se etiqueta siempre; un año intermedio se omite si queda
  // tan cerca de él que los textos se pisarían (p. ej. "2025" junto a "2026").
  const ultimo = serie.length - 1;
  const ANCHO_ETIQUETA = 34; // "2026" a 10 px, con algo de aire
  const conEtiqueta = (i) =>
    i === ultimo || (i % paso === 0 && (ultimo - i) * bw >= ANCHO_ETIQUETA);

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img"
        aria-label={`Publicaciones por año entre ${min} y ${max}`}>
        {ticksY.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="#eee" />
            <text x={padL - 6} y={y(t)} textAnchor="end" dominantBaseline="central" fontSize="10" fill="#777">{nf(t)}</text>
          </g>
        ))}
        {serie.map((d, i) => (
          <rect
            key={d.anio}
            x={x(i) + bw * 0.15}
            y={y(d.value)}
            width={bw * 0.7}
            height={Math.max(0, padT + ih - y(d.value))}
            fill={hover === i ? "#181818" : color}
            opacity={hover === null || hover === i ? 1 : 0.55}
            style={{ cursor: onPickAnio ? "pointer" : "default" }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            onClick={() => onPickAnio && onPickAnio(d.anio)}
          >
            <title>{`${d.anio}: ${nf(d.value)} publicaciones`}</title>
          </rect>
        ))}
        <polyline points={linea} fill="none" stroke="#181818" strokeWidth="1.5" opacity="0.5" />
        {serie.map((d, i) => (
          conEtiqueta(i) ? (
            <text key={d.anio} x={x(i) + bw / 2} y={H - 8} textAnchor="middle" fontSize="10" fill="#777">{d.anio}</text>
          ) : null
        ))}
      </svg>
      {hover !== null && (
        <p className="dash-muted" style={{ margin: "0.2em 0 0" }}>
          <strong>{serie[hover].anio}</strong>: {nf(serie[hover].value)} publicaciones
          {onPickAnio ? " · clic para filtrar por ese año" : ""}
        </p>
      )}
    </div>
  );
};

export const WordCloud = ({ items, onPick }) => {
  if (!items || items.length === 0) return <p className="dash-muted">Sin datos</p>;
  const vals = items.map((i) => i.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const size = (v) => {
    if (max === min) return 1.2;
    const t = (Math.log(v) - Math.log(min)) / (Math.log(max) - Math.log(min));
    return 0.85 + t * 1.5;
  };
  return (
    <div className="dash-cloud">
      {items.map((w, idx) => (
        <button
          key={w.text}
          className="dash-cloud-word"
          title={`${w.text}: ${nf(w.value)} menciones. Clic para buscar publicaciones.`}
          onClick={() => onPick && onPick(w.text)}
          style={{
            fontSize: `${size(w.value).toFixed(2)}rem`,
            fontWeight: w.value > (min + max) / 2 ? 800 : 500,
            color: COLORS[idx % COLORS.length],
          }}
        >
          {w.text}
        </button>
      ))}
    </div>
  );
};

// Contorno simplificado de Colombia en grados (lon, lat). Se proyecta con
// la misma función que los puntos, así silueta y ciudades siempre encajan.
const COLOMBIA = [
  [-71.66, 12.46], [-72.2, 11.4], [-72.9, 11.55], [-74.2, 11.25], [-74.8, 11.0],
  [-75.5, 10.4], [-75.6, 9.5], [-76.7, 8.1], [-77.4, 8.5], [-77.8, 7.1],
  [-77.4, 6.2], [-77.1, 3.9], [-77.9, 2.6], [-78.8, 1.8], [-78.85, 1.45],
  [-77.6, 0.8], [-76.5, 0.5], [-75.2, -0.6], [-73.5, -1.8], [-70.1, -2.9],
  [-69.95, -4.2], [-69.5, -1.1], [-69.8, 1.1], [-67.9, 1.3], [-67.3, 1.9],
  [-67.5, 3.8], [-67.85, 6.3], [-69.4, 6.1], [-70.7, 7.0], [-72.0, 7.1],
  [-72.5, 7.9], [-72.9, 9.1], [-72.2, 11.4], [-71.1, 12.2],
];

const LON_MIN = -79.5, LON_MAX = -66.5, LAT_MIN = -4.8, LAT_MAX = 13.2;

/**
 * Mapa de puntos proporcionales sobre la silueta del país. Sustituye a la
 * lista de barras que antes ocupaba el lugar del "mapa".
 */
export const MapaCiudades = ({ items, metrica = "publicaciones", onPick, seleccion = "" }) => {
  const conCoords = (items || []).filter((c) => c.lat != null && c.lon != null);
  if (conCoords.length === 0) return <p className="dash-muted">Sin ciudades ubicables</p>;

  const W = 420, H = 560;
  const px = (lon) => ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * W;
  const py = (lat) => ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * H;
  const path = COLOMBIA.map(([lon, lat], i) => `${i === 0 ? "M" : "L"}${px(lon).toFixed(1)},${py(lat).toFixed(1)}`).join(" ") + " Z";

  const maxV = Math.max(...conCoords.map((c) => c[metrica] || 0), 1);
  // Radio por área, no por valor: evita exagerar las diferencias.
  const r = (v) => 5 + Math.sqrt((v || 0) / maxV) * 26;
  const ordenadas = [...conCoords].sort((a, b) => (b[metrica] || 0) - (a[metrica] || 0));

  return (
    <svg className="dash-map" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mapa de ciudades con producción científica">
      <path className="dash-map-land" d={path} />
      {ordenadas.map((c) => {
        const activa = seleccion === c.ciudad;
        return (
          <g key={c.ciudad}>
            <circle
              className="dash-map-dot"
              cx={px(c.lon)} cy={py(c.lat)} r={r(c[metrica])}
              fill={activa ? "#181818" : "#1f6feb"}
              fillOpacity={activa ? 0.85 : 0.55}
              stroke={activa ? "#ffcc28" : "#1f6feb"}
              strokeWidth={activa ? 2.5 : 1}
              onClick={() => onPick && onPick(activa ? "" : c.ciudad)}
            >
              <title>{`${c.ciudad}\n${nf(c.publicaciones)} publicaciones · ${nf(c.grupos)} grupos · ${nf(c.miembros)} miembros`}</title>
            </circle>
            <text className="dash-map-label" x={px(c.lon)} y={py(c.lat) - r(c[metrica]) - 3} textAnchor="middle">
              {c.ciudad.split(" - ").pop()}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

/** Encabezado de tabla que ordena al hacer clic. */
export const Th = ({ campo, orden, onOrden, children, num = false }) => {
  const activo = orden.sort === campo;
  const flecha = !activo ? "↕" : orden.dir === "asc" ? "↑" : "↓";
  return (
    <th className={num ? "num" : undefined} aria-sort={activo ? (orden.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        className="dash-sort"
        onClick={() => onOrden(campo, activo && orden.dir === "desc" ? "asc" : "desc")}
        title={`Ordenar por ${typeof children === "string" ? children : campo}`}
      >
        {children}
        <span className={`dash-sort-arrow${activo ? "" : " off"}`}>{flecha}</span>
      </button>
    </th>
  );
};

export const Pager = ({ page, pages, total, onPage, cargando }) => (
  <div style={{ display: "flex", gap: "0.8em", alignItems: "center", marginTop: "0.8em", flexWrap: "wrap" }}>
    <button className="dash-btn" disabled={page <= 1 || cargando} onClick={() => onPage(page - 1)}>← Anterior</button>
    <span style={{ fontSize: "0.9rem" }}>
      Página {page} de {pages} ({nf(total)} registros)
    </span>
    <button className="dash-btn" disabled={page >= pages || cargando} onClick={() => onPage(page + 1)}>Siguiente →</button>
  </div>
);

export const Skeleton = ({ filas = 5 }) => (
  <div aria-busy="true" aria-live="polite">
    {Array.from({ length: filas }, (_, i) => (
      <div key={i} className="dash-skeleton" style={{ width: `${95 - i * 7}%` }} />
    ))}
  </div>
);
