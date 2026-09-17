import React, { useState } from "react";

export const FilterComponent = ({ onFilter }) => {
  const [filters, setFilters] = useState({
    groupName: "",
    city: "",
    yearOfFormation: "",
  });

  // Función para manejar cambios en los inputs
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFilters({
      ...filters,
      [name]: value,
    });
  };

  // Función para enviar los filtros al componente padre
  const handleFilter = () => {
    onFilter(filters);
  };
  return (
    <div id="filter" >
      <div class="filtros">
        <label htmlFor="groupName">Nombre del Grupo:</label><br></br>
        <input
          type="text"
          id="groupName"
          name="groupName"
          value={filters.groupName}
          onChange={handleInputChange}
         
        />
      </div>
      <div class="filtros">
        <label htmlFor="city">Ciudad:</label><br></br>
        <input
          type="text"
          id="city"
          name="city"
          value={filters.city}
          onChange={handleInputChange}
       
        />
      </div>
      <div class="filtros">
        <label htmlFor="yearOfFormation">Año de Formación:</label><br></br>
        <input
          type="month"
          id="yearOfFormation"
          name="yearOfFormation"
          value={filters.yearOfFormation}
          onChange={handleInputChange}
         
        />
      </div>
      <button onClick={handleFilter} >
        Filtrar
      </button>
    </div>
  );
};

