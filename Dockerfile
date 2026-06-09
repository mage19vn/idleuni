# Sử dụng image Python 3.9 gọn nhẹ
FROM python:3.9-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Cài đặt môi trường compile C++, GDB và công cụ tính toán thời gian/bộ nhớ
RUN apt-get update && apt-get install -y \
    g++ \
    gdb \
    time \
    && rm -rf /var/lib/apt/lists/*

# Tạo thư mục làm việc trong Container
WORKDIR /app

# Copy file requirements và cài đặt thư viện
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code Django vào container
COPY . /app/

# BƯỚC QUAN TRỌNG: Ép Django gom file CSS/JS lại (Sửa lỗi mất giao diện)
RUN python manage.py collectstatic --noinput

# Mở port 8000
EXPOSE 8000

# Chạy server Django bằng Gunicorn (Chuẩn cho Production) kèm auto-reload cho dev
CMD ["gunicorn", "unicorns_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--reload"]