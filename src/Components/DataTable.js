import React, { useState, useEffect } from "react";

// Componente DataTable para mostrar la lista de grupos de investigación
export const DataTable = () => {
  // Estado para almacenar los datos obtenidos de la API
  const [data, setData] = useState([]);
  // Estado para controlar si los datos están cargando
  const [loading, setLoading] = useState(true);
  // Estado para manejar posibles errores en la petición
  const [error, setError] = useState(null);

  // Función asíncrona para obtener los datos desde la API
  const fetchData = async () => {
    try {
      // Realiza la petición a la API
      const response = await fetch("http://localhost:5000/groups");
      if (!response.ok) {
        // Si la respuesta no es exitosa, lanza un error
        throw new Error("Error al obtener los datos");
      }
      // Convierte la respuesta en JSON
      const result = await response.json();
      console.log(result); // Muestra los datos recibidos en consola
      setData(result); // Guarda los datos en el estado
      setLoading(false); // Quita el estado de carga
    } catch (error) {
      setError(error.message); // Guarda el mensaje de error
      setLoading(false); // Quita el estado de carga en caso de error
    }
  };

  // useEffect para ejecutar fetchData solo una vez al montar el componente
  useEffect(() => {
    fetchData();
  }, []);

  // Si está cargando, muestra un mensaje de carga
  if (loading) {
    return <div>Cargando datos...</div>;
  }
  // Si hay error, muestra el mensaje de error
  if (error) {
    return <div>Error: {error}</div>;
  }
  // Renderiza la tabla con los datos obtenidos
  return (
    <div>
      <h3>Lista de Grupos de Investigación</h3>
      <table>
        <thead>
          <tr>
            <th>Nombre del Grupo</th>
            <th>Departamento</th>
            <th>Ciudad</th>
            <th>Lider</th>
            <th>Pagina Web</th>
            <th>Email</th>
            {/* ...otras columnas... */}
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item._id}>
              <td>{item.nombre_grupo}</td>
              <td>{item.departamento}</td>
              <td>{item.ciudad}</td>
              <td>{item.lider}</td>
              <td>{item.pagina_web}</td>
              <td>{item.email}</td>
              <td>{item.clasificacion}</td>
              <td>{item.area_conocimiento}</td>
              <td>{item.programa_ciencia_tecnologia}</td>
              <td>{item.programa_ciencia_tecnologia_secundario}</td>
              <td>{item.plan_estrategico}</td>
              {/* ...otras celdas... */}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};