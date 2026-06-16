import uuid

class SecurityHeadersMiddleware:
    """
    Middleware thêm các HTTP Security Headers cần thiết vào mọi response.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        nonce = uuid.uuid4().hex
        request.csp_nonce = nonce

        response = self.get_response(request)

        # 1. Content Security Policy (CSP)
        csp_directives = [
            "default-src 'self'",
            (
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdnjs.cloudflare.com "
                "https://cdn.jsdelivr.net "
                "https://unpkg.com "
                "https://www.youtube.com "
            ),
            (
                # Monaco Editor requires inline styles to function properly
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
            "connect-src 'self' https://*.ngrok-free.dev",
            "worker-src 'self' blob:",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)

        # 2. Security Headers (Anti-clickjacking, MIME sniffing, HSTS)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )
        
        # HSTS
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        return response
