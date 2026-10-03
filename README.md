# HomeLens English 🔍🇬🇧

Asistente educativo inteligente para el aprendizaje contextual del idioma inglés a partir de la exploración visual de objetos cotidianos en el hogar, impulsado por visión multimodal (Google Gemini), actividades interactivas, desafíos *Find It* y síntesis de voz (TTS).

---

## 📌 Repositorio y Entorno
- **Repositorio Remoto:** [https://github.com/patoabarca/HomeLens_English](https://github.com/patoabarca/HomeLens_English)
- **Tipo de Repositorio:** Privado
- **Copia Local:** `c:\Users\Asus\Documents\Diplomatura IA\HomeLens_English`

---

## 🏛️ Arquitectura Modular (M0 a M8)

El sistema implementa una arquitectura modular con contratos estrictos y bajo acoplamiento:

| Módulo | Nombre | Responsabilidad |
| :--- | :--- | :--- |
| **M0** | **Configuración y Entorno** | Carga segura de variables de entorno sin exposición de credenciales y registro de eventos técnicos (`config.py`, `telemetria.py`). |
| **M1** | **Acceso de Usuarios** | Gestión de contexto de identidad de usuario y control de sesión (`acceso.py`). |
| **M2** | **Captura y Preparación** | Validación de formatos reales (JPEG/PNG), límites de tamaño y gestión en memoria sin persistencia de fotos (`imagenes.py`). |
| **M3** | **Análisis con Gemini** | Detección de objetos, normalización geométrica y generación de actividades formativas (`analisis.py`). |
| **M4** | **Exploración y Contenido** | Adaptación de coordenadas a la pantalla y generación de tarjetas pedagógicas (`exploracion.py`). |
| **M5** | **Audio y Pronunciación** | Síntesis de voz con Google Cloud TTS y caché temporal de sesión (`audio.py`). |
| **M6** | **Prácticas y Find It** | Evaluación local de cuestionarios y verificación de desafíos (`practicas.py`). |
| **M7** | **Persistencia e Historial** | Contratos de persistencia atómica y aislamiento de datos por usuario (`datos/repositorio.py`). |
| **M8** | **Progreso y Analítica** | Consolidación y cálculo del estado de vocabulario aprendido (`progreso.py`). |

---

## 📁 Estructura del Proyecto

```text
HomeLens_English/
├── .env.example               # Plantilla versionada de variables de entorno
├── .gitignore                  # Exclusión de credenciales (.env), temporales y caches
├── .dockerignore               # Exclusión de archivos sensibles en build de contenedor
├── Dockerfile                  # Contenedorización de la aplicación
├── compose.yaml                # Orquestación de Docker Compose
├── pyproject.toml              # Metadatos del paquete y dependencias
├── requirements.txt            # Dependencias fijadas para instalación directa
├── README.md                   # Documentación principal
├── app.py                      # Punto de entrada de Streamlit y coordinación
│
├── homelens/                   # Paquete principal del dominio
│   ├── __init__.py
│   ├── modelos.py              # Entidades inmutables y estados de dominio
│   ├── errores.py              # Resultado[T] y ErrorOperacion
│   ├── config.py               # M0: Carga y validación de configuración
│   ├── telemetria.py           # M0: Métricas técnicas y eventos
│   ├── acceso.py               # M1: Contexto de identidad de usuario
│   ├── imagenes.py             # M2: Validación y procesado de imágenes
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
│       └── estado.py           # Estado de sesión y ciclo de vida UI
│
└── tests/                      # Suite de pruebas automatizadas
    ├── __init__.py
    ├── test_modelos.py
    ├── test_config.py
    ├── test_imagenes.py
    ├── test_exploracion.py
    └── test_progreso.py
```

---

## 🚀 Instalación y Ejecución

### 1. Requisitos Previos
- Python 3.10 o superior (o Docker / Docker Desktop)
- Git

### 2. Configuración del Entorno Local

1. **Crear y activar entorno virtual:**
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   # En Linux/macOS:
   source .venv/bin/activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno:**
   Copia el archivo `.env.example` a `.env` y completa tus credenciales reales:
   ```bash
   cp .env.example .env
   ```
   > ⚠️ **Seguridad:** El archivo `.env` está expresamente excluido de Git en `.gitignore` para proteger tus credenciales.

### 3. Ejecutar la Aplicación

```bash
streamlit run app.py
```
Abre en tu navegador la URL: `http://localhost:8501`.

### 4. Ejecución con Docker

```bash
docker compose up --build
```

---

## 🧪 Pruebas Automatizadas

Para ejecutar la suite completa de pruebas unitarias:

```bash
pytest -v
```

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
