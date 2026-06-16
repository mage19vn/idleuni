import os
import sys
import io
import tempfile
import subprocess
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

SECRET_KEY_AES = b'12345678901234567890123456789012'
IV_AES = b'1234567890123456'

import socket

SANDBOX_VOLUME_NAME = None
def get_sandbox_volume_name():
    global SANDBOX_VOLUME_NAME
    if SANDBOX_VOLUME_NAME: return SANDBOX_VOLUME_NAME
    try:
        cid = socket.gethostname()
        out = subprocess.run(["docker", "inspect", cid, "--format", "{{json .Mounts}}"], capture_output=True, text=True).stdout
        import json
        mounts = json.loads(out)
        for m in mounts:
            if m.get("Destination") == "/sandbox_data":
                SANDBOX_VOLUME_NAME = m.get("Name")
                return SANDBOX_VOLUME_NAME
    except Exception:
        pass
    SANDBOX_VOLUME_NAME = "sandbox_data"
    return SANDBOX_VOLUME_NAME

from django.core.exceptions import RequestDataTooBig

def get_decrypted_data(request):
    try:
        body = json.loads(request.body)
        if 'payload' in body:
            encrypted_b64 = body['payload']
            encrypted_bytes = base64.b64decode(encrypted_b64)
            cipher = AES.new(SECRET_KEY_AES, AES.MODE_CBC, IV_AES)
            decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return json.loads(decrypted_bytes.decode('utf-8'))
        return body
    except RequestDataTooBig:
        raise
    except Exception as e:
        print('Decrypt Error:', e)
        return {}

import time
import re
import ast
import zlib
import secrets
import hashlib
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404

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

from django.conf import settings
from .models import Profile, CodeSnippet, CodeTemplate, KeymapTemplate
from .forms import ProfileUpdateForm
from django.contrib import messages
from datetime import datetime

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

def get_client_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key

def is_safe_python_code(code: str) -> str:
    return None

def is_safe_cpp_code(code: str) -> str:
    return None

def set_resource_limits():
    if HAS_RESOURCE:
        try:
            megabyte = 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (256 * megabyte, 256 * megabyte))
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
            resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
        except Exception:
            pass

def get_safe_env():
    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TEMP": os.environ.get("TEMP", "/tmp"),
        "TMP": os.environ.get("TMP", "/tmp")
    }
    if os.name == 'nt':
        safe_env["SystemRoot"] = os.environ.get("SystemRoot", "C:\\Windows")
        safe_env["TEMP"] = os.environ.get("TEMP", "C:\\Temp")
        safe_env["TMP"] = os.environ.get("TMP", "C:\\Temp")
    return safe_env

def trace_python(code: str, inputs: str):
    security_error = is_safe_python_code(code)
    if security_error:
        return {"trace": [], "output": "", "error": security_error}
    
    sandbox_dir = '/sandbox_data' if os.path.exists('/sandbox_data') else None
    with tempfile.TemporaryDirectory(dir=sandbox_dir) as temp_dir:
        os.chmod(temp_dir, 0o777)
        user_code_path = os.path.join(temp_dir, "main.py")
        with open(user_code_path, "w", encoding="utf-8") as f:
            f.write(code)

        tracer_source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_tracer.py")
        import shutil
        shutil.copy(tracer_source_path, os.path.join(temp_dir, "tracer.py"))

        os.chmod(user_code_path, 0o777)
        os.chmod(os.path.join(temp_dir, "tracer.py"), 0o777)

        is_docker = os.path.exists('/sandbox_data')
        if is_docker:
            vol_args = ["-v", f"{get_sandbox_volume_name()}:/sandbox_data", "-w", temp_dir]
        else:
            vol_args = ["-v", f"{temp_dir}:/sandbox", "-w", "/sandbox"]

        try:
            subprocess.run(
                ["docker", "run", "--rm", "--network", "none"] + vol_args + 
                ["-i", "unicorns-python:latest", "python", "tracer.py"],
                cwd=temp_dir, input=inputs, timeout=5,
                capture_output=True, text=True
            )
        except subprocess.TimeoutExpired:
            return {"trace": [], "output": "", "error": "Chương trình Python kẹt vòng lặp vô hạn hoặc chờ input quá lâu."}
        
        trace_result, output_result, error_result, error_line_result, time_ms, memory_kb = [], "", None, -1, 0.0, 0.0

        for file_name, target in [("trace.json", "trace"), ("output.txt", "output"), ("error.txt", "error"), ("error_line.txt", "error_line"), ("metrics.json", "metrics")]:
            path = os.path.join(temp_dir, file_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    if target == "trace":
                        try: trace_result = json.load(f)
                        except: pass
                    elif target == "output": output_result = f.read()
                    elif target == "error": error_result = f.read()
                    elif target == "error_line":
                        try: error_line_result = int(f.read().strip())
                        except: pass
                    elif target == "metrics":
                        try:
                            m = json.load(f)
                            time_ms, memory_kb = m.get("time_ms", 0.0), m.get("memory_kb", 0.0)
                        except: pass

        return {
            "trace": trace_result, "output": output_result, "error": error_result,
            "error_line": error_line_result, "time_ms": time_ms, "memory_kb": memory_kb
        }

def trace_cpp(code: str, inputs: str):
    security_error = is_safe_cpp_code(code)
    if security_error:
        return {"trace": [], "output": "", "error": security_error, "error_line": -1, "time_ms": 0.0, "memory_kb": 0.0}
        
    code = re.sub(r'freopen\s*\(\s*["\'][^"\']+["\']\s*,\s*["\']r["\']\s*,\s*stdin\s*\)\s*;?', '', code)
    code = re.sub(r'freopen\s*\(\s*["\'][^"\']+["\']\s*,\s*["\']w["\']\s*,\s*stdout\s*\)\s*;?', '', code)

    sandbox_dir = '/sandbox_data' if os.path.exists('/sandbox_data') else None
    with tempfile.TemporaryDirectory(dir=sandbox_dir) as temp_dir:
        os.chmod(temp_dir, 0o777)
        exe_name = "main.exe" if os.name == 'nt' else "main.out"
        cpp_name = "main.cpp"
        
        with open(os.path.join(temp_dir, cpp_name), "w", encoding="utf-8") as f: f.write(code)
        with open(os.path.join(temp_dir, "input.txt"), "w", encoding="utf-8") as f: f.write(inputs)

        os.chmod(os.path.join(temp_dir, cpp_name), 0o777)
        os.chmod(os.path.join(temp_dir, "input.txt"), 0o777)

        is_docker = os.path.exists('/sandbox_data')
        if is_docker:
            vol_args = ["-v", f"{get_sandbox_volume_name()}:/sandbox_data", "-w", temp_dir]
        else:
            vol_args = ["-v", f"{temp_dir}:/sandbox", "-w", "/sandbox"]

        compile_process = subprocess.run(
            ["docker", "run", "--rm", "--network", "none"] + vol_args + ["unicorns-cpp:latest", "g++", "-O2", cpp_name, "-o", exe_name],
            cwd=temp_dir, capture_output=True, text=True
        )
        
        if compile_process.returncode != 0:
            err_line = -1
            match = re.search(r'main\.cpp:(\d+):', compile_process.stderr)
            if match: err_line = int(match.group(1))
            return {"trace": [], "output": "", "error": "Lỗi biên dịch:\n" + compile_process.stderr, "error_line": err_line, "time_ms": 0.0, "memory_kb": 0.0}

        time_ms, memory_kb, exe_path = 0.0, 0.0, os.path.join(temp_dir, exe_name)
        start_time = time.perf_counter()
        
        try:
            exec_process = subprocess.run(
                ["docker", "run", "--rm", "--network", "none"] + vol_args + ["-i", "unicorns-cpp:latest", f"./{exe_name}"],
                cwd=temp_dir, input=inputs, timeout=3, capture_output=True, text=True
            )
            end_time = time.perf_counter()
            time_ms = round((end_time - start_time) * 1000, 2)
        except subprocess.TimeoutExpired:
            return {"trace": [], "output": "", "error": "Lỗi: Chương trình C++ chạy quá 2 giây (Time Limit Exceeded).", "error_line": -1, "time_ms": 2000.0, "memory_kb": 0.0}
        
        trace_result = []
        try:
            import sys
            compiler_dir = os.path.dirname(os.path.abspath(__file__))
            if compiler_dir not in sys.path:
                sys.path.append(compiler_dir)
            import instrumentation
            
            instrumented_code = instrumentation.instrument_cpp_code(code)
            inst_cpp_name = "instrumented.cpp"
            inst_exe_name = "trace.exe" if os.name == 'nt' else "trace.out"
            
            with open(os.path.join(temp_dir, inst_cpp_name), "w", encoding="utf-8") as f:
                f.write(instrumented_code)
            os.chmod(os.path.join(temp_dir, inst_cpp_name), 0o777)
                
            trace_compile = subprocess.run(
                ["docker", "run", "--rm", "--network", "none"] + vol_args + ["unicorns-cpp:latest", "g++", "-g", "-O0", inst_cpp_name, "-o", inst_exe_name],
                cwd=temp_dir, capture_output=True, text=True
            )
            
            if trace_compile.returncode == 0:
                subprocess.run(
                    ["docker", "run", "--rm", "--network", "none"] + vol_args + ["-i", "unicorns-cpp:latest", f"./{inst_exe_name}"],
                    cwd=temp_dir, input=inputs, timeout=5, capture_output=True, text=True
                )
            else:
                with open("debug_trace.txt", "a", encoding="utf-8") as f:
                    f.write("=== TRACE COMPILE ERROR ===\n")
                    f.write(trace_compile.stderr + "\n")
                    f.write("=== ORIGINAL CODE ===\n")
                    f.write(code + "\n")
                    f.write("=== INSTRUMENTED CODE ===\n")
                    f.write(instrumented_code + "\n")
                
            if trace_compile.returncode == 0:
                trace_file = os.path.join(temp_dir, "trace.json")
                if os.path.exists(trace_file):
                    with open(trace_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            trace_result = json.loads(content)
        except Exception as e:
            print("AST Instrumentation Error:", e)

        error_msg = None
        if exec_process.stderr:
            error_msg = exec_process.stderr

        return {
            "trace": trace_result, "output": exec_process.stdout.replace("\\n", "\n"), "error": error_msg,
            "error_line": -1, "time_ms": time_ms, "memory_kb": memory_kb 
        }

# --- VIEW CỦA DJANGO ---

def profile_view(request):
    session_id = get_client_session(request)
    profile, created = Profile.objects.get_or_create(session_id=session_id)
    
    # Tạo mã ID mặc định cố định dựa trên session_id
    import hashlib
    uni_id_hash = hashlib.md5(session_id.encode('utf-8')).hexdigest()[:8].upper()
    uni_id = f"Uni_{uni_id_hash}"
    
    # Nếu tạo mới, gán tên tác giả bằng ID mặc định
    if created or not profile.display_name:
        profile.display_name = uni_id
        profile.save(update_fields=['display_name'])

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'ide_settings')
        
        if form_type == 'display_name':
            # Chỉ lưu tên tác giả
            new_name = request.POST.get('display_name', '').strip()
            if new_name:
                profile.display_name = new_name
                profile.save(update_fields=['display_name'])
                messages.success(request, 'Cập nhật tên tác giả thành công!')
            return redirect('profile')
        else:
            # Lưu cài đặt IDE, bỏ qua display_name
            old_display_name = profile.display_name
            p_form = ProfileUpdateForm(request.POST, instance=profile)
            p_form.fields['display_name'].required = False
            
            if p_form.is_valid():
                updated_profile = p_form.save(commit=False)
                updated_profile.display_name = old_display_name # Giữ nguyên tên
                updated_profile.save()
                messages.success(request, 'Cập nhật cài đặt IDE thành công!')
                return redirect('profile')
            else:
                p_form.data = p_form.data.copy()
                p_form.data['display_name'] = old_display_name
    else:
        p_form = ProfileUpdateForm(instance=profile)
        
    context = {
        'p_form': p_form,
        'session_id': session_id,
        'uni_id': uni_id
    }
    return render(request, 'compiler/profile.html', context)

def index_view(request):
    session_id = get_client_session(request)
    snippet_id = request.GET.get('snippet')
    code_content = None
    input_content = None
    language = None
    
    if snippet_id:
        try:
            snippet = CodeSnippet.objects.get(hash_id=snippet_id)
            if os.path.exists(snippet.file_path):
                with open(snippet.file_path, 'rb') as f:
                    compressed_code = f.read()
                code_content = zlib.decompress(compressed_code).decode('utf-8')
                input_content = snippet.input_text
                language = snippet.language
        except CodeSnippet.DoesNotExist:
            pass

    user_templates = []
    tpls = CodeTemplate.objects.filter(session_id=session_id)
    for t in tpls:
        user_templates.append({
            "name": t.name,
            "language": t.language,
            "code": t.code
        })

    profile, _ = Profile.objects.get_or_create(session_id=session_id)

    return render(request, 'compiler/index.html', {
        'snippet_code': code_content,
        'snippet_input': input_content,
        'snippet_lang': language,
        'user_templates': user_templates,
        'session_id': session_id,
        'profile': profile
    })

def report_view(request):
    session_id = get_client_session(request)
    profile, _ = Profile.objects.get_or_create(session_id=session_id)
    return render(request, 'compiler/report.html', {'session_id': session_id, 'profile': profile})

def view_snippet(request, hash_id):
    session_id = get_client_session(request)
    snippet = CodeSnippet.objects.filter(hash_id=hash_id).first()
    
    is_accessible = False
    if snippet:
        if snippet.is_public:
            is_accessible = True
        elif snippet.session_id == session_id:
            is_accessible = True

    if not is_accessible:
        class DummySnippet:
            def __init__(self, hid):
                self.hash_id = hid
                self.language = "htnt"
                self.created_at = datetime(2008, 4, 12, 0, 0, 0)
                self.title = "Code Private / Not Found"
                self.is_public = False
                self.input_text = ""
        
        profile, _ = Profile.objects.get_or_create(session_id=session_id)
        return render(request, 'compiler/review.html', {
            'snippet': DummySnippet(hash_id),
            'code_content': "// Đây là code private hoặc hoàn toàn không có link này",
            'session_id': session_id,
            'profile': profile
        })

    code_content = ""
    if os.path.exists(snippet.file_path):
        with open(snippet.file_path, 'rb') as f:
            compressed_code = f.read()
        code_content = zlib.decompress(compressed_code).decode('utf-8')
        
    profile, _ = Profile.objects.get_or_create(session_id=session_id)
    author_profile = Profile.objects.filter(session_id=snippet.session_id).first() if snippet.session_id else None

    return render(request, 'compiler/review.html', {
        'snippet': snippet,
        'code_content': code_content,
        'session_id': session_id,
        'profile': profile,
        'author_profile': author_profile
    })

@rate_limit(limit=10, window=60)
def save_snippet_api(request):
    if request.method == "POST":
        try:
            session_id = get_client_session(request)
            data = get_decrypted_data(request)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_text = data.get('inputs', '')
            if len(code) > 50000:
                return JsonResponse({"success": False, "error": "Code quá dài (tối đa 50KB)."})
            if len(input_text) > 10000:
                return JsonResponse({"success": False, "error": "Input quá dài (tối đa 10KB)."})
            
            existing_hash = data.get('hash_id')
            title = data.get('title', 'Không tên')
            is_public = data.get('is_public', True)
            
            if len(code) > 50000:
                return JsonResponse({"success": False, "error": "Code quá dài (tối đa 50KB)."})
            if len(input_text) > 10000:
                return JsonResponse({"success": False, "error": "Input quá dài (tối đa 10KB)."})
            if len(title) > 255:
                return JsonResponse({"success": False, "error": "Tiêu đề quá dài."})

            current_hash = hashlib.sha256(f"{language}|{input_text}|{code}".encode('utf-8')).hexdigest()
            
            snippet = None
            if existing_hash:
                try:
                    existing_snippet = CodeSnippet.objects.get(hash_id=existing_hash)
                    if existing_snippet.session_id == session_id:
                        snippet = existing_snippet
                except CodeSnippet.DoesNotExist:
                    pass
            
            if not snippet:
                existing_identical = CodeSnippet.objects.filter(content_hash=current_hash, session_id=session_id).first()
                if existing_identical:
                    if 'title' in data:
                        existing_identical.title = data['title']
                    if 'is_public' in data:
                        existing_identical.is_public = data['is_public']
                    existing_identical.save()
                    return JsonResponse({'success': True, 'hash_id': existing_identical.hash_id})

            if not snippet:
                snippet = CodeSnippet()
                snippet.hash_id = secrets.token_hex(4)
                snippet.session_id = session_id
                snippet.title = data.get('title', 'Không tên')
                snippet.is_public = data.get('is_public', True)
            else:
                if 'title' in data:
                    snippet.title = data['title']
                if 'is_public' in data:
                    snippet.is_public = data['is_public']
                
            snippet.language = language
            snippet.input_text = input_text
            snippet.content_hash = current_hash
            
            storage_dir = os.path.join(settings.BASE_DIR, 'storage', 'snippets')
            os.makedirs(storage_dir, exist_ok=True)
            
            file_path = os.path.join(storage_dir, f"{snippet.hash_id}.zlib")
            
            compressed_code = zlib.compress(code.encode('utf-8'))
            with open(file_path, 'wb') as f:
                f.write(compressed_code)
                
            snippet.file_path = file_path
            snippet.save()
            
            return JsonResponse({'success': True, 'hash_id': snippet.hash_id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@rate_limit(limit=5, window=10)
def visualize_api(request):
    if request.method == "POST":
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"CSRF Bypass Debug -> request.is_secure(): {request.is_secure()}")
        logger.error(f"CSRF Bypass Debug -> request.COOKIES: {request.COOKIES}")
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
                return JsonResponse({"error": "Input quá dài (tối đa 10KB).", "trace": [], "output": ""})

            from django.conf import settings
            from .tasks import trace_code_task
            task = trace_code_task.delay(code, language, inputs)
            
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                return JsonResponse({"status": "SUCCESS", "result": task.result})
                
            return JsonResponse({"task_id": str(task.id)})
            
        except Exception as e:
            return JsonResponse({"error": str(e), "trace": [], "output": ""}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

from celery.result import AsyncResult
def task_status_api(request, task_id):
    try:
        task = AsyncResult(task_id)
        if task.state == 'PENDING':
            return JsonResponse({"status": "PENDING"})
        elif task.state == 'SUCCESS':
            result = task.result
            if result is None:
                return JsonResponse({"status": "FAILURE", "error": "Lỗi hệ thống: Worker trả về None"})
            return JsonResponse({"status": "SUCCESS", "result": result})
        elif task.state == 'FAILURE':
            return JsonResponse({"status": "FAILURE", "error": str(task.info)})
        else:
            return JsonResponse({"status": task.state})
    except Exception as e:
        return JsonResponse({"status": "FAILURE", "error": str(e)})
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

def templates_api(request):
    session_id = get_client_session(request)
    if request.method == "GET":
        templates = CodeTemplate.objects.filter(session_id=session_id)
        data = []
        for t in templates:
            data.append({
                "id": t.id,
                "name": t.name,
                "language": t.language,
                "code": t.code
            })
        return JsonResponse({"templates": data})
        
    elif request.method == "POST":
        try:
            data = get_decrypted_data(request)
            name = data.get("name")
            language = data.get("language")
            code = data.get("code")
            
            if not name or not language or not code:
                return JsonResponse({"error": "Missing fields"}, status=400)
                
            template, created = CodeTemplate.objects.update_or_create(
                session_id=session_id,
                name=name,
                language=language,
                defaults={"code": code}
            )
            return JsonResponse({"success": True, "id": template.id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
    elif request.method == "DELETE":
        try:
            data = get_decrypted_data(request)
            t_id = data.get("id")
            CodeTemplate.objects.filter(id=t_id, session_id=session_id).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

def snippets_api(request):
    session_id = get_client_session(request)
    if request.method == "GET":
        snippets = CodeSnippet.objects.filter(session_id=session_id).order_by('-updated_at')
        data = []
        for s in snippets:
            data.append({
                "hash_id": s.hash_id,
                "title": s.title,
                "language": s.language,
                "is_public": s.is_public,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M")
            })
        return JsonResponse({"snippets": data})
        
    elif request.method == "PUT":
        try:
            data = get_decrypted_data(request)
            hash_id = data.get("hash_id")
            title = data.get("title")
            is_public = data.get("is_public")
            
            snippet = CodeSnippet.objects.get(hash_id=hash_id, session_id=session_id)
            if title is not None:
                snippet.title = title
            if is_public is not None:
                snippet.is_public = is_public
            snippet.save()
            return JsonResponse({"success": True})
        except CodeSnippet.DoesNotExist:
            return JsonResponse({"error": "Snippet not found or unauthorized"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "DELETE":
        try:
            data = get_decrypted_data(request)
            hash_id = data.get("hash_id")
            snippet = CodeSnippet.objects.get(hash_id=hash_id, session_id=session_id)
            if os.path.exists(snippet.file_path):
                os.remove(snippet.file_path)
            snippet.delete()
            return JsonResponse({"success": True})
        except CodeSnippet.DoesNotExist:
            return JsonResponse({"error": "Snippet not found or unauthorized"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

def save_keymap_api(request):
    if request.method == "POST":
        try:
            data = get_decrypted_data(request)
            keymap_data = data.get("keymap_data")
            name = data.get("name", "Custom Keymap")

            if not keymap_data:
                return JsonResponse({"error": "Missing keymap_data"}, status=400)

            keymap = KeymapTemplate()
            keymap.hash_id = secrets.token_hex(4)
            keymap.name = name
            keymap.keymap_data = keymap_data
            keymap.save()

            return JsonResponse({"success": True, "hash_id": keymap.hash_id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method not allowed"}, status=405)

def load_keymap_api(request, hash_id):
    if request.method == "GET":
        try:
            keymap = KeymapTemplate.objects.get(hash_id=hash_id)
            return JsonResponse({"success": True, "keymap_data": keymap.keymap_data, "name": keymap.name})
        except KeymapTemplate.DoesNotExist:
            return JsonResponse({"error": "Không tìm thấy Keymap với mã này"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method not allowed"}, status=405)