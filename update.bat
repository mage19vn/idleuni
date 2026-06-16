@echo off
setlocal
echo =======================================================
echo         DANG DAY CODE LEN GITHUB (LOCAL)
echo =======================================================
echo.

echo 1. Dang kiem tra thay doi...
git status

echo.
echo 2. Dang them toan bo file thay doi...
git add -A

echo.
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo Khong co thay doi moi. Khong can commit.
    echo.
    echo =======================================================
    echo   KHONG CO GI DE CAP NHAT.
    echo =======================================================
    pause
    exit /b 0
)

echo 3. Dang tao commit...
for /f "delims=" %%i in ('powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"') do set TIMESTAMP=%%i
git commit -m "update: %TIMESTAMP%"

echo.
echo 4. Dang push len GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo =======================================================
    echo  LOI: PUSH THAT BAI! Kiem tra ket noi mang hoac token.
    echo =======================================================
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   PUSH THANH CONG! Chay update.sh tren server de deploy.
echo =======================================================
pause
