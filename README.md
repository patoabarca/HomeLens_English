# HomeLens English

Aplicación educativa para practicar inglés a partir de fotografías del hogar. Identifica objetos con Gemini, muestra nombres y frases en inglés y español, ofrece pronunciación y cuestionarios, y permite guardar el contenido para repasarlo.

Proyecto de Patricia Abarca, Lucas Centurión y Victoria Magliano.

Utilizamos Gemini como modelo multimodal preentrenado. No entrenamos una red neuronal propia. Las imágenes anotadas se destinan a evaluar el sistema.

## Funciones y estado

Estado revisado el 13 de noviembre de 2026 sobre `main` (`4d3714e`).

| Función | Estado |
| --- | --- |
| Ingreso con Google mediante Supabase Auth | Integrado |
| Carga o captura de fotografías JPEG/PNG y preparación de imagen | Integrado |
| Análisis con Gemini y validación de la respuesta | Integrado |
| Recuadros, selección de objetos y tarjetas bilingües EN · US / ES | Integrado |
| Pronunciación de palabras y frases a pedido | Integrado |
| Cuestionarios con corrección local y explicación | Integrado |
| Guardado y recuperación del contenido educativo | Integrado |
| Desafíos Find It | Parcial: falta completar el recorrido en la interfaz |
| Mi Progreso | Parcial: existe lógica de cálculo; la pantalla y la integración están pendientes |
| Evaluación del sistema | Desarrollada en la rama `HLE_Evaluacion`, separada de `main` |

Las frases pueden escucharse a velocidad normal (1,0×), lenta (0,8×, predeterminada) o muy lenta (0,65×). Las palabras se reproducen a velocidad normal.

## Recorrido de uso

1. Ingresar con Google.
2. Cargar una fotografía o tomarla con la cámara. El límite predeterminado es de 10 MB.
3. Preparar la imagen y solicitar el análisis con Gemini.
4. Explorar los recuadros y las tarjetas con vocabulario y frases.
5. Escuchar la pronunciación o resolver los cuestionarios.
6. Pulsar **Guardar** para conservar el contenido y recuperarlo desde el historial.

El guardado es una acción del usuario. Recuperar una exploración no vuelve a analizarla con Gemini. La fotografía original no se recupera porque no se guarda en el historial.

## Tecnologías y organización

Python contiene la lógica y Streamlit construye la interfaz. Pillow prepara imágenes; Gemini analiza la escena; Pydantic valida los datos recibidos; Supabase aporta autenticación y persistencia sobre PostgreSQL; Google Cloud Text-to-Speech (TTS) genera la voz. Docker permite ejecutar la aplicación en un contenedor.

| Módulo | Responsabilidad |
| --- | --- |
| M0 | Configuración y eventos técnicos |
| M1 | Acceso y sesiones |
| M2 | Captura y preparación de imágenes |
| M3 | Análisis con Gemini y validaciones |
| M4 | Exploración visual y tarjetas educativas |
| M5 | Pronunciación y caché temporal de audio |
| M6 | Cuestionarios y lógica de desafíos |
| M7 | Guardado e historial |
| M8 | Lógica de progreso |

El código se organiza en `homelens/`, con componentes de interfaz en `homelens/ui/`, adaptadores de proveedores en `homelens/integraciones/`, persistencia en `homelens/datos/` y prompts en `homelens/prompts/`. Las pruebas están en `tests/`.

## Preparación del entorno

Se necesita Git y Python 3.10 o superior para la instalación local. La imagen Docker utiliza Python 3.11. Las integraciones reales requieren conexión a internet y servicios configurados.

Clonar el repositorio y entrar en su carpeta:

```bash
git clone https://github.com/patoabarca/HomeLens_English.git
cd HomeLens_English
```

Crear `.env` a partir de [.env.example](.env.example), si todavía no existe:

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux, macOS o Git Bash
cp .env.example .env
```

### Servicios reales

Completar en `.env`:

```dotenv
APP_ENV=development
GEMINI_API_KEY=tu_clave_gemini
GEMINI_MODEL=gemini-2.5-flash
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_ANON_KEY=tu_clave_anon
AUTH_REDIRECT_URL=http://localhost:8501
AUTH_REQUIRED=true
ALLOW_DEMO_LOGIN=false
```

`GEMINI_MODEL` es configurable. `gemini-2.5-flash` es el valor predeterminado del código revisado; el modelo efectivo depende del entorno y del acceso del proyecto de Google.

Para configurar el acceso y el historial:

1. Crear un cliente OAuth web en Google y registrar como retorno el callback de Supabase: `https://tu-proyecto.supabase.co/auth/v1/callback`.
2. Habilitar el proveedor Google en Supabase Auth y cargar allí el Client ID y el Client Secret de Google.
3. Registrar la URL de la aplicación en la configuración de URLs de Supabase. Debe coincidir con `AUTH_REDIRECT_URL`, incluido el puerto.
4. Si el consentimiento de Google está en modo de prueba, incluir las cuentas que utilizarán la aplicación entre los usuarios de prueba.
5. Para habilitar el historial en un proyecto nuevo, revisar y aplicar [la migración SQL](sql/migracion_tarea_7_historial.sql) desde el administrador de Supabase. Crea la tabla y sus políticas de acceso.

La variable que lee la aplicación es **`SUPABASE_ANON_KEY`**, no `SUPABASE_KEY`. No utilizar una clave `service_role` para reemplazar la sesión del usuario.

Para la voz, configurar Google Cloud Text-to-Speech y sus credenciales. Una opción es definir `GOOGLE_APPLICATION_CREDENTIALS` con la ruta al archivo de credenciales. En Docker, ese archivo debe estar disponible dentro del contenedor mediante un montaje de solo lectura y la variable debe apuntar a la ruta interna. El `compose.yaml` actual no incluye ese montaje.

Mantener `.env` y las credenciales fuera de los archivos publicados en Git. Los secretos OAuth de Google se configuran en Supabase, no en el README.

### Acceso de demostración local

Para habilitar el ingreso con un usuario de prueba sin autenticación real, usar:

```dotenv
APP_ENV=development
AUTH_REQUIRED=false
ALLOW_DEMO_LOGIN=true
```

Copiar `.env.example` por sí solo **no activa la demostración**: sus valores predeterminados exigen autenticación y deshabilitan el acceso demo. Este modo simula el usuario; no reemplaza automáticamente el análisis de Gemini ni la síntesis de voz por resultados simulados. Esos servicios requieren su configuración para funcionar realmente.

## Ejecución local

Crear un entorno virtual:

```bash
python -m venv .venv
```

Activarlo con `.venv\Scripts\Activate.ps1` en PowerShell o `source .venv/bin/activate` en Linux/macOS. Luego instalar y ejecutar:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abrir [http://localhost:8501](http://localhost:8501).

Las dependencias declaran versiones mínimas en `requirements.txt`; no están fijadas a versiones exactas.

## Ejecución con Docker

Con Docker y Docker Compose v2 disponibles, y `.env` preparado:

```bash
docker compose up --build
```

Abrir [http://localhost:8501](http://localhost:8501). Para detener el servicio:

```bash
docker compose down
```

Si se cambia el puerto publicado, actualizar también la URL de retorno de autenticación y las URLs permitidas en Supabase. Cambiar `APP_PORT` por sí solo no modifica el mapeo `8501:8501` de Compose.

## Pruebas

Desde el entorno virtual con las dependencias instaladas:

```bash
python -m pytest -v
```

La suite cubre reglas, validaciones, estado de interfaz e integraciones con servicios simulados. Las verificaciones de proveedores reales se realizan por separado y necesitan configuración.

El [PR #6](https://github.com/patoabarca/HomeLens_English/pull/6) registra 178 pruebas aprobadas y la comprobación manual de las tres velocidades de audio. Es un registro de esa versión, no una medición de precisión de Gemini ni una nueva ejecución de la suite.

## Evaluación del sistema

El bloque A1–A4 está en [HLE_Evaluacion](https://github.com/patoabarca/HomeLens_English/tree/HLE_Evaluacion). Comprende preparación y validación del dataset, ejecución reproducible, métricas y revisión humana, e informe de resultados.

Según la documentación de esa rama, hay 30 imágenes sintéticas aceptadas y 541 anotaciones de referencia realizadas con CVAT. La nueva prueba técnica de tres imágenes está preparada, pero no ejecutada. La validación del dataset y las simulaciones no equivalen a resultados reales de Gemini.

La rama de evaluación tiene diferencias respecto de `main`; debe identificarse qué código y configuración se evalúan. Los resultados sobre imágenes sintéticas tampoco demuestran por sí solos el desempeño con fotografías reales ni mejoras en el aprendizaje.

- [Dataset y revisión](https://github.com/patoabarca/HomeLens_English/blob/HLE_Evaluacion/docs/evaluacion/ENTREGA_DATASET_EVALUACION_FINAL.md).
- [Protocolo y pendientes](https://github.com/patoabarca/HomeLens_English/blob/HLE_Evaluacion/docs/evaluacion/PROTOCOLO_EVALUACION_FINAL.md).

## Datos y límites

- La foto se conserva temporalmente en memoria y se envía a Gemini para analizarla; la aplicación no la guarda en el historial.
- Supabase conserva el contenido educativo cuando el usuario lo solicita. Las políticas RLS (seguridad a nivel de fila) restringen los registros por usuario.
- El historial presenta fecha y hora de Argentina (ART).
- El análisis devuelve hasta cinco objetos por imagen. La validación del formato y de las coordenadas no garantiza que la detección sea correcta.
- La voz se sintetiza a pedido; la aplicación no graba ni califica la pronunciación del usuario.

## Problemas frecuentes

| Situación | Qué revisar |
| --- | --- |
| No permite ingresar con Google | Variables `SUPABASE_URL` y `SUPABASE_ANON_KEY`, proveedor Google y URLs de retorno |
| El análisis no está disponible | Clave de Gemini, acceso al modelo, cuota y conectividad |
| El historial no guarda o no carga | Sesión real, migración aplicada y políticas de acceso de Supabase |
| No se genera audio | Servicio TTS, permisos y credenciales disponibles en el entorno de ejecución |
| El puerto 8501 está ocupado | Detener la otra instancia o cambiar el puerto y ajustar las URLs de autenticación |
| Docker no inicia | Docker en ejecución y archivo `.env` presente |

## Documentación adicional

- [Propuesta del proyecto](HomeLens_English_Propuesta.md).
- [Historias de usuario](HomeLens_English_Historias_de_usuario.md).
- [Requisitos y restricciones](HomeLens_English_Requisitos_y_restricciones.md).
- [Diseño de módulos](HomeLens_English_Modulos.md).
- [Audio bajo demanda](docs/TAREA8_AUDIO_BAJO_DEMANDA.md).

Los documentos de propuesta y diseño describen también funciones previstas. Para conocer el avance integrado, consultar la tabla de estado de este README y el código de la rama correspondiente.
