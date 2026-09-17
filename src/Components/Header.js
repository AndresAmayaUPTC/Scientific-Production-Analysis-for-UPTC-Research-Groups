import React from "react";
import "./App.css";
import Help from "../images/material-symbols--help-outline-rounded.png";

const Header = () => {
  return (
    <header className="app-header">
      <div className="header-left-side">
        <img
          src="https://uptc.edu.co/sitio/portal/PRUEBAS/pruebasM/Frontal/.content/img/botones/logoUPTC24.svg"
          alt="UPTC logo"
          loading="eager"
          width={200}
        />
        <h1>Scientific Production Analysis for UPTC Research Groups</h1>
      </div>

      <div className="header-right-side">
        <a
          href="/help.html?origen=app"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Help link"
        >
          <img src={Help} alt="Help Icon" width={30} />
        </a>
      </div>
    </header>
  );
};

export default Header;
