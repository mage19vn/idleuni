# Uni IDE - Nền tảng Trình biên dịch & Mô phỏng Code

Uni IDE là một trình biên dịch và mô phỏng thực thi mã nguồn (Visualizer) mạnh mẽ, hỗ trợ Python và C++. Hệ thống được thiết kế linh hoạt với kiến trúc Asynchronous Message Queue (Hàng đợi bất đồng bộ) giúp chịu tải cao.

---

## 🚀 1. Yêu cầu Hệ thống (Prerequisites)

Để khởi chạy dự án này trên máy cá nhân hoặc máy chủ (Windows/Linux), bạn cần cài đặt các phần mềm nền tảng sau:

1. **Python 3.9+**: Môi trường chạy nền tảng Django và Celery.
2. **Trình biên dịch C++ (MinGW/GCC)**: 
   - Windows: Tải và cài đặt [MinGW-w64](https://www.msys2.org/). Hãy chắc chắn thư mục `bin` chứa `g++.exe` đã được thêm vào biến môi trường `PATH`.
   - Linux: Cài đặt qua lệnh `sudo apt install g++`.
3. **LLVM / libclang**: Bắt buộc để dùng tính năng C++ Visualizer (AST Parser).
   - Windows: Tải và cài đặt LLVM (bản Pre-built cho Windows) từ [Github LLVM](https://github.com/llvm/llvm-project/releases). Bật tùy chọn **"Add LLVM to the system PATH"** trong quá trình cài đặt.
   - Linux: `sudo apt install libclang-dev`.
4. **Redis Server**: Bắt buộc để chạy kiến trúc Message Queue cho Celery.
   - Windows: Bạn có thể cài [Memurai](https://www.memurai.com/) (Redis cho Windows) hoặc dùng Docker (`docker run -d -p 6379:6379 redis`).
   - Linux: `sudo apt install redis-server`.

---

## 🛠️ 2. Cài đặt Dự án (Installation)

1. Clone dự án và truy cập vào thư mục chứa code (`unicorns_project`).
2. Cài đặt các thư viện Python yêu cầu:
```bash
pip install -r requirements.txt
```
*(Các thư viện chính bao gồm: `Django`, `celery`, `redis`, `libclang`...)*

3. Tạo Database (SQLite mặc định):
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## ⚡ 3. Hướng dẫn Khởi chạy (Running the Project)

Hệ thống cung cấp nhiều phương thức khởi chạy khác nhau tùy thuộc vào môi trường:

### Chế độ 1: Dùng Docker Compose (Khuyên dùng cho Server / Production)
Đây là cách đơn giản và ổn định nhất để chạy trên máy chủ (Linux/VPS). Hệ thống sẽ tự động đóng gói và thiết lập toàn bộ PostgreSQL, Redis, Web Server (Gunicorn) và Celery Worker.
1. Hãy đảm bảo máy bạn đã cài đặt [Docker](https://docs.docker.com/get-docker/) và **Docker Compose**.
2. Tại thư mục dự án, chạy lệnh:
```bash
docker-compose up -d --build
```
3. Khởi tạo cơ sở dữ liệu cho lần chạy đầu tiên:
```bash
docker-compose exec -T web python manage.py migrate
```
*(💡 Mẹo: Trên server Linux, bạn có thể chạy thẳng file `./update.sh` để tự động hóa toàn bộ quá trình cập nhật code và build lại)*

### Chế độ 2: Chạy thủ công đa tiến trình (Manual Async Mode)
Dành cho Developer muốn tự quản lý từng thành phần. Bạn cần mở **3 cửa sổ Terminal (Command Prompt)** riêng biệt và chạy đồng thời:

**Terminal 1: Khởi động Redis (Nếu dùng Docker)**
```bash
docker run -d -p 6379:6379 redis
```
*(Nếu cài Memurai/Redis dưới dạng Service thì bỏ qua bước này)*

**Terminal 2: Khởi động Web Server (Django)**
```bash
python manage.py runserver
```

**Terminal 3: Khởi động Celery Worker (Người chạy việc)**
- Trên Windows:
```bash
celery -A unicorns_project worker --loglevel=info --pool=solo
```
- Trên Linux:
```bash
celery -A unicorns_project worker --loglevel=info
```

### Chế độ 3: Môi trường Test Nhanh (Eager Mode / No Redis)
Dành cho Developer muốn test UI nhanh mà không cần bật Redis và Celery Worker.
1. Mở file `unicorns_project/settings.py`.
2. Tìm và BẬT biến này lên: `CELERY_TASK_ALWAYS_EAGER = True`.
3. Chỉ cần chạy duy nhất Web Server: `python manage.py runserver`.
*(Lưu ý: Mọi code sẽ được chạy thẳng một cách đồng bộ. Khi có nhiều người dùng cùng lúc, máy chủ sẽ bị treo).*

---

## 🧩 4. Cấu trúc Dự án
- `compiler/views.py`: API Server và giao diện người dùng.
- `compiler/tasks.py`: Worker chịu trách nhiệm gọi lệnh biên dịch C++ và Python ở chế độ nền.
- `compiler/python_tracer.py`: Bộ kiểm soát môi trường (Sandbox & Tracing) an toàn cho Python.
- `compiler/instrumentation.py`: Bộ công cụ phân tích AST và cấy mã tự động cho ngôn ngữ C++ bằng `libclang`.
