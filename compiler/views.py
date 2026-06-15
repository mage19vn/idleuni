import os
import sys
import io
import tempfile
import subprocess
import json
import time
import re
import ast
import zlib
import secrets
import hashlib
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
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

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_safe_python_code(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "Lỗi cú pháp Python."

    forbidden_modules = {'os', 'sys', 'subprocess', 'pty', 'socket', 'urllib', 'requests', 'importlib', 'builtins'}
    forbidden_functions = {'eval', 'exec', 'open', '__import__', 'compile', 'globals', 'locals', 'getattr', 'setattr', 'delattr'}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in forbidden_modules:
                    return f"Bảo mật: Không được phép import module '{alias.name}'"

        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in forbidden_modules:
                return f"Bảo mật: Không được phép import từ module '{node.module}'"

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in forbidden_functions:
                    return f"Bảo mật: Không được phép sử dụng hàm '{node.func.id}()'"
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_functions:
                    return f"Bảo mật: Không được phép gọi thuộc tính hoặc hàm '{node.func.attr}'"
    return None

def is_safe_cpp_code(code: str) -> str:
    code_no_comments = re.sub(r'//.*|/\*[\s\S]*?\*/', '', code)
    forbidden_patterns = [
        r'#include\s*[<"]\s*cstdlib\s*[>"]', 
        r'#include\s*[<"]\s*stdlib\.h\s*[>"]',
        r'#include\s*[<"]\s*unistd\.h\s*[>"]', 
        r'#include\s*[<"]\s*windows\.h\s*[>"]',
        r'#include\s*[<"]\s*sys/socket\.h\s*[>"]', 
        r'#include\s*[<"]\s*fstream\s*[>"]',
        r'\bsystem\s*\(', r'\bpopen\s*\(', r'\bfork\s*\(', r'\bexec\w*\s*\(',
        r'\bremove\s*\(', r'\brename\s*\('
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, code_no_comments, re.IGNORECASE):
            return "Bảo mật: Mã C++ chứa thư viện/lệnh không an toàn (vd: system(), file I/O)."
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
    
    with tempfile.TemporaryDirectory() as temp_dir:
        user_code_path = os.path.join(temp_dir, "main.py")
        with open(user_code_path, "w", encoding="utf-8") as f:
            f.write(code)

        import shutil
        tracer_source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "python_tracer.py")
        tracer_path = os.path.join(temp_dir, "tracer.py")
        shutil.copy2(tracer_source_path, tracer_path)

        try:
            python_exe = "python" if os.name == 'nt' else "python3"
            subprocess.run(
                [python_exe, "tracer.py"], cwd=temp_dir, input=inputs, timeout=3,
                capture_output=True, text=True, env=get_safe_env(),
                preexec_fn=set_resource_limits if HAS_RESOURCE and os.name != 'nt' else None
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

    with tempfile.TemporaryDirectory() as temp_dir:
        exe_name = "main.exe" if os.name == 'nt' else "main.out"
        cpp_name = "main.cpp"
        
        with open(os.path.join(temp_dir, cpp_name), "w", encoding="utf-8") as f: f.write(code)
        with open(os.path.join(temp_dir, "input.txt"), "w", encoding="utf-8") as f: f.write(inputs)

        compile_process = subprocess.run(
            ["g++", "-g", "-O0", cpp_name, "-o", exe_name],
            cwd=temp_dir, capture_output=True, text=True, env=get_safe_env()
        )
        
        if compile_process.returncode != 0:
            err_line = -1
            match = re.search(r'main\.cpp:(\d+):', compile_process.stderr)
            if match: err_line = int(match.group(1))
            return {"trace": [], "output": "", "error": "Lỗi biên dịch:\n" + compile_process.stderr, "error_line": err_line, "time_ms": 0.0, "memory_kb": 0.0}

        time_ms, memory_kb, exe_path = 0.0, 0.0, os.path.join(temp_dir, exe_name)
        start_time = time.perf_counter()
        
        try:
            if HAS_RESOURCE and os.name != 'nt':
                try:
                    exec_process = subprocess.run(
                        ["/usr/bin/time", "-f", "%M", exe_path], cwd=temp_dir, input=inputs, timeout=2, 
                        capture_output=True, text=True, env=get_safe_env(), preexec_fn=set_resource_limits
                    )
                    if exec_process.stderr:
                        lines = exec_process.stderr.strip().split('\n')
                        try:
                            memory_kb = float(lines[-1])
                            exec_process.stderr = '\n'.join(lines[:-1]) 
                        except ValueError: pass
                except FileNotFoundError:
                    exec_process = subprocess.run([exe_path], cwd=temp_dir, input=inputs, timeout=2, env=get_safe_env(), capture_output=True, text=True, preexec_fn=set_resource_limits)
            else:
                exec_process = subprocess.run([exe_path], cwd=temp_dir, input=inputs, timeout=2, env=get_safe_env(), capture_output=True, text=True)
                
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
                
            trace_compile = subprocess.run(
                ["g++", "-g", "-O0", inst_cpp_name, "-o", inst_exe_name],
                cwd=temp_dir, capture_output=True, text=True, env=get_safe_env()
            )
            
            if trace_compile.returncode == 0:
                subprocess.run(
                    [os.path.join(temp_dir, inst_exe_name)],
                    cwd=temp_dir, input=inputs, timeout=3, capture_output=True, text=True, env=get_safe_env()
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
    ip = get_client_ip(request)
    profile, created = Profile.objects.get_or_create(ip_address=ip)
        
    if request.method == 'POST':
        p_form = ProfileUpdateForm(request.POST, instance=profile)
        if p_form.is_valid():
            p_form.save()
            messages.success(request, 'Cập nhật hồ sơ thành công!')
            return redirect('profile')
    else:
        p_form = ProfileUpdateForm(instance=profile)
        
    context = {
        'p_form': p_form,
        'ip_address': ip
    }
    return render(request, 'compiler/profile.html', context)

def index_view(request):
    ip = get_client_ip(request)
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
    tpls = CodeTemplate.objects.filter(author_ip=ip)
    for t in tpls:
        user_templates.append({
            "name": t.name,
            "language": t.language,
            "code": t.code
        })

    profile, _ = Profile.objects.get_or_create(ip_address=ip)

    return render(request, 'compiler/index.html', {
        'snippet_code': code_content,
        'snippet_input': input_content,
        'snippet_lang': language,
        'user_templates': user_templates,
        'ip_address': ip,
        'profile': profile
    })

def report_view(request):
    ip = get_client_ip(request)
    profile, _ = Profile.objects.get_or_create(ip_address=ip)
    return render(request, 'compiler/report.html', {'ip_address': ip, 'profile': profile})

def view_snippet(request, hash_id):
    ip = get_client_ip(request)
    snippet = CodeSnippet.objects.filter(hash_id=hash_id).first()
    
    is_accessible = False
    if snippet:
        if snippet.is_public:
            is_accessible = True
        elif snippet.author_ip == ip:
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
        
        profile, _ = Profile.objects.get_or_create(ip_address=ip)
        return render(request, 'compiler/review.html', {
            'snippet': DummySnippet(hash_id),
            'code_content': "// Đây là code private hoặc hoàn toàn không có link này",
            'ip_address': ip,
            'profile': profile
        })

    code_content = ""
    if os.path.exists(snippet.file_path):
        with open(snippet.file_path, 'rb') as f:
            compressed_code = f.read()
        code_content = zlib.decompress(compressed_code).decode('utf-8')
        
    profile, _ = Profile.objects.get_or_create(ip_address=ip)
    author_profile = Profile.objects.filter(ip_address=snippet.author_ip).first() if snippet.author_ip else None

    return render(request, 'compiler/review.html', {
        'snippet': snippet,
        'code_content': code_content,
        'ip_address': ip,
        'profile': profile,
        'author_profile': author_profile
    })

@csrf_exempt
def save_snippet_api(request):
    if request.method == "POST":
        try:
            ip = get_client_ip(request)
            data = json.loads(request.body)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_text = data.get('inputs', '')
            existing_hash = data.get('hash_id')
            title = data.get('title', 'Không tên')
            is_public = data.get('is_public', True)

            current_hash = hashlib.sha256(f"{language}|{input_text}|{code}".encode('utf-8')).hexdigest()
            
            snippet = None
            if existing_hash:
                try:
                    existing_snippet = CodeSnippet.objects.get(hash_id=existing_hash)
                    if existing_snippet.author_ip == ip:
                        snippet = existing_snippet
                except CodeSnippet.DoesNotExist:
                    pass
            
            if not snippet:
                existing_identical = CodeSnippet.objects.filter(content_hash=current_hash, author_ip=ip).first()
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
                snippet.author_ip = ip
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

@csrf_exempt 
def visualize_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            language = data.get("language")
            code = data.get("code")
            inputs = data.get("inputs", "")

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
@csrf_exempt
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

@csrf_exempt
def templates_api(request):
    ip = get_client_ip(request)
    if request.method == "GET":
        templates = CodeTemplate.objects.filter(author_ip=ip)
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
            data = json.loads(request.body)
            name = data.get("name")
            language = data.get("language")
            code = data.get("code")
            
            if not name or not language or not code:
                return JsonResponse({"error": "Missing fields"}, status=400)
                
            template, created = CodeTemplate.objects.update_or_create(
                author_ip=ip,
                name=name,
                language=language,
                defaults={"code": code}
            )
            return JsonResponse({"success": True, "id": template.id})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
    elif request.method == "DELETE":
        try:
            data = json.loads(request.body)
            t_id = data.get("id")
            CodeTemplate.objects.filter(id=t_id, author_ip=ip).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def snippets_api(request):
    ip = get_client_ip(request)
    if request.method == "GET":
        snippets = CodeSnippet.objects.filter(author_ip=ip).order_by('-updated_at')
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
            data = json.loads(request.body)
            hash_id = data.get("hash_id")
            title = data.get("title")
            is_public = data.get("is_public")
            
            snippet = CodeSnippet.objects.get(hash_id=hash_id, author_ip=ip)
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
            data = json.loads(request.body)
            hash_id = data.get("hash_id")
            snippet = CodeSnippet.objects.get(hash_id=hash_id, author_ip=ip)
            if os.path.exists(snippet.file_path):
                os.remove(snippet.file_path)
            snippet.delete()
            return JsonResponse({"success": True})
        except CodeSnippet.DoesNotExist:
            return JsonResponse({"error": "Snippet not found or unauthorized"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def save_keymap_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
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

@csrf_exempt
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