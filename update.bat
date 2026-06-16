@echo off
setlocal
echo =======================================================
echo     DANG CAP NHAT VA KHOI DONG LAI HE THONG DOCKER
echo =======================================================
echo.

:: Kiem tra phien ban docker compose
docker compose version >NUL 2>NUL
if %errorlevel% equ 0 (
    set DOCKER_CMD=docker compose
) else (
    set DOCKER_CMD=docker-compose
)

echo 0. Dang day code len GitHub...
git add -A
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo Khong co thay doi moi de commit.
) else (
    for /f "delims=" %%i in ('powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"') do set TIMESTAMP=%%i
    git commit -m "update: auto-deploy %TIMESTAMP%"
    git push origin main
    if %errorlevel% neq 0 (
        echo CANH BAO: Push len GitHub that bai. Tiep tuc deploy local...
    ) else (
        echo Push thanh cong len GitHub.
    )
)

echo.
echo 1. Dang dung cac container cu (neu co)...
%DOCKER_CMD% down >NUL 2>NUL
docker stop unicorns_app >NUL 2>NUL
docker rm unicorns_app >NUL 2>NUL

echo.
echo 2. Dang build va chay lai he thong (Postgres, Redis, Web, Celery)...
%DOCKER_CMD% up -d --build

echo.
echo 3. Dang kiem tra Sandbox Images...
docker image inspect unicorns-cpp:latest >NUL 2>NUL
if %errorlevel% neq 0 (
    echo Dang tai unicorns-cpp...
    docker pull gcc:latest
    docker tag gcc:latest unicorns-cpp:latest
)
docker image inspect unicorns-python:latest >NUL 2>NUL
if %errorlevel% neq 0 (
    echo Dang tai unicorns-python...
    docker pull python:3.9-slim
    docker tag python:3.9-slim unicorns-python:latest
)

echo.
echo 4. Dang khoi tao co so du lieu (Migrate)...
echo Dang cho database san sang...
set count=0
:wait_db
%DOCKER_CMD% exec -T web python manage.py inspectdb >NUL 2>NUL
if %errorlevel% equ 0 (
    echo Database da san sang!
    goto :migrate
)
set /a count+=1
if %count% geq 15 (
    echo Qua thoi gian cho phep. Tiep tuc migrate nhung co the se that bai...
    goto :migrate
)
echo Cho database... (%count%/15)
timeout /t 2 /nobreak >NUL
goto :wait_db

:migrate
echo Dang tien hanh migrate...
%DOCKER_CMD% exec -T web python manage.py migrate
if %errorlevel% neq 0 (
    echo =======================================================
    echo  LOI: MIGRATE THAT BAI! Kiem tra lai ket noi Database.
    echo =======================================================
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   CAP NHAT THANH CONG! Truy cap: http://localhost:8000
echo =======================================================
pause
