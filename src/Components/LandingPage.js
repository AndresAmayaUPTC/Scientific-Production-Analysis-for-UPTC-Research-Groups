import React from "react";
import Book from "../images/famicons--book-outline.png";
import Arrow from "../images/line-md--arrow-right.png";
import Info from "../images/octicon--info-16.png";
import Groups from "../images/ci--users.png";
import "./landingpage.css";

function LandingPage() {
  return (
    <div className="main-container">
      <header>
        <div className="image-container">
          <img
            src={Book}
            alt="Book icon"
            loading="eager"
            width={42}
            height={42}
          />
        </div>

        <div>
          <h1>Bienvenido a SCI-UPTC.</h1>
          <span>Scientific Production Analysis for UPTC Research Groups</span>
        </div>

        <button onClick={() => (window.location.href = "/mainView")}>
          Ir a la Aplicación
          <img
            src={Arrow}
            alt="Arrow icon"
            loading="eager"
            width={20}
            height={20}
          />
        </button>
      </header>

      <section>
        <article>
          <div>
            <img
              src={Groups}
              alt="Groups icon"
              loading="lazy"
              width={24}
              height={24}
            />
            <h2>Grupos de Investigación</h2>
          </div>
          {/* <p>
          Participan los siguientes grupos de investigación..Infelcom, Gamma.
        </p> */}
          <ul>
            <li>
              <span>Infelcom</span>
            </li>
            <li>
              <span>Gamma</span>
            </li>
          </ul>
        </article>

        <article>
          <div>
            <img
              src={Info}
              alt="Info icon"
              loading="lazy"
              width={24}
              height={24}
            />
            <h2>Información Básica</h2>
          </div>

          <p>
            Software que permite la captura y análisis de información sobre
            productos de apropiación social y desarrollo tecnológico desde la
            plataforma GrupLAC-SCIENTI, con el fin de evaluar y potenciar la
            producción reportada y avalada por los grupos de investigación de la
            UPTC.
          </p>

          <footer className="aditional-info">
            <p>
              <strong>Desarrollado por:</strong> Grupo de Investigación INFELCOM
            </p>
          </footer>
        </article>
      </section>
    </div>
  );
}

export default LandingPage;
