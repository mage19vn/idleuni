with open('compiler/views.py', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add rate_limit
rate_limit_code = """
from django.core.cache import cache
from functools import wraps

def rate_limit(limit=10, window=60):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            session_id = get_client_session(request)
            key = f"rate_limit:{view_func.__name__}:{session_id}"
            count = cache.get(key, 0)
            if count >= limit:
                return JsonResponse({"success": False, "error": "Thao tác quá nhanh. Vui lòng chậm lại!"}, status=429)
            cache.set(key, count + 1, timeout=window)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
"""
c = c.replace("from django.http import JsonResponse, Http404", "from django.http import JsonResponse, Http404\n" + rate_limit_code)

# 2. Add rate_limit to save_snippet_api and size checks
save_snippet_orig = """def save_snippet_api(request):
    if request.method == "POST":
        try:
            session_id = get_client_session(request)
            data = get_decrypted_data(request)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_text = data.get('inputs', '')
            existing_hash = data.get('hash_id')
            title = data.get('title', 'Không tên')
            is_public = data.get('is_public', True)"""

save_snippet_new = """@rate_limit(limit=10, window=60)
def save_snippet_api(request):
    if request.method == "POST":
        try:
            session_id = get_client_session(request)
            data = get_decrypted_data(request)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_text = data.get('inputs', '')
            existing_hash = data.get('hash_id')
            title = data.get('title', 'Không tên')
            is_public = data.get('is_public', True)
            
            if len(code) > 50000:
                return JsonResponse({"success": False, "error": "Code quá dài (tối đa 50KB)."})
            if len(input_text) > 10000:
                return JsonResponse({"success": False, "error": "Input quá dài (tối đa 10KB)."})
            if len(title) > 255:
                return JsonResponse({"success": False, "error": "Tiêu đề quá dài."})"""
c = c.replace(save_snippet_orig, save_snippet_new)

# 3. Add rate_limit to visualize_api and size checks
visualize_api_orig = """def visualize_api(request):
    if request.method == "POST":
        try:
            data = get_decrypted_data(request)
            language = data.get("language")
            code = data.get("code")
            inputs = data.get("inputs", "")"""

visualize_api_new = """@rate_limit(limit=5, window=10)
def visualize_api(request):
    if request.method == "POST":
        try:
            data = get_decrypted_data(request)
            language = data.get("language")
            code = data.get("code")
            inputs = data.get("inputs", "")
            
            if code is None: code = ""
            if inputs is None: inputs = ""
            if len(code) > 50000:
                return JsonResponse({"error": "Code quá dài (tối đa 50KB).", "trace": [], "output": ""})
            if len(inputs) > 10000:
                return JsonResponse({"error": "Input quá dài (tối đa 10KB).", "trace": [], "output": ""})"""
c = c.replace(visualize_api_orig, visualize_api_new)

with open('compiler/views.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("Update Phase 4 complete.")
