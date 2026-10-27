@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "PYTHON_EXE=%BACKEND_DIR%\aurora-env\Scripts\python.exe"
set "NEXT_EXE=%FRONTEND_DIR%\node_modules\.bin\next.cmd"

if /I "%~1"=="__backend" goto run_backend
if /I "%~1"=="__frontend" goto run_frontend
if /I "%~1"=="--help" goto show_help

title AURORA Launcher
cd /d "%PROJECT_ROOT%"

echo.
echo ============================================================
echo   AURORA - Multilingual RAG Platform
echo   Automatic local development launcher
echo ============================================================
echo.

if not exist "%PROJECT_ROOT%.env" (
    echo [WARNING] .env was not found. Application defaults will be used.
    echo           Provider-backed indexing and Google login need a configured .env.
    echo.
)

where docker.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker was not found in PATH.
    echo         Install Docker Desktop, then run this file again.
    goto launch_failed
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [WAIT] Docker is not running. Attempting to open Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "Docker Desktop" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else (
        echo [ERROR] Docker Desktop could not be located automatically.
        echo         Start Docker Desktop manually, then run this file again.
        goto launch_failed
    )

    for /L %%I in (1,1,60) do (
        docker info >nul 2>&1
        if not errorlevel 1 goto docker_ready
        timeout /t 2 /nobreak >nul
    )
    echo [ERROR] Docker did not become ready within two minutes.
    goto launch_failed
)

:docker_ready
echo [1/6] Starting PostgreSQL...
docker compose up -d db
if errorlevel 1 (
    echo [ERROR] PostgreSQL could not be started.
    goto launch_failed
)

set "DB_HEALTH="
for /L %%I in (1,1,30) do (
    for /F "delims=" %%H in ('docker inspect --format "{{.State.Health.Status}}" aurora-postgres 2^>nul') do set "DB_HEALTH=%%H"
    if /I "!DB_HEALTH!"=="healthy" goto database_ready
    timeout /t 2 /nobreak >nul
)
echo [ERROR] PostgreSQL did not report a healthy state within one minute.
goto launch_failed

:database_ready
echo [2/6] PostgreSQL is healthy.

if not exist "%PYTHON_EXE%" (
    echo [3/6] Creating the backend Python environment...
    where py.exe >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%BACKEND_DIR%\aurora-env"
    ) else (
        where python.exe >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Python 3 was not found in PATH.
            goto launch_failed
        )
        python -m venv "%BACKEND_DIR%\aurora-env"
    )
    if errorlevel 1 (
        echo [ERROR] The backend Python environment could not be created.
        goto launch_failed
    )
)

"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, docx, openpyxl, pptx" >nul 2>&1
if errorlevel 1 (
    echo [3/6] Installing backend dependencies...
    "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Backend dependencies could not be installed.
        goto launch_failed
    )
) else (
    echo [3/6] Backend environment is ready.
)

where node.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js was not found in PATH.
    echo         Install Node.js 20.9 or newer, then run this file again.
    goto launch_failed
)

if not exist "%NEXT_EXE%" (
    echo [4/6] Installing frontend dependencies...
    call :install_frontend
    if errorlevel 1 (
        echo [ERROR] Frontend dependencies could not be installed.
        echo         Install Node.js 20.9+ with Corepack or pnpm, then retry.
        goto launch_failed
    )
) else (
    echo [4/6] Frontend environment is ready.
)

echo [5/6] Applying database migrations...
pushd "%BACKEND_DIR%"
"%PYTHON_EXE%" -m alembic -c alembic.ini upgrade head
set "MIGRATION_RESULT=!errorlevel!"
popd
if not "!MIGRATION_RESULT!"=="0" (
    echo [ERROR] Database migrations failed. Servers were not started.
    goto launch_failed
)

echo [6/6] Starting application servers...
if /I not "%~1"=="--keep" (
    echo Stopping any existing servers on ports 8000 and 3000 to ensure fresh launch...
    call :kill_port 8000
    call :kill_port 3000
    timeout /t 1 /nobreak >nul
)

call :port_open 8000
if errorlevel 1 (
    echo Starting AURORA backend on http://127.0.0.1:8000 ...
    start "AURORA Backend" "%ComSpec%" /k call "%~f0" __backend
) else (
    echo [INFO] Port 8000 is active; existing backend was kept.
)

call :port_open 3000
if errorlevel 1 (
    echo Starting AURORA frontend on http://localhost:3000 ...
    start "AURORA Frontend" "%ComSpec%" /k call "%~f0" __frontend
) else (
    echo [INFO] Port 3000 is active; existing frontend was kept.
)

echo.
echo Waiting for backend at http://127.0.0.1:8000 ...
for /L %%I in (1,1,30) do (
    call :port_open 8000
    if not errorlevel 1 goto backend_ready
    timeout /t 1 /nobreak >nul
)
echo [WARNING] Backend is taking longer than expected to start.
:backend_ready

echo Waiting for frontend at http://localhost:3000 ...
for /L %%I in (1,1,45) do (
    call :port_open 3000
    if not errorlevel 1 goto frontend_ready
    timeout /t 1 /nobreak >nul
)
echo [WARNING] The frontend is still starting. Check the AURORA Frontend window.
goto launch_complete

:frontend_ready
echo [READY] AURORA is running. Opening Research Desk...
start "" "http://localhost:3000/workspaces"

:launch_complete
echo.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:3000/workspaces
echo.
echo Keep the Backend and Frontend windows open while using AURORA.
echo Closing this launcher window will not stop those servers or PostgreSQL.
echo To restart servers cleanly with new code, run start-aurora.bat again.
echo.
pause
exit /b 0

:install_frontend
pushd "%FRONTEND_DIR%"
where pnpm.cmd >nul 2>&1
if not errorlevel 1 (
    call pnpm install
    set "INSTALL_RESULT=!errorlevel!"
    popd
    exit /b !INSTALL_RESULT!
)
where corepack.cmd >nul 2>&1
if not errorlevel 1 (
    call corepack pnpm install
    set "INSTALL_RESULT=!errorlevel!"
    popd
    exit /b !INSTALL_RESULT!
)
popd
exit /b 1

:kill_port
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$p = (Get-NetTCPConnection -LocalPort %~1 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique); foreach ($id in $p) { if ($id -and $id -gt 4) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }" >nul 2>&1
exit /b 0

:port_open
powershell.exe -NoLogo -NoProfile -NonInteractive -Command "$client = [Net.Sockets.TcpClient]::new(); try { $client.Connect('127.0.0.1', %~1); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %errorlevel%

:run_backend
title AURORA Backend - http://127.0.0.1:8000
cd /d "%BACKEND_DIR%"
echo Starting the AURORA FastAPI backend...
"%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
echo.
echo The backend stopped. Review any error above.
exit /b %errorlevel%

:run_frontend
title AURORA Frontend - http://localhost:3000
cd /d "%FRONTEND_DIR%"
echo Starting the AURORA Next.js frontend...
call "%NEXT_EXE%" dev
echo.
echo The frontend stopped. Review any error above.
exit /b %errorlevel%

:show_help
echo AURORA launcher
echo.
echo Double-click start-aurora.bat or run it without arguments.
echo It starts PostgreSQL, applies migrations, launches the backend and frontend,
echo waits for port 3000, and opens http://localhost:3000/workspaces.
exit /b 0

:launch_failed
echo.
echo AURORA was not started. Resolve the error above and run this file again.
echo.
pause
exit /b 1
