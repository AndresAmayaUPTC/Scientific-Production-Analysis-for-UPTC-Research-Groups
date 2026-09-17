import React, { useState } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import Dashboard from "./Dashboard";
import "../App.css";

function MainView() {
  // Vista activa compartida: los botones laterales cambian la pestaña del dashboard.
  const [view, setView] = useState("resumen");
  // Grupo seleccionado para la vista "Grupo Único"
  const [selectedGroup, setSelectedGroup] = useState("");

  return (
    <div className="App">
      <Header></Header>
      <div className="App_layout">
        <aside className="App_aside">
          <Sidebar activeView={view} onSelectView={setView}></Sidebar>
        </aside>
        <main className="App_main">
          <Dashboard
            view={view}
            onSelectView={setView}
            selectedGroup={selectedGroup}
            onSelectGroup={setSelectedGroup}
          ></Dashboard>
        </main>
      </div>
    </div>
  );
}

export default MainView;
