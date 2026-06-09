#!/bin/bash
echo "======================================================="
echo "    DANG CAP NHAT VA KHOI DONG LAI DOCKER CONTAINER"
echo "======================================================="
echo ""

echo "0. Kiem tra ket noi Git..."
if [ ! -d ".git" ]; then
    echo "Thu muc chua duoc khoi tao git. Dang khoi tao..."
    git init
fi

# Dat url cho remote origin de dam bao dung du an
git remote set-url origin https://github.com/mage19vn/uniidle.git 2>/dev/null || git remote add origin https://github.com/mage19vn/uniidle.git

echo "Dang pull code moi nhat tu Git..."
git pull origin main
echo ""

echo "1. Dang dung container cu..."
docker stop unicorns_app 2>/dev/null

echo "2. Dang xoa container cu..."
docker rm unicorns_app 2>/dev/null

echo "3. Dang build lai image (uniidle)..."
docker build -t uniidle .

echo "4. Dang chay lai container voi code moi nhat..."
# Thay %cd% bằng $(pwd)
docker run -d -p 8000:8000 -v "$(pwd):/app" --name unicorns_app uniidle

echo ""
echo "======================================================="
echo "  CAP NHAT THANH CONG! Truy cap: http://localhost:8000"
echo "======================================================="
read -p "Nhan Enter de thoat..."