# HomeLens English 🔍🇬🇧

Asistente educativo inteligente para el aprendizaje contextual del idioma inglés a partir de la exploración visual de objetos cotidianos en el hogar, impulsado por visión multimodal (Google Gemini), actividades interactivas, desafíos *Find It* y síntesis de voz (TTS).

---

## 📌 Repositorio y Entorno
- **Repositorio Remoto:** [https://github.com/patoabarca/HomeLens_English](https://github.com/patoabarca/HomeLens_English)
- **Tipo de Repositorio:** Privado
- **Rama Principal:** `main`

---

## 🏛️ Arquitectura Modular (M0 a M8)

El sistema implementa una arquitectura modular con contratos estrictos y bajo acoplamiento:

| Módulo | Nombre | Responsabilidad |
| :--- | :--- | :--- |
| **M0** | **Configuración y Entorno** | Carga segura de variables de entorno sin exposición de credenciales y registro de eventos técnicos (`config.py`, `telemetria.py`). |
| **M1** | **Acceso de Usuarios** | Gestión de contexto de identidad de usuario y control de sesión (`acceso.py`). |
| **M2** | **Captura y Preparación** | Validación de formatos reales (JPEG/PNG), límites de tamaño, corrección EXIF y gestión en memoria sin persistencia de fotos (`imagenes.py`, `ui/captura.py`). |
| **M3** | **Análisis con Gemini** | Detección de objetos, normalización geométrica y generación de actividades formativas (`analisis.py`). |
| **M4** | **Exploración y Contenido** | Adaptación de coordenadas a la pantalla y generación de tarjetas pedagógicas (`exploracion.py`). |
| **M5** | **Audio y Pronunciación** | Síntesis de voz con Google Cloud TTS y caché temporal de sesión (`audio.py`). |
| **M6** | **Prácticas y Find It** | Evaluación local de cuestionarios y verificación de desafíos (`practicas.py`). |
| **M7** | **Persistencia e Historial** | Contratos de persistencia atómica y aislamiento de datos por usuario (`datos/repositorio.py`). |
| **M8** | **Progreso y Analítica** | Consolidación y cálculo del estado de vocabulario aprendido (`progreso.py`). |

---

## 📸 M2: Captura y Preparación de Imágenes (Parte 3)

El módulo **M2** (`homelens/imagenes.py` y `homelens/ui/captura.py`) gestiona la ingesta de fotografías garantizando privacidad, seguridad e integridad antes de cualquier integración con modelos de IA:

### 1. Reglas y Procesamiento en `homelens/imagenes.py`
- **Comprobación de tamaño previa:** Verifica que el archivo no supere los `10 000 000 bytes` (10 MB) antes de decodificar en memoria.
- **Validación de formato real:** Admite exclusivamente `JPEG` y `PNG`. Rechaza archivos corruptos, imágenes truncadas o archivos de texto disfrazados con extensión de imagen.
- **Corrección de orientación EXIF:** Corrige automáticamente la rotación generada por teléfonos móviles y cámaras fotográficas usando `ImageOps.exif_transpose`.
- **Saneamiento de privacidad:** Elimina metadatos EXIF innecesarios (coordenadas GPS, modelo de dispositivo, fechas).
- **Tratamiento de color y transparencias:** Normaliza modos de color (CMYK, P, L) a RGB/RGBA y compone transparencias sobre blanco para salidas JPEG.
- **Preservación de proporción:** Mantiene exactamente la orientación y relación de aspecto original para la visualización en pantalla y posterior delimitación geométrica.
- **Estructura inmutable:** Retorna `Resultado[ImagenPreparada]` con bytes limpios, tipo MIME y dimensiones reales coherentes.

### 2. Ciclo de Vida y Gestión de Memoria (`homelens/ui/estado.py`)
- **Aislamiento en sesión:** La imagen se conserva temporalmente en memoria (`st.session_state.imagen_preparada`).
- **Invalidación automática:** Al cambiar de archivo o cambiar entre cámara y subida de archivo, se invalidan inmediatamente las preparaciones anteriores.
- **Liberación de recursos:** El botón *Quitar / Reemplazar Imagen* invoca `liberar_imagen()` para descartar referencias en memoria.
- **Sin persistencia:** No se escriben imágenes en disco, bases de datos ni logs técnicos.

### 3. Punto de Conexión con Gemini (M3)
El objeto `ImagenPreparada` preparado por M2 queda disponible en la sesión para ser recibido directamente por la función de análisis de M3:
```python
analizar_exploracion(
    usuario=st.session_state.usuario,
    imagen=st.session_state.imagen_preparada,
    operacion_id=uuid4(),
)
```

---

## 📁 Estructura del Proyecto

```text
HomeLens_English/
├── .env.example               # Plantilla versionada de variables de entorno
├── .gitignore                  # Exclusión de credenciales (.env), temporales y caches
├── .dockerignore               # Exclusión de archivos sensibles en build de contenedor
├── Dockerfile                  # Contenedorización de la aplicación (Python 3.11-slim)
├── compose.yaml                # Orquestación de Docker Compose para Streamlit
├── pyproject.toml              # Metadatos del paquete y dependencias
├── requirements.txt            # Dependencias fijadas para instalación directa
├── README.md                   # Documentación principal del sistema
├── app.py                      # Punto de entrada de Streamlit y coordinación
│
├── homelens/                   # Paquete principal del dominio
│   ├── __init__.py
│   ├── modelos.py              # Entidades inmutables y estados de dominio
│   ├── errores.py              # Resultado[T] y ErrorOperacion
│   ├── config.py               # M0: Carga y validación de configuración
│   ├── telemetria.py           # M0: Métricas técnicas y eventos
│   ├── acceso.py               # M1: Contexto de identidad de usuario
│   ├── imagenes.py             # M2: Validación, saneamiento y procesado de imágenes
│   ├── analisis.py             # M3: Interfaz de análisis con Gemini
│   ├── exploracion.py          # M4: Coordenadas de pantalla y tarjetas
│   ├── audio.py                # M5: Caché y síntesis de voz
│   ├── practicas.py            # M6: Evaluación de prácticas e intentos
│   ├── progreso.py             # M8: Cálculo de avance formativo
│   ├── esquemas_ia.py          # Esquemas Pydantic para respuestas de IA
│   │
│   ├── datos/                  # M7: Capa de persistencia
│   │   ├── __init__.py
│   │   └── repositorio.py      # Contrato de repositorio
│   │
│   ├── integraciones/          # Adaptadores externos
│   │   ├── __init__.py
│   │   ├── autenticacion.py    # Proveedor de autenticación
│   │   ├── gemini.py           # Cliente Google Gemini
│   │   └── tts.py              # Cliente Google Cloud TTS
│   │
│   ├── prompts/                # Plantillas versionadas de prompts
│   │   ├── exploracion.txt
│   │   └── find_it.txt
│   │
│   └── ui/                     # Componentes y estado de interfaz Streamlit
│       ├── __init__.py
│       ├── estado.py           # Estado de sesión y ciclo de vida de imágenes
│       └── captura.py          # M2: Pantalla de captura, uploader y preparación
│
└── tests/                      # Suite de pruebas automatizadas
    ├── __init__.py
    ├── test_modelos.py
    ├── test_config.py
    ├── test_imagenes.py        # Cobertura exhaustiva de validación M2
    ├── test_exploracion.py
    └── test_progreso.py
```

---

## 🐳 Ejecución con Docker (Recomendada)

### 1. Requisitos Previos
- **Docker Engine** (20.10+) o **Docker Desktop** instalado y en ejecución.
- **Docker Compose** (v2 o superior / plugin `docker compose`).

### 2. Configurar Variables de Entorno
Crea tu archivo local `.env` a partir de la plantilla versionada `.env.example`:

- **En Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
- **En Linux / macOS / Git Bash:**
  ```bash
  cp .env.example .env
  ```

> ℹ️ **Modo Demostración:** No es necesario configurar claves externas (Gemini, Supabase, TTS) para ejecutar la demostración. El archivo `.env` creado a partir de `.env.example` permite levantar la aplicación de forma inmediata.

### 3. Construir e Iniciar la Aplicación

Para construir la imagen e iniciar el contenedor en primer plano:
```bash
docker compose up --build
```

Si prefieres iniciarlo en segundo plano (modo detached):
```bash
docker compose up -d --build
```

### 4. Acceso a la Aplicación
Una vez que el contenedor esté activo, accede desde tu navegador web a:
- **URL:** [http://localhost:8501](http://localhost:8501)

### 5. Consultar Registros (Logs)
Para ver los registros en tiempo real del servicio:
```bash
docker compose logs -f app
```

### 6. Detener la Aplicación
- Si iniciaste en primer plano: presiona `Ctrl + C`.
- Para detener y remover los contenedores asociados:
  ```bash
  docker compose down
  ```

---

## 💻 Ejecución Local (Sin Docker)

### 1. Requisitos Previos
- Python 3.10, 3.11 o superior instalado.
- Git.

### 2. Crear y Activar Entorno Virtual
```bash
# Crear entorno virtual
python -m venv .venv

# Activar en Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Activar en Linux / macOS:
source .venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar `.env`
```bash
cp .env.example .env
```

### 5. Ejecutar con Streamlit
```bash
streamlit run app.py
```
Abre en tu navegador: [http://localhost:8501](http://localhost:8501).

---

## 🧪 Pruebas Automatizadas vs. Verificación Manual

### Pruebas Automatizadas Unitarias (26 tests)
Ejecuta la suite con:
```bash
python -m unittest discover -s tests -v
```
o con pytest:
```bash
pytest -v
```

Cobertura automatizada:
- ✅ Imágenes válidas en formatos JPEG y PNG.
- ✅ Rechazo estricto de archivos por encima del límite (`10 MB`).
- ✅ Rechazo de formatos no admitidos (GIF, BMP, etc.).
- ✅ Rechazo de archivos corruptos o texto plano con extensión `.jpg`.
- ✅ Rechazo de imágenes JPEG truncadas con fin de archivo prematuro.
- ✅ Corrección y transposición de orientación basada en metadatos EXIF.
- ✅ Tratamiento de canales alfa y modo RGBA.
- ✅ Coherencia estricta entre dimensiones, tipo MIME y bytes resultantes en `ImagenPreparada`.
- ✅ Redimensionado opcional respetando la relación de aspecto.
- ✅ Liberación de recursos con `liberar_imagen`.
- ✅ Modelos inmutables, invariantes de dominio, configuración y cálculo de progreso.

### Aspectos de Verificación Manual
- 📱 **Acceso a la cámara web o móvil:** Requiere aceptar permisos de cámara en el navegador web del usuario.
- 📱 **Diseño vertical en teléfonos:** Comprobar la disposición de columnas y legibilidad de vista previa en pantallas táctiles.

---

## 💡 Funcionamiento del Modo Demostración

En el modo demostración (sin credenciales externas configuradas):
- ✅ **Carga segura de configuración:** El sistema inicializa valores por defecto seguros y reporta el estado de cada servicio en la barra lateral sin fallar.
- ✅ **Contexto de usuario ficticio:** Se asigna un identificador de usuario local (`00000000-0000-0000-0000-000000000001`) para permitir el flujo sin base de datos activa.
- ✅ **Captura y preparación M2:** Admite subir archivos o usar la cámara, previsualizar, corregir orientación y preparar la imagen en memoria.
- ✅ **Aislamiento educativo:** No se muestran etiquetas falsas simulando análisis sobre fotos del usuario.
- 🟡 **Servicios externos protegidos:** Los servicios que requieren API keys (Gemini, Supabase, TTS) muestran estado pendiente de forma informativa y limpia.

---

## 📋 Estado de la Entrega 1

- [x] Repositorio Git local inicializado y vinculado al origen remoto.
- [x] Exclusión de credenciales asegurada con `.gitignore` previo y `.env.example`.
- [x] Modelos de dominio compartidos (`homelens/modelos.py`) con validaciones e invariantes.
- [x] Sistema de manejo de errores controlado (`homelens/errores.py`) con `Resultado[T]`.
- [x] Módulo M0 (`config.py`, `telemetria.py`) para arranque seguro de la aplicación.
- [x] Módulo M2 (`imagenes.py`) con validación estricta de formatos y dimensiones.
- [x] Módulo M4 (`exploracion.py`) con funciones puras para recuadros en pantalla.
- [x] Módulo M8 (`progreso.py`) con cálculo puro de palabras y estadísticas.
- [x] Arquitectura de persistencia (`datos/repositorio.py`) e integraciones preparadas.
- [x] Interfaz inicial de Streamlit (`app.py`) con navegación modular.
- [x] Entorno de contenedorización (`Dockerfile`, `compose.yaml`, `.dockerignore`).
- [x] Suite de pruebas automatizadas con 100% de cobertura sobre las funciones puras.

---

## 🛠️ Solución de Problemas Habituales

| Problema | Causa Posible | Solución |
| :--- | :--- | :--- |
| `Bind for 0.0.0.0:8501 failed: port is already allocated` | El puerto 8501 está siendo utilizado por otra instancia local de Streamlit u otro proceso. | Detén el proceso que usa el puerto 8501 o cambia el mapeo de puertos en `compose.yaml` (ej. `"8502:8501"`). |
| `Cannot connect to the Docker daemon` / `Docker daemon is not running` | Docker Desktop no está iniciado o el servicio Docker está detenido. | Inicia la aplicación **Docker Desktop** o el servicio `dockerd` antes de ejecutar `docker compose`. |
| `open .env: no such file or directory` | Falta el archivo `.env` en la raíz del proyecto. | Ejecuta `cp .env.example .env` (o `Copy-Item .env.example .env` en PowerShell) para generar el archivo antes de iniciar Compose. |
| `ModuleNotFoundError` en entorno local | Las dependencias no fueron instaladas en el entorno virtual activo. | Verifica que el entorno `.venv` esté activo y ejecuta `pip install -r requirements.txt`. |
| Cámara no disponible en navegador | El navegador bloqueó el permiso de cámara. | Permite el acceso a la cámara en el icono de candado en la barra de direcciones del navegador. |
