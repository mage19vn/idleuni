#!/bin/bash
echo "======================================================="
echo "    DANG CAP NHAT VA KHOI DONG LAI DOCKER CONTAINER"
echo "======================================================="
echo ""

# Chuyen den thu muc du an (nhan tham so 1, mac dinh la thu muc chua script hoac pwd)
TARGET_DIR="${1:-$(pwd)}"
echo "Dich den thu muc: $TARGET_DIR"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Thu muc $TARGET_DIR khong ton tai. Dang tao moi..."
    mkdir -p "$TARGET_DIR"
fi

cd "$TARGET_DIR" || exit 1

echo "0. Kiem tra ket noi Git..."
if [ ! -d ".git" ]; then
    echo "Thu muc chua duoc khoi tao git. Dang khoi tao..."
    git init
    git checkout -B main
fi

# Dat url cho remote origin de dam bao dung du an
git remote set-url origin https://github.com/mage19vn/idleuni.git 2>/dev/null || git remote add origin https://github.com/mage19vn/idleuni.git

echo "Dang lay code moi nhat tu Git..."
git fetch origin

echo "Dang dong bo code (ghi de moi thay doi cuc bo de dam bao sach se)..."
git reset --hard origin/main

echo ""
if command -v docker-compose &> /dev/null; then
    DOCKER_CMD="docker-compose"
else
    DOCKER_CMD="docker compose"
fi

echo "1. Dang dung cac container cu (neu co)..."
$DOCKER_CMD down 2>/dev/null || true
docker stop unicorns_app 2>/dev/null || true
docker rm unicorns_app 2>/dev/null || true

echo "2. Dang build va chay lai toan bo he thong..."
$DOCKER_CMD up -d --build

echo "2.5. Kiem tra Sandbox Images..."
if ! docker image inspect unicorns-cpp:latest >/dev/null 2>&1; then
    echo "Dang tai unicorns-cpp..."
    docker pull gcc:latest
    docker tag gcc:latest unicorns-cpp:latest
fi
if ! docker image inspect unicorns-python:latest >/dev/null 2>&1; then
    echo "Dang tai unicorns-python..."
    docker pull python:3.9-slim
    docker tag python:3.9-slim unicorns-python:latest
fi

echo "3. Dang khoi tao co so du lieu (Migrate)..."
# Kiem tra va doi DB san sang (toi da 30 giay)
echo "Dang cho database san sang..."
for i in {1..15}; do
    if $DOCKER_CMD exec -T web python manage.py inspectdb > /dev/null 2>&1; then
        echo "Database da san sang!"
        break
    fi
    echo "Cho database... ($i/15)"
    sleep 2
done

# Chay migrate va bat loi neu that bai
echo "Dang tien hanh migrate..."
if ! $DOCKER_CMD exec -T web python manage.py migrate; then
    echo "======================================================="
    echo " LOI: MIGRATE THAT BAI! Kiem tra lai ket noi Database."
    echo "======================================================="
    exit 1
fi

echo ""
echo "======================================================="
echo "  CAP NHAT THANH CONG! Truy cap: http://localhost:8000"
echo "======================================================="