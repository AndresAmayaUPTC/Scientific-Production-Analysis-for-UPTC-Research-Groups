# Importa las librerías necesarias
from flask import Flask, jsonify
from pymongo import MongoClient

# Inicializa la aplicación Flask
app = Flask(__name__)

import os

# La cadena de conexión se lee del entorno. Antes estaba escrita aquí en
# claro, con usuario y contraseña, en un archivo versionado en git.
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "sci_uptc")
if not MONGODB_URI:
    raise RuntimeError(
        "Falta MONGODB_URI. Copia .env.example a .env y pon ahi la cadena de "
        "conexion del cluster de Atlas."
    )

# Conexión a la base de datos MongoDB
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
collection = db['grupos']

# Endpoint para obtener todos los datos completos de la colección
@app.route('/datos', methods=['GET'])
def obtener_datos():
    # Devuelve toda la información de la colección sin el campo _id
    datos = list(collection.find({}, {'_id': 0}))
    return jsonify(datos)

# Endpoint para obtener los miembros de cada grupo
@app.route('/miembros', methods=['GET'])
def obtener_miembros():
    miembros = []
    # Busca los grupos y sus miembros
    grupos = list(collection.find({}, {'_id': 0, 'nombre_grupo': 1, 'miembros': 1}))
    for grupo in grupos:
        nombre_grupo = grupo.get('nombre_grupo', 'Sin Nombre')
        for miembro in grupo.get('miembros', []):
            miembros.append({
                'nombre_grupo': nombre_grupo,
                'nombre_miembro': miembro.get('Nombre del integrante', 'Sin Nombre'),
                'estado': miembro.get('Estado', 'Desconocido')
            })
    return jsonify(miembros)

# Endpoint para obtener las publicaciones de cada grupo
@app.route('/publicaciones', methods=['GET'])
def obtener_publicaciones():
    publicaciones = []
    # Busca los grupos y sus publicaciones
    grupos = list(collection.find({}, {'_id': 0, 'nombre_grupo': 1, 'publicaciones': 1}))
    for grupo in grupos:
        nombre_grupo = grupo.get('nombre_grupo', 'Sin Nombre')
        for publicacion in grupo.get('publicaciones', []):
            publicaciones.append({
                '_id': publicacion.get('_id', 'Desconocido'),
                'nombre_grupo': nombre_grupo,
                'titulo': publicacion.get('Título', 'Sin Título'),
                'tipo': publicacion.get('Tipo', 'Desconocido'),
                'tipo_publicacion': publicacion.get('Tipo Publicación', 'Desconocido'),
                'revista': publicacion.get('Revista', 'Desconocida'),
                'pais': publicacion.get('País', 'Desconocido'), 
                'ISSN': publicacion.get('ISSN', 'Desconocido'),
                'año': publicacion.get('Año', 'Desconocido'),
                'volumen': publicacion.get('Volumen', 'Desconocido'),
                'autores': publicacion.get('Autores', 'Desconocido'),
                'avalado': publicacion.get('avalado', 'Desconocido'),
                'todo': publicacion.get('todo', 'Desconocido'),
                'DOI': publicacion.get('DOI', 'Desconocido'),
            })
    return jsonify(publicaciones)

# Punto de entrada principal para ejecutar la aplicación Flask
if __name__ == '__main__':
    app.run(debug=True)