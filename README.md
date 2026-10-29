# Observatorio de medios electorales — MVP para Render

Plataforma privada de monitoreo de medios, prellenado asistido por OpenAI, revisión humana sincronizada con YouTube y analítica de registros aprobados. **No está afiliada al Tecnológico de Monterrey:** su dirección visual retoma una estética universitaria contemporánea, sin utilizar logotipos oficiales.

## Funciona hoy

- Inicio de sesión para `admin` y `revisor`, sin contraseñas dentro del código.
- Registro por día de hasta **50 URLs de YouTube** (una por línea), con medio, etapa y programa.
- Extracción *intentada* de subtítulos de YouTube con marcas de tiempo (español, español de México, inglés).
- **Importación manual alternativa de SRT/VTT**, indispensable cuando YouTube bloquea la recuperación desde Render.
- Cola de trabajos en PostgreSQL, procesada por un servicio worker independiente.
- Análisis de tramos de 10 minutos mediante OpenAI y `Structured Outputs`, vinculado a segmentos temporales.
- Menciones con emisor, sujeto, cita, contexto, tiempos, género periodístico, tema, valoración y hallazgos de 25 categorías cualitativas.
- Pantalla de revisión con reproductor de YouTube que inicia en el fragmento y acceso directo a la fuente.
- Guardado, aprobación, descarte, correcciones y bitácora de cambios.
- Registro manual de menciones que la IA haya omitido; confirmación humana de testigos sin mención.
- Analítica por etapa y exportación CSV de **menciones aprobadas**.
- Etapa `prueba` separada de la estadística oficial (ideal para ensayar con una conferencia matutina).

## Despliegue en Render.com

1. Sube la carpeta completa a un repositorio GitHub privado. No incluyas `.env` ni claves API en Git.
2. En Render, elige **New → Blueprint** y conecta el repositorio. Detectará `render.yaml`.
3. El Blueprint crea un **Web Service**, un **Background Worker** y **Render Postgres**. En Render configura las variables solicitadas **en ambos servicios cuando corresponda**:
   - `ADMIN_PASSWORD`: contraseña fuerte de administrador (servicio web).
   - `REVIEWER_PASSWORD`: contraseña fuerte de revisor (servicio web).
   - `OPENAI_API_KEY`: tu clave de OpenAI (worker). **No la pegues dentro del código ni en el navegador.**
   - `OPENAI_MODEL`: por defecto `gpt-4.1-mini`; asegúrate de que tu cuenta tiene acceso a este modelo y que soporta `Responses API` y `Structured Outputs`.
   - `DATABASE_URL` y `APP_SECRET`: el Blueprint los conecta/genera automáticamente.
4. Confirma los costos de los planes que Render te muestra. El worker y PostgreSQL permanentes **no están incluidos como un único sitio estático gratuito**.
5. Una vez desplegado, inicia sesión como `admin` con la contraseña configurada y agrega la URL de tu **conferencia matutina** con etapa **Prueba metodológica**.
6. Si el testigo queda en **Falta transcripción**, abre su ficha e importa una transcripción SRT/VTT que incluya tiempos. El sistema encolará inmediatamente el análisis.
7. Entra a **Mesa de revisión**, reproduce las menciones, corrige campos y aprueba. Consulta los resultados en **Analítica electoral → Pruebas**.

**IMPORTANTE SOBRE YOUTUBE**: la API oficial de YouTube para descargar subtítulos requiere permisos de edición sobre el video; no puede emplearse libremente para obtener subtítulos de cualquier URL pública. El paquete `youtube-transcript-api` es no oficial y advierte que los proveedores cloud pueden sufrir bloqueos por IP. Por eso el producto NO promete la extracción automática del 100% de los videos. La alternativa SRT/VTT es parte del flujo productivo. No se usan proxies, descargas de video ni técnicas de evasión de restricciones.

## Prueba local

Con Python 3.11+:

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
cp .env.example .env
# Edita .env, pon APP_SECRET/ADMIN_PASSWORD/REVIEWER_PASSWORD y OPENAI_API_KEY
uvicorn app.main:app --reload
```

En otra terminal, con el mismo entorno:

```bash
python -m app.worker
```

Visita http://localhost:8000; el administrador inicia sesión como `admin`; la cuenta de revisión usa `revisor`. Para correr pruebas automáticas, desde la carpeta raíz:

```bash
pytest -q
```

## Arquitectura

```text
Navegador -> FastAPI/Jinja/JS -> PostgreSQL (Render)
    |                                  ^
    | registro de URLs                 | transcripciones + menciones + auditoría
    +--> YouTube iframe (reproducción)  |
                          Worker <-- cola de trabajos Postgres
                            |--> youtube-transcript-api (si funciona)
                            |--> SRT/VTT manual (alternativa)
                            +--> OpenAI Responses API (prellenado)
```

El **worker** es persistente; la web no procesa entrevistas de dos horas mientras atiende solicitudes. El worker consulta la cola cada 3 segundos. Los trabajos se reclaman con `FOR UPDATE SKIP LOCKED` en PostgreSQL, permitiendo añadir workers en el futuro. El análisis se realiza por bloques de aproximadamente 10 minutos y guarda avances por ventana; en caso de fallo de API, el trabajo puede reintentarse manualmente.

Los registros generados por IA nunca se convierten automáticamente en aprobados. El paso de aprobación ocurre en una operación aparte que audita valor anterior y nuevo. Los modelos no calculan duraciones: el backend las deriva de las marcas temporales de los segmentos.

## Limitaciones del MVP y siguiente fase

1. **No hay almacenamiento propio de videos/audio**: el archivo permanece exclusivamente en YouTube. Si desaparece, se privatiza, bloquea la reproducción embebida o cambia la cuenta, la referencia histórica puede dejar de ser reproducible. Conserva por separado los originales y sus derechos de acceso. El texto importado y las menciones sí quedan en PostgreSQL.
2. Los subtítulos de YouTube son segmentos aproximados, **no alineación garantizada a nivel de palabra**, y no identifican de forma fiable todas las voces. El revisor debe ajustar los segundos y comprobar el emisor.
3. El análisis con OpenAI es un **prellenado**, no una clasificación metodológicamente validada. Puede perder menciones, confundir personas o identificar de forma errónea categorías. Todos los negativos deben tener muestreo de calidad y revisión de testigos sin mención.
4. La detección de los 25 aspectos cualitativos utiliza el **texto**, no fotogramas. Categorías visuales como cosificación en televisión requieren un módulo multimodal adicional.
5. No hay catálogo oficial actualizado de candidaturas 2026–2027 ni cruce automático con partidos, género, distrito, cargo y coalición. Se necesita integrarlo para operar un proceso electoral real. La prueba con una mañanera en etapa `prueba` no debe interpretarse como monitoreo electoral oficial.
6. El Dashboard implementa los indicadores base (menciones aprobadas, temas, etapas, sujetos, categorías). **No genera aún los 11 indicadores completos** de la matriz cuantitativa ni los informes metodológicos quincenales. Los indicadores de participación por género, programas y tiempo de cobertura deben modelarse contra catálogos oficiales, mediciones de transmisión e interrupciones verificadas.
7. El sistema usa `Base.metadata.create_all` como inicio rápido; en producción necesitará migraciones con Alembic, backups, gestión de usuarios persistentes, control de sesiones avanzado y alertas.
8. La versión base restringe a dos roles por contraseña de entorno. Antes de operar con un equipo grande se requiere gestión individual de usuarios, permisos y MFA.
9. Las solicitudes de OpenAI tienen costo y podrían verse limitadas por cuota y velocidad. Los tiempos de ejecución dependen de la densidad del transcript y el modelo utilizado.
10. Los cambios al catálogo o reglas metodológicas deberán versionarse para preservar la interpretación histórica de las clasificaciones.

## Estructura de carpetas

```text
app/main.py         Rutas web, autorización, formularios y analítica
app/models.py       Esquema SQLAlchemy
app/transcripts.py  URLs y subtítulos SRT/VTT / YouTube
app/pipeline.py     OpenAI estructurado y validación de evidencias
app/worker.py       Cola y procesamiento en background
app/definitions.py  25 categorías y catálogos iniciales
app/templates/      Pantallas del sistema
app/static/         CSS y JavaScript
render.yaml         Blueprint Render con web + worker + DB
tests/              Pruebas sin llamadas externas
```

## Metodología

Se usa la Matriz 1 de análisis cuantitativo (11 indicadores) y Matriz 2 de análisis cualitativo (25 aspectos) aportadas por el equipo. Los aspectos cualitativos se integran como categorías configurables; las expresiones sugeridas por IA no son conclusiones oficiales. Antes de producción deben implementarse el diccionario metodológico definitivo y los catálogos oficiales del proceso.

## Seguridad

- Cookie de sesión firmada y marcada como segura en Render, tokens CSRF, roles separados.
- Credenciales y llave de OpenAI solo en variables de entorno.
- IDs de YouTube validados por allowlist de host; nunca se consulta un servidor arbitrario usando una URL suministrada por el usuario.
- Consultas con ORM y exportación CSV que neutraliza fórmulas peligrosas.
- Bitácora de ediciones y revisión humana.
- Base PostgreSQL sin acceso público externo en el Blueprint.

Para alta criticidad o producción pública agregar rate limiting, auditoría centralizada, cuentas nominativas, políticas de retención, monitoreo de seguridad y revisión jurídica de conservación de contenidos.

### Recomendación para videos que suben ustedes a su propio canal

Si los videos son subidos por su propia cuenta de YouTube, pueden usar la **API oficial de subtítulos** (más adecuada que el extractor público). Configura manualmente estas variables opcionales en **Environment → observatorio-worker** de Render:

- `YOUTUBE_CLIENT_ID` y `YOUTUBE_CLIENT_SECRET` del cliente OAuth de Google Cloud de tu organización.
- `YOUTUBE_REFRESH_TOKEN` emitido tras autorizar con la cuenta que puede **editar esos videos**, con alcance `https://www.googleapis.com/auth/youtube.force-ssl` y acceso *offline*.
- Habilita **YouTube Data API v3** en el proyecto de Google Cloud; comprueba las cuotas antes de procesar 30 grabaciones diarias. Las llamadas `captions.list` y `captions.download` tienen costos de cuota propios.

El worker intentará primero la descarga oficial en formato VTT; si falla, intentará subtítulos públicos y, por último, solicitará importación manual. La conexión Google OAuth y el manejo de credenciales son opcionales; **no se incluyen flujos web de consentimiento ni gestión de canales en este MVP**. No hay claves en el repositorio y el flujo debe configurarse por el administrador del canal.
