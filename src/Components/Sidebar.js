import React from "react";
import "./App.css";
import { VIEWS } from "./views";

// Botonera presentacional: solo avisa qué vista se eligió.
// MainView pasa la vista activa al Dashboard, que decide qué sección pinta.
const Sidebar = ({ activeView = "resumen", onSelectView = () => {} }) => (
  <div className="sidebar">
    <div className="pagination-buttons">
      {VIEWS.map((v) => (
        <button
          key={v.id}
          className={"button-pagination" + (activeView === v.id ? " active" : "")}
          aria-current={activeView === v.id ? "page" : undefined}
          onClick={() => onSelectView(v.id)}
        >
          {v.label}
        </button>
      ))}
    </div>
  </div>
);

export default Sidebar;
