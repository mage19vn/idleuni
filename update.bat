@echo off
echo =======================================================
echo     DANG CAP NHAT VA KHOI DONG LAI DOCKER CONTAINER
echo =======================================================
echo.

echo 1. Dang dung container cu...
docker stop unicorns_app 2>NUL

echo 2. Dang xoa container cu...
docker rm unicorns_app 2>NUL

echo 3. Dang build lai image (uniidle)...
docker build -t uniidle .

echo 4. Dang chay lai container voi code moi nhat...
docker run -d -p 8000:8000 -e DB_HOST=host.docker.internal -v "%cd%":/app --name unicorns_app uniidle

echo.
echo =======================================================
echo   CAP NHAT THANH CONG! Truy cap: http://localhost:8000
echo =======================================================
pause
