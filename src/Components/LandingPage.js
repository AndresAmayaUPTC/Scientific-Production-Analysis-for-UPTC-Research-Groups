import React from 'react';
import './landingpage.css';

function LandingPage() {
  return (
    <div>
      <header>
        <h1>Bienvenido a SCI-UPTC.</h1> 
        <h2>(Scientific Production Analysis for UPTC Research Groups)</h2>
      </header>
      <section className='button_section'>
      <button onClick={() => window.location.href='/mainView'}>Ir a la Aplicación</button>
      </section>
      <section>
        <h2>Grupos de Investigación</h2>
        <p>Participan los siguientes grupos de investigación..Infelcom, Gamma.</p>
      </section>
      <section>
        <h2>Información Básica</h2>
        <p>Software que permite la captura y análisis de información sobre productos de apropiación social y desarrollo tecnológico desde la plataforma GrupLAC-SCIENTI, con el fin de evaluar y potenciar la producción reportada y avalada por los grupos de investigación de la UPTC.</p>
      </section>
      <footer>
        <p>Desarrollado por: Grupo de Investigación INFELCOM</p>
      </footer>
    
    </div>
  );
}

export default LandingPage;
