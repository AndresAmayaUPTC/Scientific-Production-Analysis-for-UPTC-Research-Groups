import React from 'react';
import { Logo } from './Logo';
import '../App.css';

const Sidebar = () => {
  const navigateToPage = (pageName) => {
    if (window.report) {
      window.report.setPage(pageName).catch((error) => {
        console.error('Error al navegar a la página:', error);
      });
    } else {
      console.error('El informe de Power BI aún no está incrustado.');
    }
  };

  return (
    <div className="sidebar">
      <div className="logo-container">
      <Logo />
      </div>
      <div className="pagination-buttons">
        <button onClick={() => navigateToPage('TotalGroup')}>Total Grupos</button>
        <button onClick={() => navigateToPage('Onlygropu')}>Grupo Unico</button>
        <button onClick={() => navigateToPage('Nube de palabras')}>Nube de palabras</button>
        <button onClick={() => navigateToPage('mapa de revistas')}>Mapa Revistas</button>
      </div>
    </div>
  );
};

export default Sidebar;