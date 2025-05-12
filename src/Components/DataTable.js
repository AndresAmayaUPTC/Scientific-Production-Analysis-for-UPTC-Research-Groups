import React, { useState, useEffect } from "react";

export const DataTable = () => {
  const [data, setData] = useState([]); // Estado para almacenar los datos de la API
  const [loading, setLoading] = useState(true); // Estado para mostrar un indicador de carga
  const [error, setError] = useState(null); // Estado para manejar errores

  // Función para obtener los datos desde la API
  const fetchData = async () => {
    try {
      const response = await fetch("https://"); // URL de tu API/pendiente
      if (!response.ok) {
        throw new Error("Error al obtener los datos");
      }
      const result = await response.json();
      setData(result); // Guardar los datos en el estado
      setLoading(false); // Quitar el estado de carga
    } catch (error) {
      setError(error.message); // Guardar el mensaje de error
      setLoading(false); // Quitar el estado de carga en caso de error
    }
  };

  // Efecto que se ejecuta cuando el componente se monta
  useEffect(() => {
    fetchData();
  }, []); // [] asegura que se ejecute solo una vez cuando el componente se monta

  if (loading) {
    return <div>Cargando datos...</div>; // Mostrar indicador de carga
  }
  if (error) {
    return <div>Error: {error}</div>; // Mostrar mensaje de error
  }
  return (
    <div>
      <h2>Lista de Grupos de Investigación</h2>
      <table>
        <thead>
          <tr>
            <th>Nombre del Grupo</th>
            <th>Ciudad</th>
            <th>Año de Formación</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.id}>
              <td>{item.groupName}</td>
              <td>{item.city}</td>
              <td>{item.yearOfFormation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};