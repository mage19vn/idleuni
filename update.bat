@echo off
setlocal
echo =======================================================
echo     DANG BUILD VA KHOI DONG LAI HE THONG (LOCAL)
echo =======================================================
echo.

:: Kiem tra phien ban docker compose
docker compose version >NUL 2>NUL
if %errorlevel% equ 0 (
    set DOCKER_CMD=docker compose
) else (
    set DOCKER_CMD=docker-compose
)

echo 1. Dang dung cac container hien tai...
%DOCKER_CMD% down

echo.
echo 2. Dang build va khoi dong lai (Bao gom API Server, DB, Redis, Celery)...
%DOCKER_CMD% up -d --build
if %errorlevel% neq 0 (
    echo =======================================================
    echo  LOI: BUILD / KHOI DONG THAT BAI!
    echo =======================================================
    pause
    exit /b 1
)

echo.
echo 3. Kiem tra Sandbox Images (Python, C++)...
docker image inspect unicorns-python:latest >NUL 2>NUL
if %errorlevel% neq 0 (
    echo Dang tai unicorns-python...
    docker pull python:3.9-slim
    docker tag python:3.9-slim unicorns-python:latest
)
docker image inspect unicorns-cpp:latest >NUL 2>NUL
if %errorlevel% neq 0 (
    echo Dang tai unicorns-cpp...
    docker pull gcc:latest
    docker tag gcc:latest unicorns-cpp:latest
)

echo.
echo 4. Dang cho database khoi dong de migrate...
set count=0
:wait_db
%DOCKER_CMD% exec -T web python manage.py inspectdb >NUL 2>NUL
if %errorlevel% equ 0 (
    echo Database da san sang. Dang cap nhat cau truc (neu co)...
    goto :migrate
)
set /a count+=1
if %count% geq 15 (
    echo Qua thoi gian cho phep, se thu migrate...
    goto :migrate
)
echo Cho database... (%count%/15)
timeout /t 2 /nobreak >NUL
goto :wait_db

:migrate
%DOCKER_CMD% exec -T web python manage.py migrate
if %errorlevel% neq 0 (
    echo =======================================================
    echo  LOI: MIGRATE THAT BAI! Kiem tra lai he thong.
    echo =======================================================
    pause
    exit /b 1
)

echo.
echo 5. Dang gom file tinh (CSS/JS)...
%DOCKER_CMD% exec -T web python manage.py collectstatic --noinput
if %errorlevel% neq 0 (
    echo =======================================================
    echo  LOI: GOM FILE TINH THAT BAI!
    echo =======================================================
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   HOAN TAT! API Server da chay tai: http://localhost:8000
echo =======================================================
pause
