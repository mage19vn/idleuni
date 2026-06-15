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

echo "3. Dang khoi tao co so du lieu (Migrate)..."
# Doi 3 giay de database kip san sang truoc khi migrate
sleep 3
$DOCKER_CMD exec -T web python manage.py migrate

echo ""
echo "======================================================="
echo "  CAP NHAT THANH CONG! Truy cap: http://localhost:8000"
echo "======================================================="