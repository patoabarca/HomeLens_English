@echo off
setlocal
title HomeLens English - localhost:8501
cd /d "%~dp0" || goto error
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto deps
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto error
:deps
"%PY%" -c "import streamlit, google.genai, pydantic, dotenv, PIL, supabase" >nul 2>nul
if errorlevel 1 (
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto error
)
"%PY%" -c "import psutil" >nul 2>nul
if errorlevel 1 (
    "%PY%" -m pip install psutil
    if errorlevel 1 goto error
)
"%PY%" -c "from pathlib import Path; import sys; exec(Path(sys.argv[1]).read_text(encoding='ascii').split('\n# LAUNCHER_PYTHON\n',1)[1])" "%~f0"
if errorlevel 1 goto error
set "AUTH_REDIRECT_URL=http://localhost:8501"
"%PY%" -m streamlit run app.py --server.address localhost --server.port 8501 --browser.serverAddress localhost --browser.serverPort 8501 --server.headless false
if errorlevel 1 goto error
exit /b 0
:error
echo [ERROR] No se pudo iniciar HomeLens en localhost:8501.
pause
exit /b 1

# LAUNCHER_PYTHON
import os
import socket
import time
import subprocess
import shutil
import psutil

root = Path.cwd()
app = (root / 'app.py').resolve()
if not app.is_file():
    sys.exit('Falta app.py junto a iniciar.bat.')

def runs_this_app(proc):
    args = proc.cmdline()
    for idx, arg in enumerate(args[:-1]):
        if arg.lower() != 'run' or idx == 0:
            continue
        if Path(args[idx-1]).stem.lower() != 'streamlit':
            continue
        if (Path(proc.cwd()) / args[idx+1]).resolve() == app:
            return True
    return False

stopping = []
for proc in psutil.process_iter(['name']):
    if (proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe', 'streamlit.exe'):
        continue
    try:
        if runs_this_app(proc):
            print('Cerrando HomeLens anterior, PID', proc.pid, flush=True)
            proc.terminate()
            stopping.append(proc)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        continue
psutil.wait_procs(stopping, timeout=5)

if shutil.which('docker'):
    try:
        result = subprocess.run(['docker', 'compose', 'ps', '-q', 'app'], capture_output=True, text=True, timeout=8)
        for container in result.stdout.splitlines():
            if result.returncode or not container.strip():
                continue
            ports = subprocess.run(['docker', 'port', container.strip()], capture_output=True, text=True, timeout=8)
            if any(line.strip().endswith(':8501') for line in ports.stdout.splitlines()):
                print('Deteniendo el contenedor de HomeLens que publica 8501.', flush=True)
                subprocess.run(['docker', 'stop', container.strip()], check=True, timeout=30)
    except subprocess.TimeoutExpired:
        print('Docker no respondio a tiempo. Comprobando el puerto local.')

for attempt in range(20):
    try:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(('127.0.0.1', 8501))
        break
    except OSError:
        time.sleep(0.25)
else:
    sys.exit('El puerto 8501 sigue ocupado. Revise el programa que lo usa.')
