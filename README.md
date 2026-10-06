# HomeLens English 🔍🇬🇧

Asistente educativo inteligente para el aprendizaje contextual del idioma inglés a partir de la exploración visual de objetos cotidianos en el hogar, impulsado por visión multimodal (Google Gemini), actividades interactivas, desafíos *Find It* y síntesis de voz (TTS).

---

## 📌 Repositorio y Entorno
- **Repositorio Remoto:** [https://github.com/patoabarca/HomeLens_English](https://github.com/patoabarca/HomeLens_English)
- **Tipo de Repositorio:** Privado
- **Rama Actual:** `HLE_Pato` (Parte 4: Análisis con Gemini & Integración M3)

---

## 🏛️ Arquitectura Modular (M0 a M8)

El sistema implementa una arquitectura modular con contratos estrictos y bajo acoplamiento:

| Módulo | Nombre | Responsabilidad |
| :--- | :--- | :--- |
| **M0** | **Configuración y Entorno** | Carga segura de variables de entorno sin exposición de credenciales y registro de eventos técnicos (`config.py`, `telemetria.py`). |
| **M1** | **Acceso de Usuarios** | Gestión de contexto de identidad de usuario y control de sesión (`acceso.py`). |
| **M2** | **Captura y Preparación** | Validación de formatos reales (JPEG/PNG), límites de tamaño, corrección EXIF y gestión en memoria sin persistencia de fotos (`imagenes.py`, `ui/captura.py`). |
| **M3** | **Análisis con Gemini** | Detección multimodal de objetos, normalización geométrica `[ymin, xmin, ymax, xmax]`, esquemas estructurados y generación de actividades formativas (`analisis.py`, `integraciones/gemini.py`). |
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
- **Invalidación automática:** Al cambiar de archivo o alternar entre cámara y subida de archivo, se invalidan inmediatamente las preparaciones anteriores.
- **Liberación de recursos:** El botón *Quitar / Reemplazar Imagen* invoca `liberar_imagen()` para descartar referencias en memoria.
- **Sin persistencia:** No se escriben imágenes en disco, bases de datos ni logs técnicos.

---

## 🤖 M3: Análisis Visual y Educativo con Gemini (Parte 4)

El módulo **M3** (`homelens/analisis.py`, `homelens/integraciones/gemini.py`, `homelens/esquemas_ia.py` y `homelens/prompts/exploracion.txt`) realiza el reconocimiento multimodal y la generación de contenido educativo mediante una **única llamada principal estructurada**:

### 1. Modelo Seleccionado y Justificación
- **Modelo:** `gemini-1.5-flash` (configurable mediante la variable `GEMINI_MODEL`).
- **Verificación oficial:** Soporte nativo de visión multimodal y salida estructurada JSON (`response_schema=RespuestaExploracionIA`).
- **Ventajas:** Latencia mínima, alta velocidad de inferencia, bajo costo operativo y precisión en la detección de objetos y generación bilingüe (EN/ES) de nivel A1/A2.

### 2. Contrato de Entrada y Salida
```python
analizar_exploracion(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    operacion_id: UUID,
    adaptador: Optional[AdaptadorGemini] = None,
) -> Resultado[Exploracion]
```

### 3. Principios y Validaciones Estrictas
- **Una llamada atómica por exploración:** Obtiene en un solo paso el estado del análisis, los objetos detectados (1 a 5), recuadros normalizados `[0, 1000]`, traducciones, frases de ejemplo y cuestionarios interactivos de 3 opciones.
- **Defensa contra Prompt Injection:** El prompt explicita que la imagen y cualquier texto visible en ella son contenido a analizar y no instrucciones de control.
- **Validación geométrica exhaustiva:** Exige `0 <= ymin, xmin, ymax, xmax <= 1000`, `ymin < ymax` y `xmin < xmax`.
- **Integridad de actividades:** Verifica exactamente 3 opciones distintas por pregunta, existencia obligatoria de la opción correcta y correspondencia de referencias cruzadas entre preguntas y objetos.
- **Mapeo a entidades inmutables:** Traduce identificadores locales de IA a `UUID` inmutables del dominio, asignando la autoría al `ContextoUsuario`.
- **Manejo diferenciado de errores:** Clasifica errores de cuota (`429 / LIMITE_ALCANZADO`), credenciales (`401/403 / ACCESO_DENEGADO`), tiempos de espera (`TIEMPO_AGOTADO`), respuestas bloqueadas/inválidas (`RESPUESTA_INVALIDA`) y fallos temporales de red (`SERVICIO_NO_DISPONIBLE`), sin exponer secretos.
- **Telemetría no bloqueante:** Registra duración en milisegundos, reintentos y tokens utilizados vía `homelens/telemetria.py`.

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
│   ├── analisis.py             # M3: Coordinación y validación de análisis Gemini
│   ├── exploracion.py          # M4: Coordenadas de pantalla y tarjetas
│   ├── audio.py                # M5: Caché y síntesis de voz
│   ├── practicas.py            # M6: Evaluación de prácticas e intentos
│   ├── progreso.py             # M8: Cálculo de avance formativo
│   ├── esquemas_ia.py          # M3: Esquemas Pydantic para respuestas de Gemini
│   │
│   ├── datos/                  # M7: Capa de persistencia
│   │   ├── __init__.py
│   │   └── repositorio.py      # Contrato de repositorio
│   │
│   ├── integraciones/          # Adaptadores externos
│   │   ├── __init__.py
│   │   ├── autenticacion.py    # Proveedor de autenticación
│   │   ├── gemini.py           # M3: Adaptador del SDK de Google Gemini
│   │   └── tts.py              # Cliente Google Cloud TTS
│   │
│   ├── prompts/                # Plantillas versionadas de prompts
│   │   ├── exploracion.txt     # M3: Prompt pedagógico y multimodal
│   │   └── find_it.txt
│   │
│   └── ui/                     # Componentes y estado de interfaz Streamlit
│       ├── __init__.py
│       ├── estado.py           # Estado de sesión y ciclo de vida de imágenes
│       └── captura.py          # M2/M3: Pantalla de captura y prueba manual
│
└── tests/                      # Suite de pruebas automatizadas
    ├── __init__.py
    ├── test_modelos.py         # Invariantes y entidades del dominio
    ├── test_config.py          # Validación segura de entorno M0
    ├── test_imagenes.py        # Cobertura exhaustiva de validación M2
    ├── test_analisis.py        # Cobertura exhaustiva de validación y simulación M3
    ├── test_exploracion.py     # Proyecciones de pantalla y tarjetas M4
    └── test_progreso.py        # Lógica pura de cálculo de progreso M8
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

> ℹ️ **Modo Demostración:** No es necesario configurar claves externas para ejecutar la demostración inicial. La aplicación levantará de forma inmediata e informará el estado de las integraciones en la barra lateral.

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

### 5. Detener la Aplicación
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
*(Si vas a probar el análisis real con Gemini, añade tu `GEMINI_API_KEY=tu_api_key_aqui` en `.env`)*

### 5. Ejecutar con Streamlit
```bash
streamlit run app.py
```
Abre en tu navegador: [http://localhost:8501](http://localhost:8501).

---

## 🧪 Pruebas Automatizadas vs. Verificación Manual

### Pruebas Automatizadas Unitarias (43 tests - 100% aisladas)
Ejecuta la suite con:
```bash
python -m unittest discover -s tests -v
```
o con pytest:
```bash
pytest -v
```

**Cobertura automatizada (sin consumo de API ni credenciales):**
- ✅ **M0 Configuración:** Carga segura y defaults.
- ✅ **M2 Captura e Imágenes:** Validación JPEG/PNG, límites de tamaño, orientación EXIF, canales alfa, coherencia de dimensiones y liberación de recursos.
- ✅ **M3 Análisis Gemini (Simulado):**
  - Análisis exitoso con 1 y múltiples objetos educativos.
  - Resultados válidos de estados `SIN_OBJETOS_CLAROS` y `REPETIR_CAPTURA`.
  - Rechazo estricto de exceso de objetos (> 5).
  - Rechazo de coordenadas fuera de rango (`> 1000` o `< 0`).
  - Rechazo de coordenadas invertidas (`ymin >= ymax` o `xmin >= xmax`).
  - Rechazo de campos faltantes o vacíos (nombres, frases).
  - Rechazo de preguntas con opciones duplicadas o solución no existente.
  - Rechazo de referencias a objetos inexistentes.
  - Manejo controlado de errores de cuota (429), timeout, credenciales inválidas (401/403) y caídas de servicio (503).
  - Comportamiento seguro de `AdaptadorGemini` sin credenciales.
  - Ocultamiento de soluciones en `obtener_actividades_publicas`.
- ✅ **M4 Exploración y M8 Progreso:** Invariantes de dominio, cálculos puros de estadísticas y tarjetas.

### Prueba Manual en Vivo con Gemini (Acción Explícita)
1. Coloca tu clave en `.env`: `GEMINI_API_KEY=AIzaSy...`
2. Inicia la aplicación con `streamlit run app.py`.
3. Navega a **Exploración Visual**, carga una imagen o toma una fotografía y presiona **"⚙️ Preparar Imagen"**.
4. Haz clic en el botón explícito **"🔍 Analizar Imagen con Gemini"**.
5. Se enviará la imagen transitoria y se listarán los objetos educativos y preguntas generadas.

---

## 💡 Funcionamiento del Modo Demostración

En el modo demostración (sin credenciales externas configuradas):
- ✅ **Carga segura de configuración:** El sistema inicializa valores por defecto seguros y reporta el estado de cada servicio en la barra lateral sin fallar.
- ✅ **Captura y preparación M2:** Admite subir archivos o usar la cámara, previsualizar, corregir orientación y preparar la imagen en memoria.
- ✅ **Aviso informativo en M3:** Al intentar analizar sin clave en `.env`, informa de manera limpia que se requiere configurar `GEMINI_API_KEY`.
- 🟡 **Servicios protegidos:** Supabase y TTS muestran estado pendiente de forma informativa y limpia.

---

## 📋 Estado de Implementación

- [x] Repositorio Git local y sincronización remota.
- [x] Exclusión de credenciales asegurada con `.gitignore` previo y `.env.example`.
- [x] Modelos de dominio compartidos (`homelens/modelos.py`) con validaciones e invariantes.
- [x] Sistema de manejo de errores controlado (`homelens/errores.py`) con `Resultado[T]`.
- [x] Módulo M0 (`config.py`, `telemetria.py`) para arranque seguro de la aplicación.
- [x] Módulo M2 (`imagenes.py`, `ui/captura.py`) con validación y orientación de imágenes.
- [x] Módulo M3 (`analisis.py`, `integraciones/gemini.py`, `esquemas_ia.py`, `prompts/exploracion.txt`) con llamada multimodal estructurada y validación exhaustiva.
- [x] Módulo M4 (`exploracion.py`) con funciones puras para recuadros en pantalla.
- [x] Módulo M8 (`progreso.py`) con cálculo puro de palabras y estadísticas.
- [x] Entorno de contenedorización (`Dockerfile`, `compose.yaml`, `.dockerignore`).
- [x] Suite de 43 pruebas automatizadas con 100% de éxito.

---

## 🛠️ Solución de Problemas Habituales

| Problema | Causa Posible | Solución |
| :--- | :--- | :--- |
| `Bind for 0.0.0.0:8501 failed: port is already allocated` | El puerto 8501 está siendo utilizado por otra instancia local de Streamlit u otro proceso. | Detén el proceso que usa el puerto 8501 o cambia el mapeo de puertos en `compose.yaml` (ej. `"8502:8501"`). |
| `Cannot connect to the Docker daemon` / `Docker daemon is not running` | Docker Desktop no está iniciado o el servicio Docker está detenido. | Inicia la aplicación **Docker Desktop** o el servicio `dockerd` antes de ejecutar `docker compose`. |
| `open .env: no such file or directory` | Falta el archivo `.env` en la raíz del proyecto. | Ejecuta `cp .env.example .env` (o `Copy-Item .env.example .env` en PowerShell) para generar el archivo antes de iniciar Compose. |
| `ModuleNotFoundError` en entorno local | Las dependencias no fueron instaladas en el entorno virtual activo. | Verifica que el entorno `.venv` esté activo y ejecuta `pip install -r requirements.txt`. |
| Cámara no disponible en navegador | El navegador bloqueó el permiso de cámara. | Permite el acceso a la cámara en el icono de candado en la barra de direcciones del navegador. |
| Error `LIMITE_ALCANZADO` al analizar con Gemini | Se superó la cuota gratuita por minuto de la API de Google Gemini. | Espera un minuto antes de enviar una nueva imagen. |
