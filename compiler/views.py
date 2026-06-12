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
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Profile, CodeSnippet

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

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
    # Cấu hình môi trường an toàn và thư mục Temp cho cả Windows & Linux (Docker)
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

        tracer_script = """
import sys, io, json, traceback, time, tracemalloc, builtins

_stdin_content = sys.stdin.read()
sys.stdin = io.StringIO(_stdin_content)
_original_open = builtins.open

def _mock_open(file, mode='r', *args, **kwargs):
    allowed_system_files = ["main.py", "metrics.json", "trace.json", "output.txt", "error.txt", "error_line.txt"]
    if file in allowed_system_files:
        return _original_open(file, mode, *args, **kwargs)
    if 'r' in mode:
        return io.StringIO(_stdin_content)
    raise PermissionError("Bảo mật: Hệ thống không cho phép ghi file.")

builtins.open = _mock_open
tracemalloc.start()
start_time = time.perf_counter()

trace_log = []
output_buffer = io.StringIO()
error_msg = None

def trace_calls(frame, event, arg):
    if event in ('line', 'return') and frame.f_code.co_filename == 'main.py':
        locals_copy = {}
        for k, v in frame.f_locals.items():
            if not k.startswith('__') and not isinstance(v, type) and not str(type(v)).startswith("<class 'function'>") and not str(type(v)).startswith("<class 'module'>"):
                if isinstance(v, (int, float, str, bool)): locals_copy[k] = {"type": "prim", "val": repr(v)}
                elif isinstance(v, (list, tuple)): locals_copy[k] = {"type": "list", "val": [repr(x) for x in v]}
                elif isinstance(v, dict): locals_copy[k] = {"type": "dict", "val": {str(dk): repr(dv) for dk, dv in v.items()}}
                elif hasattr(v, '__dict__'):
                    attrs = {str(ak): repr(av) for ak, av in v.__dict__.items() if not str(ak).startswith('__')}
                    locals_copy[k] = {"type": "object", "class_name": v.__class__.__name__, "val": attrs}
                else: locals_copy[k] = {"type": "prim", "val": repr(v)}

        func_name = frame.f_code.co_name
        if func_name == '<module>': func_name = 'Global (Main)'
        trace_log.append({"line": frame.f_lineno, "func_name": func_name, "vars": locals_copy})
    return trace_calls

old_stdout = sys.stdout
sys.stdout = output_buffer

try:
    with open("main.py", "r", encoding="utf-8") as f:
        user_code = f.read()
    compiled_code = compile(user_code, 'main.py', 'exec')
    sys.settrace(trace_calls)
    exec(compiled_code, {"__name__": "__main__", "__file__": "main.py"})
except EOFError:
    error_msg = "Lỗi: Chương trình yêu cầu nhập dữ liệu (input) nhưng bạn chưa cung cấp đủ đầu vào."
except Exception as e:
    error_msg = traceback.format_exc().splitlines()[-1]
    tb = traceback.extract_tb(e.__traceback__)
    error_line = -1
    for frame in reversed(tb):
        if frame.filename == "main.py":
            error_line = frame.lineno
            break
    with open("error_line.txt", "w", encoding="utf-8") as f:
        f.write(str(error_line))
finally:
    sys.settrace(None)
    sys.stdout = old_stdout
    
end_time = time.perf_counter()
current, peak_memory = tracemalloc.get_traced_memory()
tracemalloc.stop()

metrics = {"time_ms": round((end_time - start_time) * 1000, 2), "memory_kb": round(peak_memory / 1024, 2)}
with open("metrics.json", "w", encoding="utf-8") as f: json.dump(metrics, f)
with open("trace.json", "w", encoding="utf-8") as f: json.dump(trace_log, f)
with open("output.txt", "w", encoding="utf-8") as f: f.write(output_buffer.getvalue())
if error_msg:
    with open("error.txt", "w", encoding="utf-8") as f: f.write(error_msg)
"""
        tracer_path = os.path.join(temp_dir, "tracer.py")
        with open(tracer_path, "w", encoding="utf-8") as f:
            f.write(tracer_script)

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
        
        user_words_json = json.dumps(list(set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', code))))
        
        gdb_script = f"""
import gdb, json, re

trace_log = []
user_code_words = set({user_words_json})

def get_user_global_vars():
    globals_list = []
    try:
        out = gdb.execute("info variables", to_string=True)
        is_in_main = False
        for line in out.split("\\n"):
            line = line.strip()
            if not line: continue
            if line.startswith("File main.cpp:"): is_in_main = True; continue
            elif line.startswith("File "): is_in_main = False; continue
            if is_in_main and line:
                idents = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', re.sub(r'\\[.*?\\]', '', line.replace(";", "").strip()))
                if idents and not idents[-1].startswith("_") and "@" not in idents[-1]:
                    g_name = idents[-1]
                    if g_name in user_code_words and g_name not in ["cin", "cout", "cerr", "endl", "main"]:
                        globals_list.append(g_name)
    except: pass
    return globals_list

try:
    gdb.execute("set disable-randomization off")
    gdb.execute("set confirm off")
    gdb.execute("set print pretty off")
    gdb.execute("set pagination off")
    gdb.execute("set max-value-size unlimited") 
    gdb.execute("set print elements 30")       
    gdb.execute("set print repeats 0")
    gdb.execute("break main")
    gdb.execute("run < input.txt > output.txt")

    user_globals = get_user_global_vars()

    while True:
        frame = gdb.selected_frame()
        if not frame: break
        sal = frame.find_sal()
        if not sal or not sal.symtab: break
        if "main.cpp" not in sal.symtab.filename:
            try: gdb.execute("finish"); continue
            except: break
                
        locals_dict = {{}}
        for g_name in user_globals:
            try:
                val_str = str(gdb.parse_and_eval(g_name)).strip()
                if val_str.startswith("{{") and val_str.endswith("}}"):
                    items = [x.strip() for x in val_str[1:-1].split(",") if x.strip()]
                    locals_dict[f"[Global] {{g_name}}"] = {{"type": "list", "val": items}}
                else:
                    locals_dict[f"[Global] {{g_name}}"] = {{"type": "prim", "val": val_str.split(" ")[0]}}
            except: pass
        
        try:
            block = frame.block()
            while block and not block.is_global and not block.is_static:
                for symbol in block:
                    if (symbol.is_variable or symbol.is_argument) and not symbol.name.startswith("_"):
                        if symbol.name in user_code_words and symbol.name not in ["cin", "cout", "cerr", "endl", "main"]:
                            try:
                                val = str(frame.read_var(symbol)).strip()
                                if val.startswith("{{") and val.endswith("}}"):
                                    items = [x.strip() for x in val.split("{{")[-1].replace("}}","").split(",") if x.strip()]
                                    locals_dict[symbol.name] = {{"type": "list", "val": items}}
                                else:
                                    locals_dict[symbol.name] = {{"type": "prim", "val": val.split(" ")[0]}}
                            except: pass
                block = block.superblock
        except: pass

        func_name = frame.name() if frame.name() else "main"
        trace_log.append({{"line": sal.line, "func_name": func_name, "vars": locals_dict}})
        gdb.execute("step")
except Exception: pass 
with open("trace.json", "w") as f: json.dump(trace_log, f)
"""
        with open(os.path.join(temp_dir, "gdb_script.py"), "w", encoding="utf-8") as f: f.write(gdb_script)

        try:
            gdb_process = subprocess.run(
                ["gdb", "-nx", "-q", "--batch", "-x", "gdb_script.py", exe_name],
                cwd=temp_dir, timeout=5, capture_output=True, text=True, env=get_safe_env()
            )
        except subprocess.TimeoutExpired:
            return {"trace": [], "output": "", "error": "Chương trình C++ kẹt vòng lặp hoặc chờ GDB xử lý quá lâu.", "time_ms": time_ms, "memory_kb": memory_kb}

        if "Python scripting is not supported" in gdb_process.stderr:
             return {"trace": [], "output": "", "error": "Bản MinGW/GDB hiện tại không hỗ trợ Python API.", "time_ms": time_ms, "memory_kb": memory_kb}

        trace_result, output_result = [], ""
        json_path = os.path.join(temp_dir, "trace.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                try: trace_result = json.load(f)
                except: pass
                
        output_txt_path = os.path.join(temp_dir, "output.txt")
        if os.path.exists(output_txt_path):
            with open(output_txt_path, "r", encoding="utf-8") as f: output_result = f.read()

        error_msg = "Không thu thập được dữ liệu mô phỏng. Code có thể lỗi hoặc bị giới hạn bộ nhớ." if not trace_result and not output_result else None

        return {
            "trace": trace_result, "output": output_result.replace("\\n", "\n"), "error": error_msg,
            "error_line": -1, "time_ms": time_ms, "memory_kb": memory_kb 
        }

# --- VIEW CỦA DJANGO ---

def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'compiler/register.html', {'form': form})

from .forms import UserProfileForm, ProfileUpdateForm
from .models import Profile
from django.contrib import messages

@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)
        
    if request.method == 'POST':
        u_form = UserProfileForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=profile)
        
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Cập nhật hồ sơ thành công!')
            return redirect('profile')
    else:
        u_form = UserProfileForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)
        
    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'compiler/profile.html', context)

@login_required
def index_view(request):
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
    if request.user.is_authenticated:
        from .models import CodeTemplate
        tpls = CodeTemplate.objects.filter(user=request.user)
        for t in tpls:
            user_templates.append({
                "name": t.name,
                "language": t.language,
                "code": t.code
            })

    return render(request, 'compiler/index.html', {
        'snippet_code': code_content,
        'snippet_input': input_content,
        'snippet_lang': language,
        'user_templates': user_templates
    })

@login_required
def report_view(request):
    return render(request, 'compiler/report.html')

from datetime import datetime

def view_snippet(request, hash_id):
    snippet = CodeSnippet.objects.filter(hash_id=hash_id).first()
    
    is_accessible = False
    if snippet:
        if snippet.is_public:
            is_accessible = True
        elif request.user.is_authenticated and snippet.author == request.user:
            is_accessible = True

    if not is_accessible:
        class DummySnippet:
            def __init__(self, hid):
                self.hash_id = hid
                self.language = "htnt"
                self.created_at = datetime(2008, 4, 12, 0, 0, 0)
                self.author = None
                self.title = "Code Private / Not Found"
                self.is_public = False
                self.input_text = ""
        
        return render(request, 'compiler/review.html', {
            'snippet': DummySnippet(hash_id),
            'code_content': "// Đây là code private hoặc hoàn toàn không có link này"
        })

    code_content = ""
    if os.path.exists(snippet.file_path):
        with open(snippet.file_path, 'rb') as f:
            compressed_code = f.read()
        code_content = zlib.decompress(compressed_code).decode('utf-8')
        
    return render(request, 'compiler/review.html', {
        'snippet': snippet,
        'code_content': code_content
    })

@csrf_exempt
def save_snippet_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '')
            language = data.get('language', 'python')
            input_text = data.get('inputs', '')
            existing_hash = data.get('hash_id')
            title = data.get('title', 'Không tên')
            is_public = data.get('is_public', True)

            current_hash = hashlib.sha256(f"{language}|{input_text}|{code}".encode('utf-8')).hexdigest()
            user = request.user if request.user.is_authenticated else None
            
            snippet = None
            if existing_hash and user:
                try:
                    existing_snippet = CodeSnippet.objects.get(hash_id=existing_hash)
                    if existing_snippet.author == user:
                        snippet = existing_snippet
                except CodeSnippet.DoesNotExist:
                    pass
            
            # Nếu người dùng này đã lưu chính xác đoạn code này trước đó và không cố tình update snippet cụ thể
            if not snippet:
                existing_identical = CodeSnippet.objects.filter(content_hash=current_hash, author=user).first()
                if existing_identical:
                    # Cập nhật title/quyền nếu họ truyền lên khác mặc định
                    if 'title' in data:
                        existing_identical.title = data['title']
                    if 'is_public' in data:
                        existing_identical.is_public = data['is_public']
                    existing_identical.save()
                    return JsonResponse({'success': True, 'hash_id': existing_identical.hash_id})

            if not snippet:
                snippet = CodeSnippet()
                snippet.hash_id = secrets.token_hex(4)
                snippet.author = user
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

            if language == "python":
                result = trace_python(code, inputs)
            elif language == "cpp":
                result = trace_cpp(code, inputs)
            else:
                return JsonResponse({"error": "Ngôn ngữ không được hỗ trợ", "trace": [], "output": ""}, status=400)

            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({"error": str(e), "trace": [], "output": ""}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
@csrf_exempt
def templates_api(request):
    from .models import CodeTemplate
    
    if request.method == "GET":
        templates = CodeTemplate.objects.filter(user=request.user)
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
                user=request.user,
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
            CodeTemplate.objects.filter(id=t_id, user=request.user).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
@csrf_exempt
def snippets_api(request):
    if request.method == "GET":
        snippets = CodeSnippet.objects.filter(author=request.user).order_by('-updated_at')
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
            
            snippet = CodeSnippet.objects.get(hash_id=hash_id, author=request.user)
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
            snippet = CodeSnippet.objects.get(hash_id=hash_id, author=request.user)
            if os.path.exists(snippet.file_path):
                os.remove(snippet.file_path)
            snippet.delete()
            return JsonResponse({"success": True})
        except CodeSnippet.DoesNotExist:
            return JsonResponse({"error": "Snippet not found or unauthorized"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)