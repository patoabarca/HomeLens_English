@echo off
setlocal
title HomeLens English - Launcher

cd /d "%~dp0"

echo ========================================================
echo            Iniciando HomeLens English
echo ========================================================
echo.

:: 1. Verificar si Python esta instalado en el sistema
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el sistema.
    echo Por favor instala Python 3.10 o superior y asegurate de marcar
    echo "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

:: 2. Verificar si el entorno virtual .venv existe
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creando entorno virtual .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado exitosamente.
    echo.
)

:: 3. Activar el entorno virtual
call ".venv\Scripts\activate.bat"

:: 4. Verificar si las dependencias estan instaladas
python -c "import streamlit, google.genai, pydantic, dotenv, PIL, supabase" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias desde requirements.txt...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Hubo un problema al instalar las dependencias.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas correctamente.
    echo.
) else (
    echo [OK] Dependencias verificadas y listas.
)

:: 5. Iniciar la aplicacion con Streamlit
echo.
echo ========================================================
echo   Ejecutando HomeLens English...
echo   Presiona Ctrl + C en esta ventana para detener.
echo ========================================================
echo.

streamlit run app.py

if errorlevel 1 (
    echo.
    echo [AVISO] La aplicacion se detuvo.
    pause
)
