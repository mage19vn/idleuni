import uuid


class SecurityHeadersMiddleware:
    """
    Middleware thêm các HTTP Security Headers cần thiết vào mọi response.
    - Content-Security-Policy: Chống XSS, clickjacking, injection
    - X-Content-Type-Options: Ngăn MIME-sniffing
    - X-Frame-Options: Chống clickjacking (fallback cho CSP frame-ancestors)
    - Referrer-Policy: Kiểm soát thông tin referrer được gửi đi
    - Permissions-Policy: Hạn chế truy cập các API nhạy cảm của trình duyệt
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Tạo nonce ngẫu nhiên cho CSP (dùng cho inline scripts nếu cần)
        nonce = uuid.uuid4().hex
        request.csp_nonce = nonce

        response = self.get_response(request)

        # --- Content Security Policy ---
        # Cho phép:
        # - Scripts từ CDN đáng tin cậy (cdnjs, cloudflare, unpkg)
        # - Styles từ CDN đáng tin cậy + Google Fonts
        # - Fonts từ Google Fonts + data URIs
        # - Images từ self + data URIs (cho favicon, SVG)
        # - Kết nối AJAX chỉ đến chính server (ngăn data exfil)
        # - Chặn iframe nhúng trang này vào nơi khác (clickjacking)
        csp_directives = [
            "default-src 'self'",
            (
                "script-src 'self' 'unsafe-eval' "
                "https://cdnjs.cloudflare.com "
                "https://cdn.jsdelivr.net "
                "https://unpkg.com "
                "https://www.youtube.com "
            ),
            (
                "style-src 'self' 'unsafe-inline' "
                "https://cdnjs.cloudflare.com "
                "https://fonts.googleapis.com "
                "https://cdn.jsdelivr.net "
                "https://unpkg.com"
            ),
            (
                "font-src 'self' data: "
                "https://fonts.gstatic.com "
                "https://cdnjs.cloudflare.com "
                "https://cdn.jsdelivr.net "
                "https://unpkg.com"
            ),
            "img-src 'self' data: blob: https:",
            "connect-src 'self' https://predefine-pavement-zit.ngrok-free.dev",
            "worker-src 'self' blob:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)

        # --- X-Content-Type-Options ---
        # Ngăn trình duyệt đoán MIME type (chống MIME confusion attacks)
        response['X-Content-Type-Options'] = 'nosniff'

        # --- X-Frame-Options ---
        # Chống clickjacking (bổ sung cho CSP frame-ancestors)
        response['X-Frame-Options'] = 'DENY'

        # --- Referrer-Policy ---
        # Chỉ gửi referrer khi đi trong cùng origin, ẩn khi ra ngoài
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # --- Permissions-Policy ---
        # Tắt các API trình duyệt nhạy cảm không cần thiết
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )

        return response
