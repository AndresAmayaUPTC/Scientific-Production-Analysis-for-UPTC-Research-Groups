# SCI-UPTC — Tablero de producción científica

Aplicación web para explorar la producción científica de los grupos de
investigación de la UPTC: 149 grupos, 10.561 integrantes y 20.935 productos,
descargados del GrupLac de Minciencias.

Las cifras de este README son las de la última descarga registrada; consulta
las vigentes con `python -m ingesta.run estado`.

- **Frontend:** React (Create React App), en `src/`.
- **Backend:** FastAPI + pandas, en `main.py`. Carga los datos a memoria al
  arrancar y expone agregados y tablas paginadas bajo `/demo/*`.
- **Ingesta:** paquete `ingesta/`. Scraping del GrupLac, escritura versionada
  en MongoDB Atlas, controles de calidad y respaldo en disco.

## Puesta en marcha

### Backend

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn main:app --reload --port 8000
```

Comprueba que cargó bien con `curl http://localhost:8000/demo/estado`.
La documentación interactiva queda en <http://localhost:8000/docs>.

Los datos se cargan a memoria al arrancar y se recargan solos después de cada
ingesta publicada. `POST /demo/recargar` fuerza una recarga sin reiniciar.

### Frontend

```bash
npm install
npm start
```

La URL del backend sale de `REACT_APP_API_URL`. Copia `.env.example` a `.env`
si necesitas apuntar a otro sitio; sin la variable se usa `http://localhost:8000`.

## Pruebas

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q      # backend e ingesta
npm test                               # frontend
```

Las pruebas de la ingesta usan `mongomock`: ejercitan el versionado, los
controles de calidad, la cadena de respaldo y los reintentos del scraping sin
necesidad de un Atlas real ni de red. Las del frontend incluyen el botón
«Volver a la aplicación» de `public/help.html`, cargando ese HTML en jsdom.

## Secciones del tablero

La barra lateral es el único menú. Todas las vistas comparten el estado de
grupo seleccionado, así que un clic en el nombre de un grupo desde cualquier
tabla abre su ficha.

| Sección | Qué muestra |
|---|---|
| Resumen general | Indicadores, serie anual de publicaciones y cortes por tipo, programa, clasificación, ciudad y área. |
| Total Grupos | Tabla de grupos, ordenable y filtrable por ciudad, clasificación y programa. |
| Grupo Único | Ficha de un grupo: evolución anual, líneas de investigación, contacto, productos y miembros. |
| Mapa Revistas | Mapa de puntos por ciudad y ranking de revistas extraídas del ISSN. |
| Nube de palabras | Términos frecuentes en títulos o áreas; al pulsar uno se buscan sus publicaciones. |
| Comparador | Hasta 3 grupos lado a lado, con la evolución anual en escalas comparables. |
| Publicaciones | Tabla completa con filtros de texto, tipo, aval, programa y rango de años. |
| Miembros | Integrantes por grupo y estado. |

Las tablas se exportan a CSV con los filtros aplicados (separador `;` y BOM,
para que Excel en español las abra directamente).

## Datos: MongoDB, scraping periódico y respaldo

Los datos se obtienen del GrupLac de Minciencias y viven en MongoDB Atlas.
El paquete `ingesta/` se encarga de todo el ciclo.

### Cómo no perder los datos cuando el scraping falla

Cada corrida escribe sus documentos etiquetados con un `run_id` propio y solo
al final, si supera los controles de calidad, mueve el puntero de versión
activa. El tablero lee siempre la versión activa, así que **una corrida que
falla o que trae datos truncados no toca lo que se está sirviendo**.

| Situación | Qué ocurre |
|---|---|
| El portal no responde | La corrida queda `fallida`. Sigue vigente la versión anterior. |
| Devuelve pocos grupos o publicaciones | Se marca `descartada` y se borran sus documentos. Sigue la anterior. |
| Cae más de un 20 % frente a la vigente | Se descarta igualmente, aunque supere los mínimos absolutos. |
| Todo correcto | Se publica, se guarda un snapshot en disco y se purgan las versiones viejas. |

Los umbrales se ajustan con `MIN_GRUPOS`, `MIN_PUBLICACIONES` y `MAX_DROP_RATIO`.

Además, el backend recorre una cadena de orígenes al cargar:

    MongoDB (versión publicada) → último snapshot en disco → Excel de extraccion-

`GET /demo/estado` dice cuál se está usando y por qué se descartaron las otras.

### El cluster

| | |
|---|---|
| Organización | Semillero UPTC |
| Proyecto | Scientific Production Analysis for UPTC Research Groups |
| Cluster | `sci-uptc` (M0 gratuito, AWS `us-east-1`, MongoDB 8.0) |
| Base de datos | `sci_uptc` |
| Usuario | `sci_uptc_app`, con permiso `readWrite` solo sobre `sci_uptc` |
| Acceso de red | `0.0.0.0/0` (protegido por usuario y contraseña) |

La cadena de conexión va en `.env`, que está en `.gitignore`. Para levantar el
entorno en otra máquina, copia `.env.example` a `.env` y pega ahí la URI que
da Atlas en **Database → Connect → Drivers**.

### Puesta en marcha de la base

```bash
cp .env.example .env          # y pon MONGODB_URI dentro

python -m ingesta.run sembrar   # crea colecciones, índices y la primera versión
python -m ingesta.run scrapear  # a partir de ahí, datos frescos del GrupLac
```

`sembrar` deja la base operativa sin depender de que el portal responda: crea
la base de datos, sus colecciones y una primera versión publicada a partir de
los Excel del repositorio.

### Comandos

```bash
python -m ingesta.run estado      # versión activa, conteos, última corrida
python -m ingesta.run scrapear    # una pasada (pensado para cron)
python -m ingesta.run sembrar     # recarga desde los Excel
python -m ingesta.run historial   # últimas corridas y por qué se descartaron
python -m ingesta.run respaldos   # snapshots guardados
python -m ingesta.run indices     # (re)crea los índices
```

### Descarga de las fichas

El portal corta conexiones si recibe muchas peticiones a la vez (con 8
simultáneas se perdieron ~50 fichas de 152 en la primera prueba). Por eso la
descarga va en dos fases:

1. **Primera pasada** con `SCRAPE_WORKERS` (3) descargas en paralelo.
2. **Reintentos** de las fichas fallidas, de una en una, con
   `SCRAPE_RETRY_PAUSE` (3 s) entre fichas. Hasta `SCRAPE_RETRY_ROUNDS` (3)
   rondas, esperando antes de cada una `SCRAPE_RETRY_ROUND_PAUSE` (30 s),
   que se duplica en cada ronda: 30 s, 60 s, 120 s.

Una ficha cuenta como fallida si no trae el nombre del grupo (petición
cortada o página de error). Las que sigan fallando se omiten, y si son muchas
los controles de calidad rechazan la corrida. Todas las peticiones tienen
límite de tiempo (`SCRAPE_TIMEOUT`).

### Periodicidad

El scraping se ejecuta solo, **una vez al mes**. Esa cadencia viene del ritmo
real del GrupLac: no tiene calendario de publicación —cada grupo edita su
ficha cuando quiere— y el flujo medido es de unas 5 publicaciones nuevas al día
repartidas entre 149 grupos (+2.471 publicaciones en los 17 meses que separan
los Excel de la primera descarga). La clasificación oficial de cada grupo, que
solo cambia con las convocatorias de Minciencias, se mueve cada 1–3 años.

Hay dos mecanismos, y conviene tener claro cuál cubre cada caso:

- **Planificador interno** (activo por defecto). Al arrancar el backend se
  programa una ingesta cada `SCRAPE_INTERVAL_HOURS` (720 h = 30 días). Solo funciona
  mientras el proceso esté vivo.
- **Cron externo.** `.github/workflows/ingesta.yml` lanza
  `python -m ingesta.run scrapear` el día 1 de cada mes a las 06:00 UTC, esté o no
  encendido el backend. Sirve igual para un Cron Job de Render. Requiere el
  secreto `MONGODB_URI` en el repositorio.

Si usas el cron externo, pon `SCRAPE_SCHEDULER=false` para que el backend no
scrapee también. Es lo recomendable cuando hay varias réplicas del backend,
para que no descarguen todas a la vez.

**Al arrancar** el backend no espera el mes completo a ciegas: `SCRAPE_ON_STARTUP=auto`
(el valor por defecto) comprueba el estado real de los datos y lanza una
ingesta de inmediato si están atrasados.

| Estado de la base al arrancar | ¿Scrapea ya? |
|---|---|
| Sin ninguna versión publicada | Sí |
| Solo sembrada desde los Excel | Sí — esos datos son una foto antigua |
| Última descarga hace más de `SCRAPE_INTERVAL_HOURS` | Sí |
| Última descarga reciente | No; espera al siguiente disparo |

Sin este comportamiento, un proceso que se reinicia antes de cumplirse el
intervalo no llegaría a scrapear nunca. `GET /admin/ingesta/estado` informa de
la decisión en los campos `datos_atrasados` y `motivo`.

### Endpoints de administración

```
GET  /admin/ingesta/estado      versión activa, próxima ejecución, snapshots,
                                si los datos están atrasados y por qué
GET  /admin/ingesta/historial   últimas corridas con su desenlace
POST /admin/ingesta/ejecutar    lanza una ingesta ahora (?origen_datos=excel
                                para sembrar desde los .xlsx)
GET  /demo/estado               qué fuente se está sirviendo y por qué
POST /demo/recargar             recarga en memoria sin reiniciar
                                (?preferir=mongodb|respaldo|excel)
```

> Estos endpoints no tienen autenticación. Antes de exponer el backend a
> Internet, protégelos (o déjalos solo en la red interna).

### Colecciones

| Colección | Contenido |
|---|---|
| `grupos` | Un documento por grupo: ciudad, líder, clasificación, programa, líneas, contacto. |
| `miembros` | Un documento por integrante. |
| `publicaciones` | Un documento por producto, con su año ya extraído. |
| `ejecuciones` | Historial de corridas: estado, conteos y motivo de rechazo. |
| `meta` | Puntero a la versión publicada. |

### Cuánto se guarda

Se conservan las **3 últimas versiones publicadas** en Mongo (`RUNS_KEEP`) y los
**10 últimos snapshots** en disco (`BACKUP_KEEP`, carpeta `respaldos/`, que está
en `.gitignore`). Las versiones más viejas se purgan solas tras cada ingesta.
Cada versión ocupa unos 15 MB, así que las tres caben de sobra en los 512 MB
del cluster gratuito. `MONGODB_DB` (por defecto `sci_uptc`) permite usar otra
base, por ejemplo para pruebas.

## Notas sobre los datos

El GrupLac no expone el año en un campo propio: viene dentro del texto de cada
registro, y en un sitio distinto según el formato — después del ISSN en
artículos, antes del ISBN en libros y capítulos. Se identifica en el **96 %**
de los registros (20.103 de 20.935):

| Tipo | Con año |
|---|---|
| Artículos publicados | 100 % |
| Otros artículos publicados | 100 % |
| Libros publicados | 100 % |
| Capítulos de libro publicados | 77 % |

**Al filtrar por rango de años, los registros sin año identificado quedan fuera
del resultado.**

Antes de leer el año, el texto se normaliza con `limpiar_registro`: el parser
del GrupLac rellena los tramos de espacios con `" _ "`, que ensuciaba las tablas
del tablero y dejaba ilegible el año de los libros (0 % de cobertura hasta que
se corrigió).

Los patrones viven en `_ANIO_PATRONES` (`ingesta/texto.py`) y están cubiertos
por `test_main.py`. Los comparten el scraper y el lector de Excel, así que si
aparece un formato nuevo basta con tocarlos ahí.

## Historial

El proyecto integraba un reporte embebido de Power BI. Se retiró junto con su
backend de tokens de Azure; el tablero local pasó a ser la única vista.

El scraper original (`extraccion-/scraping.py`) escribía directo en Mongo y
borraba las colecciones antes de descargar nada. Sus funciones de extracción
se conservan como biblioteca, pero la ingesta la gobierna ahora `ingesta/`.
