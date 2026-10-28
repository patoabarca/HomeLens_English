# HomeLens English 🔍🇬🇧

Asistente educativo inteligente para el aprendizaje contextual del idioma inglés a partir de la exploración visual de objetos cotidianos en el hogar, impulsado por visión multimodal (Google Gemini), actividades interactivas, desafíos *Find It* y síntesis de voz (TTS).

---

## 📌 Repositorio y Entorno
- **Repositorio Remoto:** [https://github.com/patoabarca/HomeLens_English](https://github.com/patoabarca/HomeLens_English)
- **Tipo de Repositorio:** Privado
- **Rama Actual:** `main` (Integración M1 a M4: Autenticación Supabase/Google y Exploración Visual con Gemini)

---

## 🏛️ Arquitectura Modular (M0 a M8)

El sistema implementa una arquitectura modular con contratos estrictos y bajo acoplamiento:

| Módulo | Nombre | Responsabilidad |
| :--- | :--- | :--- |
| **M0** | **Configuración y Entorno** | Carga segura de variables de entorno sin exposición de credenciales y registro de eventos técnicos (`config.py`, `telemetria.py`). |
| **M1** | **Acceso de Usuarios** | Autenticación real con Google OAuth 2.0 vía Supabase Auth, flujo PKCE con protección CSRF, sesiones verificadas, identidad estable inmutable (`ContextoUsuario`) y bloqueo de operaciones protegidas (`acceso.py`, `integraciones/autenticacion.py`, `ui/acceso.py`). |
| **M2** | **Captura y Preparación** | Validación de formatos reales (JPEG/PNG), límites de tamaño, corrección EXIF y gestión en memoria sin persistencia de fotos (`imagenes.py`, `ui/captura.py`). |
| **M3** | **Análisis con Gemini** | Detección multimodal de objetos, normalización geométrica `[ymin, xmin, ymax, xmax]`, esquemas estructurados y generación de actividades formativas (`analisis.py`, `integraciones/gemini.py`). |
| **M4** | **Exploración y Contenido** | Adaptación de coordenadas a la pantalla y generación de tarjetas pedagógicas (`exploracion.py`, `ui/exploracion.py`). |
| **M5** | **Audio y Pronunciación** | Síntesis de voz con Google Cloud TTS y caché temporal de sesión (`audio.py`). |
| **M6** | **Prácticas y Find It** | Evaluación local de cuestionarios y verificación de desafíos (`practicas.py`). |
| **M7** | **Persistencia e Historial** | Contratos de persistencia atómica y aislamiento de datos por usuario (`datos/repositorio.py`). |
| **M8** | **Progreso y Analítica** | Consolidación y cálculo del estado de vocabulario aprendido (`progreso.py`). |

---

## 🔐 M1: Acceso de Usuarios y Autenticación con Google (Parte 5)

El módulo **M1** (`homelens/acceso.py`, `homelens/integraciones/autenticacion.py` y `homelens/ui/acceso.py`) implementa un sistema de autenticación real y seguro con **Google OAuth 2.0 a través de Supabase Auth**, garantizando la identidad del usuario y protegiendo todas las operaciones pedagógicas y de análisis de la aplicación:

### 1. Flujo OAuth 2.0 con PKCE y Protección CSRF
- **Inicio de sesión:** Al pulsar el botón **"Continuar con Google"**, el adaptador genera un par criptográfico PKCE (`code_verifier` y `code_challenge` con SHA-256) y un parámetro de estado criptográfico de alta entropía (`state`, 32 bytes) para mitigar ataques CSRF.
- **Redirección controlada:** Se construye la URL de autorización de Supabase (`sign_in_with_oauth`) configurando a Google como proveedor externo y `AUTH_REDIRECT_URL` como URL de retorno autorizada.
- **Retorno e intercambio seguro:** Google redirige al usuario a la aplicación con los parámetros de consulta `?code=...&state=...`. La aplicación valida que el `state` coincida con el generado previamente, recupera el `code_verifier` asociado y ejecuta el intercambio del código por tokens de sesión (`exchange_code_for_session`).
- **Saneamiento inmediato de URL:** Tras procesar el código o detectar errores, los parámetros de consulta (`st.query_params`) se limpian inmediatamente de la barra de direcciones del navegador para evitar la fuga de credenciales o códigos sensibles en el historial o cabeceras `Referer`.

### 2. Identidad Estable y Verificada (`ContextoUsuario`)
- **Identificador inmutable:** La identidad del usuario se deriva directamente del `user.id` persistente provisto por Supabase Auth (UUID v4 inmutable por cuenta de Google).
- **Contrato de dominio:** Se construye `ContextoUsuario(user_id=UUID, sesion_id=str, email=..., nombre=...)`, garantizando que el mismo usuario siempre mantenga su identidad a lo largo de recargas y futuras consultas.
- **Sin manipulación externa:** La identidad no puede ser falsificada mediante parámetros de consulta o encabezados modificables desde el navegador del cliente.

### 3. Verificación Activa y Control de Operaciones Protegidas
- **Protección a nivel de dominio:** Operaciones protegidas como `analizar_exploracion` en `homelens/analisis.py` validan activamente la presencia y legitimidad del `ContextoUsuario`. Si el usuario no está autenticado o la identidad no es válida, la ejecución se rechaza inmediatamente con `CODIGO_SESION_REQUERIDA`.
- **Protección a nivel de interfaz:** Si no existe una sesión válida, Streamlit bloquea la navegación, oculta los paneles de exploración/captura y muestra exclusivamente la pantalla de acceso.
- **Renovación automática:** Durante las recargas, se comprueba la validez del token de acceso (`get_user`). Si ha expirado, se intenta la renovación segura con el refresh token (`refresh_session`). Si la sesión fue revocada o expiró definitivamente, se bloquea el acceso con `CODIGO_SESION_EXPIRADA`.

### 4. Cierre de Sesión Seguro y Limpieza Profunda
El botón **"Cerrar sesión"** (disponible en la barra lateral y perfiles) ejecuta una invalidación integral:
1. **Revocación remota:** Invoca `auth.sign_out()` en Supabase para invalidar la sesión activa del proveedor.
2. **Eliminación de referencias locales:** Borra tokens, credenciales y el `ContextoUsuario` de la memoria del servidor.
3. **Liberación de imágenes y datos temporales:** Ejecuta `limpiar_datos_exploracion()` y `liberar_imagen()`, liberando buffers de fotos, recuadros en pantalla y selecciones.
4. **Invalidación de widgets de UI:** Incrementa los identificadores de versión de widgets (`uploader_key`, `camera_key`) para descartar archivos cargados en el DOM del navegador.
5. **Redirección inmediata:** Reinicia el ciclo de ejecución de Streamlit redirigiendo a la pantalla de bienvenida y login.

### 5. Separación Estricta entre Modo Real y Demostración Local
- **Sin fallback silencioso:** Ante fallos de conexión, indisponibilidad de Supabase o credenciales erróneas, el sistema **nunca** conmuta silenciosamente a un usuario simulado. Informa el error de forma clara (`CODIGO_PROVEEDOR_AUTH_ERROR`).
- **Demostración explícita:** El modo demo (`ALLOW_DEMO_LOGIN=true` y `AUTH_REQUIRED=false`) está claramente señalizado (`es_demo=True`), limitado a entornos de desarrollo y no permite acceso a cuentas reales ni datos privados ajenos.

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

### 1. Modelo Seleccionado y Biblioteca Oficial
- **Biblioteca Oficial:** `google-genai` (v1.29.0+), reemplazando a la biblioteca obsoleta `google-generativeai`.
- **Modelo:** `gemini-2.5-flash` / `gemini-1.5-flash` (configurable mediante la variable `GEMINI_MODEL`, por defecto `gemini-2.5-flash`).
- **Verificación oficial:** Soporte nativo de visión multimodal y salida estructurada JSON (`response_schema=RespuestaExploracionIA`).
- **Ventajas:** Latencia mínima, alta velocidad de inferencia, bajo costo operativo y precisión en la detección de objetos y generación bilingüe (EN/ES) de nivel A1/A2.
- **Configuración de Resiliencia:** `GEMINI_TIMEOUT_SECONDS` (60.0s provisional) y `GEMINI_MAX_RETRIES` (1 reintento para fallos transitorios 5xx/red exclusivamente).

### 2. Contrato de Entrada y Salida
```python
analizar_exploracion(
    usuario: ContextoUsuario,
    imagen: ImagenPreparada,
    operacion_id: UUID,
    adaptador: Optional[AdaptadorGemini] = None,
) -> Resultado[Exploracion]
```

### 3. Principios y Validaciones Estrictas Endurecidas
- **Una llamada atómica por exploración:** Obtiene en un solo paso el estado del análisis, los objetos detectados (1 a 5), recuadros normalizados `[0, 1000]`, traducciones, frases de ejemplo y cuestionarios interactivos de 3 opciones (1 a 2 actividades).
- **Defensa contra Prompt Injection:** El prompt explicita que la imagen y cualquier texto visible en ella son contenido a analizar y no instrucciones de control.
- **Validación exhaustiva de estados y coherencia:**
  - Solo se aceptan los estados previstos (`UTILIZABLE`, `SIN_OBJETOS_CLAROS`, `REPETIR_CAPTURA`). Cualquier otro estado produce `CODIGO_RESPUESTA_INVALIDA`.
  - `UTILIZABLE` exige entre 1 y 5 objetos y entre 1 y 2 actividades pedagógicas.
  - `SIN_OBJETOS_CLAROS` y `REPETIR_CAPTURA` exigen listas vacías de objetos y actividades. Se rechazan combinaciones inconsistentes.
- **Validación de identificadores:** Exige `id_local` no vacío y estrictamente único dentro de la respuesta para objetos y actividades (no se inventan identificadores).
- **Validación geométrica exhaustiva:**
  - Exige coordenadas enteras normalizadas (`0 <= ymin, xmin, ymax, xmax <= 1000`).
  - Rechaza tipos booleanos o no enteros (`type(coord) is not bool and isinstance(coord, int)`).
  - Exige `ymin < ymax` y `xmin < xmax` (rechazando recuadros invertidos o de área nula).
  - *Nota:* La validación geométrica garantiza coherencia numérica y estructural, pero no garantiza por sí sola la precisión visual o semántica del modelo.
- **Integridad y referencias de actividades:**
  - Cada actividad debe referenciar al menos un `id_local` de objeto devuelto en la misma respuesta.
  - Se rechazan referencias a objetos inexistentes o referencias duplicadas dentro de la misma actividad (se eliminó cualquier asociación automática fallback al primer objeto).
  - Exige exactamente 3 opciones por actividad, con identificadores y textos únicos y no vacíos.
  - La opción correcta (`opcion_correcta_id`) debe pertenecer obligatoriamente a las 3 opciones provistas.
- **Aclaración sobre visualización de recuadros:** La renderización interactiva y visual de los recuadros delimitadores sobre la fotografía en pantalla corresponde a la **Tarea 6**. La imagen preparada se mantiene en memoria en la sesión para permitir dicha visualización posterior.
- **Mapeo a entidades inmutables:** Traduce identificadores locales de IA a `UUID` inmutables del dominio, asignando la autoría al `ContextoUsuario`.
- **Manejo diferenciado de errores:** Clasifica errores de cuota (`429 / LIMITE_ALCANZADO`), credenciales (`401/403 / ACCESO_DENEGADO`), tiempos de espera (`TIEMPO_AGOTADO`), respuestas bloqueadas/inválidas (`RESPUESTA_INVALIDA`) y fallos temporales de red (`SERVICIO_NO_DISPONIBLE`), sin exponer secretos ni registrar imágenes.
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
├── pyproject.toml              # Metadatos del paquete y dependencias (google-genai>=1.29.0)
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
│   │   ├── gemini.py           # M3: Adaptador del SDK google-genai
│   │   └── tts.py              # Cliente Google Cloud TTS
│   │
│   ├── prompts/                # Plantillas versionadas de prompts
│   │   ├── exploracion.txt     # M3: Prompt pedagógico y multimodal
│   │   └── find_it.txt
│   │
│   └── ui/                     # Componentes y estado de interfaz Streamlit
│       ├── __init__.py
│       ├── estado.py           # Estado de sesión y ciclo de vida de imágenes
│       ├── acceso.py           # M1: Pantalla y controles de autenticación Google / Demo
│       ├── captura.py          # M2/M3: Pantalla de captura y prueba manual
│       └── exploracion.py      # M4: Visualización de recuadros y tarjetas pedagógicas
│
└── tests/                      # Suite de pruebas automatizadas
    ├── __init__.py
    ├── test_acceso.py          # Cobertura exhaustiva de autenticación y seguridad M1
    ├── test_ui_acceso.py       # Pruebas de integración de UI con AppTest (M1)
    ├── test_modelos.py         # Invariantes y entidades del dominio
    ├── test_config.py          # Validación segura de entorno M0
    ├── test_imagenes.py        # Cobertura exhaustiva de validación M2
    ├── test_analisis.py        # Cobertura exhaustiva de validación, esquemas y simulación M3
    ├── test_exploracion.py     # Proyecciones de pantalla y tarjetas M4
    ├── test_estado_ui.py       # Estado de interfaz y transiciones M4
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

### Pruebas Automatizadas Unitarias (82 tests - 100% aisladas)
Ejecuta la suite con:
```bash
python -m unittest discover -s tests -v
```
o con pytest:
```bash
python -m pytest -v
```

**Cobertura automatizada (sin consumo de API ni credenciales externas):**
- ✅ **M0 Configuración:** Carga segura, defaults, timeout y reintentos.
- ✅ **M1 Acceso y Autenticación con Google (12 tests unitarios y de UI):**
  - **Bloqueo sin sesión:** Operaciones protegidas (`analizar_exploracion`) y pantallas principales bloqueadas con `CODIGO_SESION_REQUERIDA` si el usuario no está autenticado.
  - **Acceso autorizado:** Verificación de firma/tokens y emisión de `ContextoUsuario` completo.
  - **Identidad estable:** El identificador `user_id: UUID` permanece idéntico en recargas y nuevas consultas para la misma cuenta.
  - **Sesión expirada o revocada:** Manejo controlado con `CODIGO_SESION_EXPIRADA` forzando reingreso sin exponer excepciones.
  - **Cierre de sesión integral:** Revocación remota, eliminación de credenciales locales, liberación de imágenes en memoria (`liberar_imagen`), descarte de exploraciones y reseteo de widgets.
  - **Error del proveedor:** Captura de respuestas de error OAuth con mensajes comprensibles y sin accesos espurios (`CODIGO_PROVEEDOR_AUTH_ERROR`).
  - **Ausencia de configuración:** Comportamiento seguro sin conmutación silenciosa a sesiones falsas cuando `AUTH_REQUIRED=true`.
  - **Aislamiento en cambio de usuario:** El ingreso de un segundo usuario descarta completamente los datos y recuadros del anterior.
  - **Protección CSRF y manipulación:** Rechazo estricto de parámetros de estado inválidos, códigos reutilizados o identidades adulteradas.
  - **Intercambio PKCE:** Generación y validación de `code_verifier` y `code_challenge`.
  - **Integración de UI con AppTest:** Verificación de bloqueo de rutas, renderizado de botón Google y flujo interactivo de cierre de sesión.
- ✅ **M2 Captura e Imágenes:** Validación JPEG/PNG, límites de tamaño, orientación EXIF, canales alfa, coherencia de dimensiones y liberación de recursos.
- ✅ **M3 Análisis Gemini (Simulado & Esquemas):**
  - Construcción y validación del esquema Pydantic nativo con el SDK `google-genai` sin llamadas de red.
  - Análisis exitoso con 1 y múltiples objetos educativos (1 a 5).
  - Resultados válidos de estados `SIN_OBJETOS_CLAROS` y `REPETIR_CAPTURA` sin contenido.
  - Rechazo estricto de estados desconocidos e inconsistencias (ej. `SIN_OBJETOS_CLAROS` con objetos, o `UTILIZABLE` sin objetos).
  - Rechazo estricto de identificadores `id_local` de objetos y actividades vacíos o duplicados (sin fallbacks inventados).
  - Rechazo de coordenadas fuera de rango (`> 1000` o `< 0`), invertidas (`ymin >= ymax`, `xmin >= xmax`), de área nula o tipos booleanos/no enteros.
  - Rechazo de exploraciones utilizables sin actividades (exige 1 a 2 actividades).
  - Rechazo de actividades sin referencias a objetos, referencias duplicadas o referencias a objetos inexistentes (sin asignación automática al primer objeto).
  - Rechazo de preguntas con opciones insuficientes/excesivas (exige exactamente 3) o solución no existente en las opciones.
  - Manejo controlado de respuestas vacías, bloqueadas por seguridad, truncadas o con JSON inválido.
  - Manejo controlado y mapeo de errores del SDK (cuota 429, timeout, credenciales inválidas 401/403, 400 y caídas transitorias de servicio 5xx).
  - Verificación de reintentos: solo ante errores transitorios 5xx/red, nunca ante credenciales o esquemas inválidos.
  - Comportamiento seguro de `AdaptadorGemini` sin credenciales y con cliente simulado (`mock_client`).
  - Ocultamiento de soluciones en `obtener_actividades_publicas`.
- ✅ **M4 Exploración y Contenido (Tarea 6):**
  - **Conversión geométrica exacta:** Normalización en escala 0–1000 mapeada a los píxeles reales de la imagen orientada (`izquierda = xmin/1000 * ancho`, `arriba = ymin/1000 * alto`, etc.).
  - **Superposición gráfica in-memory (Pillow):** Dibujado de recuadros con paleta accesible de alto contraste y etiquetas numéricas legibles (`#1`, `#2`...) que respetan los márgenes visibles de la pantalla.
  - **Selección e interactividad:** Destacado visual del objeto seleccionado (mayor grosor, relleno translúcido y acento en tarjeta) y opción para visualizar todos los objetos, sin llamadas adicionales al modelo ni desajustes por redimensionado.
  - **Tarjetas pedagógicas claras:** Vocabulario (inglés/español) y frases contextuales para nivel inicial, sin exponer UUIDs, metadatos internos ni detalles del proveedor.
  - **Gestión y coherencia de estado:** Persistencia de resultados tras reruns de Streamlit, vinculación estricta entre la imagen activa y la exploración, e invalidación automática al descartar o cambiar la imagen.
  - **Limpieza centralizada para Tarea 5:** Función reutilizable `limpiar_datos_exploracion()` integrada con el cierre de sesión, expiración y cambio de usuario de Lucas.
  - **Aclaración evaluativa (M9):** Los recuadros visualizados corresponden a la localización estimada por Gemini multimodal; su precisión real debe ser objeto de auditoría visual en el anexo de evaluación M9.
- ✅ **M8 Progreso:** Invariantes de dominio, cálculos puros de estadísticas y tarjetas.

---

## ⚙️ Guía de Configuración: Supabase Auth y Google OAuth

Para utilizar la autenticación real en entornos de desarrollo y producción:

### 1. Configurar Credenciales en Google Cloud Console
1. Accede a [Google Cloud Console](https://console.cloud.google.com/) y crea un proyecto (o selecciona uno existente).
2. Dirígete a **APIs & Services** > **OAuth consent screen**:
   - Tipo de usuario: **External**.
   - Completa el nombre de la app (*HomeLens English*), correo de soporte y datos de contacto.
   - En **Scopes**, añade `.../auth/userinfo.email` y `.../auth/userinfo.profile`.
3. Ve a **Credentials** > **Create Credentials** > **OAuth client ID**:
   - Application type: **Web application**.
   - Name: *HomeLens English Supabase Auth*.
   - En **Authorized redirect URIs**, agrega la URL provista por Supabase:
     ```text
     https://<TU-PROJECT-REF>.supabase.co/auth/v1/callback
     ```
4. Guarda el **Client ID** y el **Client Secret** generados.

### 2. Configurar el Proveedor en el Panel de Supabase
1. Ingresa a tu proyecto en [Supabase Dashboard](https://supabase.com/dashboard).
2. Ve a **Authentication** > **Providers** > **Google**:
   - Activa el interruptor **Enable Google provider**.
   - Pega el **Client ID** y **Client Secret** obtenidos de Google Cloud.
   - Guarda los cambios.
3. Ve a **Authentication** > **URL Configuration**:
   - En **Site URL**, define la URL base de tu aplicación: `http://localhost:8501` (o tu dominio de producción).
   - En **Redirect URLs**, añade:
     ```text
     http://localhost:8501
     http://localhost:8501/
     ```

### 3. Configurar `.env` Local
En tu archivo `.env` local, define:
```env
# Supabase Auth
SUPABASE_URL=https://<TU-PROJECT-REF>.supabase.co
SUPABASE_KEY=<TU_SUPABASE_ANON_KEY>
AUTH_REDIRECT_URL=http://localhost:8501
AUTH_REQUIRED=true
ALLOW_DEMO_LOGIN=false
```
> ⚠️ **Seguridad:** Usa únicamente la clave **anon / public**. Nunca configures `SUPABASE_SERVICE_ROLE_KEY` en la aplicación cliente.

---

## 👥 Procedimiento de Validación Manual con Dos Cuentas de Google

Una vez configuradas las credenciales de Supabase y Google, sigue estos pasos para verificar el flujo de extremo a extremo:

1. **Ingreso con Cuenta A:**
   - Inicia la aplicación con `streamlit run app.py`.
   - Se presentará la pantalla de bienvenida con el botón **"Continuar con Google"**.
   - Haz clic en el botón. Serás redirigido a la pantalla de consentimiento de Google.
   - Selecciona la **Cuenta A** de Google y autoriza el acceso.
   - Serás redirigido a `http://localhost:8501`. La URL se limpiará automáticamente.
   - Comprueba que en la barra lateral se visualice el nombre y correo de la Cuenta A, y el estado `🟢 Conectado con Google`.
2. **Operación protegida con Cuenta A:**
   - En la sección **Exploración Visual**, carga una fotografía y presiona **Preparar Imagen**.
   - Presiona **Analizar Fotografía con IA**. La exploración se completará vinculada a la Cuenta A.
3. **Persistencia tras recarga:**
   - Recarga la página en el navegador (`F5` o `Ctrl+R`).
   - Verifica que la sesión se mantenga activa sin solicitar reautenticación y que los datos en memoria sigan accesibles.
4. **Cierre de sesión:**
   - Pulsa **"Cerrar sesión"** en la barra lateral.
   - Comprueba que la sesión se cierre inmediatamente, las fotos y recuadros desaparezcan y se regrese a la pantalla de acceso.
5. **Ingreso con Cuenta B:**
   - Haz clic nuevamente en **"Continuar con Google"**.
   - Selecciona una segunda cuenta de Google diferente (**Cuenta B**).
   - Verifica que la aplicación muestre la nueva identidad (nombre, correo y UUID distinto).
   - **Comprobación de aislamiento:** Verifica que no quede ningún rastro, foto o recuadro perteneciente a la Cuenta A.
6. **Validación de expiración:**
   - Revoca la sesión desde el panel de Supabase o simula un token caducado.
   - Al recargar, comprueba que la aplicación muestre el mensaje `Tu sesión ha expirado. Por favor, ingresa nuevamente` y bloquee el acceso a la exploración.

---

### Prueba Manual en Vivo con Gemini (Acción Explícita)
1. Configura tu clave en `.env`: `GEMINI_API_KEY=tu_api_key_aqui`
2. Opcionalmente ajusta el modelo en `.env`: `GEMINI_MODEL=gemini-2.5-flash`
3. Inicia la aplicación con `streamlit run app.py` (o abre `http://localhost:8501`).
4. En el panel de **Exploración Visual**, toma una foto con la cámara o carga un archivo JPG/PNG.
5. Presiona **"⚙️ Preparar Imagen"** para que el módulo M2 procese la imagen en memoria.
6. Haz clic en el botón **"🔍 Analizar Fotografía con IA"**.
7. Verifica la visualización de la fotografía con sus recuadros delimitadores y etiquetas numéricas, los controles táctiles de selección/enfoque y las tarjetas educativas de vocabulario.
8. Si se produce un error o la imagen no contiene objetos claros, comprueba que se muestre un mensaje pedagógico claro y que no se mantenga un resultado anterior desactualizado.

---

## 💡 Funcionamiento del Modo Demostración

En el modo demostración (`ALLOW_DEMO_LOGIN=true` y `AUTH_REQUIRED=false`):
- ✅ **Carga segura de configuración:** El sistema reporta el estado de cada servicio en la barra lateral sin fallar.
- ✅ **Acceso simulado explícito:** Se ofrece un botón secundario claramente diferenciado (`👤 Ingresar en Modo Demo`) que genera un contexto de prueba (`es_demo=True`).
- 🛑 **Sin conmutación silenciosa:** Si `AUTH_REQUIRED=true` y falla Supabase, el acceso se bloquea con un error informativo sin pasar a demo.
- 🟡 **Persistencia separada:** Las pruebas demo no se mezclan con usuarios reales.

---

## 📋 Estado de Implementación

- [x] Repositorio Git local y sincronización remota en rama `main`.
- [x] Exclusión de credenciales asegurada con `.gitignore` previo y `.env.example`.
- [x] Modelos de dominio compartidos (`homelens/modelos.py`) con validaciones e invariantes.
- [x] Sistema de manejo de errores controlado (`homelens/errores.py`) con `Resultado[T]`.
- [x] Módulo M0 (`config.py`, `telemetria.py`) para arranque seguro de la aplicación.
- [x] Módulo M1 (`acceso.py`, `integraciones/autenticacion.py`, `ui/acceso.py`) con autenticación Google OAuth real vía Supabase Auth, flujo PKCE, protección CSRF y bloqueo de operaciones protegidas (Parte 5).
- [x] Módulo M2 (`imagenes.py`, `ui/captura.py`) con validación y orientación de imágenes.
- [x] Módulo M3 (`analisis.py`, `integraciones/gemini.py`, `esquemas_ia.py`, `prompts/exploracion.txt`) migrado a `google-genai` con validación estricta.
- [x] Módulo M4 (`exploracion.py`, `ui/exploracion.py`) con recuadros visuales sobre fotografía, selección interactiva y tarjetas pedagógicas (Tarea 6).
- [x] Módulo M8 (`progreso.py`) con cálculo puro de palabras y estadísticas.
- [x] Entorno de contenedorización (`Dockerfile`, `compose.yaml`, `.dockerignore`).
- [x] Suite de 82 pruebas automatizadas con 100% de éxito.

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
