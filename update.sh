#!/bin/bash
echo "======================================================="
echo "    DANG CAP NHAT TU GITHUB VA DEPLOY (SERVER)"
echo "======================================================="
echo ""

TARGET_DIR="${1:-$(pwd)}"
cd "$TARGET_DIR" || exit 1

echo "1. Dong bo code tu GitHub..."
if [ ! -d ".git" ]; then
    git init
    git checkout -B main
fi
git remote set-url origin https://github.com/mage19vn/idleuni.git 2>/dev/null || git remote add origin https://github.com/mage19vn/idleuni.git

git fetch origin
# Ghi de toan bo thay doi local bang code moi tren github
git reset --hard origin/main
git clean -fd

echo ""
if command -v docker-compose &> /dev/null; then
    DOCKER_CMD="docker-compose"
else
    DOCKER_CMD="docker compose"
fi

echo "2. Dung he thong cu..."
$DOCKER_CMD down 2>/dev/null || true
# Lam sach them neu can thiet
docker stop unicorns_app 2>/dev/null || true
docker rm unicorns_app 2>/dev/null || true

echo "3. Build va khoi dong lai (Du lieu CSDL van duoc bao toan trong Volume)..."
$DOCKER_CMD up -d --build

echo "4. Kiem tra Sandbox Images (Python, C++)..."
if ! docker image inspect unicorns-python:latest > /dev/null 2>&1; then
    echo "Dang tai unicorns-python..."
    docker pull python:3.9-slim
    docker tag python:3.9-slim unicorns-python:latest
fi
if ! docker image inspect unicorns-cpp:latest > /dev/null 2>&1; then
    echo "Dang tai unicorns-cpp..."
    docker pull gcc:latest
    docker tag gcc:latest unicorns-cpp:latest
fi

echo "5. Cho Database san sang de migrate..."
for i in {1..20}; do
    if $DOCKER_CMD exec -T web python manage.py inspectdb > /dev/null 2>&1; then
        echo "Database da san sang!"
        break
    fi
    echo "Cho database... ($i/20)"
    sleep 2
done

echo "Dang cap nhat cau truc bang (neu co)..."
if ! $DOCKER_CMD exec -T web python manage.py migrate; then
    echo "======================================================="
    echo " LOI: MIGRATE THAT BAI!"
    echo "======================================================="
    exit 1
fi

echo ""
echo "======================================================="
echo "  DEPLOY THANH CONG TREN SERVER!"
echo "======================================================="