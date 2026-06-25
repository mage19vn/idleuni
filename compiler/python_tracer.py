import sys
import trace
import traceback
import json
import io
import time
import builtins
import os
import tracemalloc

# Chặn import os, sys (Sandbox nhẹ ở mức độ interpreter)
def safe_import(name, *args, **kwargs):
    if name in ['os', 'sys', 'subprocess', 'shutil', 'socket']:
        raise ImportError(f"Bảo mật: Không cho phép import thư viện '{name}'")
    return __import__(name, *args, **kwargs)

builtins.__import__ = safe_import

_stdin_content = sys.stdin.read()
sys.stdin = io.StringIO(_stdin_content)

_original_open = builtins.open
def safe_open(file, mode='r', *args, **kwargs):
    allowed_system_files = ['main.py', 'input.txt', 'output.txt', 'error.txt', 'error_line.txt', 'trace.json', 'metrics.json']
    if file in allowed_system_files:
        return _original_open(file, mode, *args, **kwargs)
    if 'r' in mode:
        return io.StringIO(_stdin_content)
    raise PermissionError("Bảo mật: Hệ thống không cho phép ghi file tùy ý.")
builtins.open = safe_open

tracemalloc.start()
start_time = time.perf_counter()

trace_log = []
output_buffer = io.StringIO()
error_msg = None

MAX_ITEMS = 100
MAX_STEPS = 5000

def trim_value(v):
    try:
        if isinstance(v, (int, float, str, bool)):
            s = repr(v)
            if len(s) > 200: return {"type": "prim", "val": s[:100] + " ... [truncated] ... " + s[-100:]}
            return {"type": "prim", "val": s}
        elif isinstance(v, (list, tuple)):
            if len(v) > MAX_ITEMS:
                arr = [repr(x) for x in v[:MAX_ITEMS//2]] + ["... [Bị cắt bớt do quá dài] ..."] + [repr(x) for x in v[-MAX_ITEMS//2:]]
                return {"type": "list", "val": arr}
            return {"type": "list", "val": [repr(x) for x in v]}
        elif isinstance(v, dict):
            if len(v) > MAX_ITEMS:
                d = {str(dk): repr(dv) for i, (dk, dv) in enumerate(v.items()) if i < MAX_ITEMS//2 or i >= len(v) - MAX_ITEMS//2}
                d["..."] = "[truncated]"
                return {"type": "dict", "val": d}
            return {"type": "dict", "val": {str(dk): repr(dv) for dk, dv in v.items()}}
        elif hasattr(v, '__dict__'):
            attrs = {str(ak): repr(av) for ak, av in v.__dict__.items() if not str(ak).startswith('__')}
            return {"type": "object", "class_name": getattr(v.__class__, '__name__', 'Object'), "val": attrs}
        else:
            return {"type": "prim", "val": repr(v)}
    except Exception:
        return {"type": "prim", "val": "<unrepresentable>"}

def trace_calls(frame, event, arg):
    if len(trace_log) >= MAX_STEPS:
        trace_log.append({"line": frame.f_lineno, "func_name": "Hệ Thống", "vars": {"CẢNH BÁO": {"type": "prim", "val": "Vượt quá 5000 bước lặp. Visualizer tự động dừng để chống tràn bộ nhớ."}}})
        sys.settrace(None)
        return None
        
    if event in ('line', 'return'):
        # CHỈ BẮT CODE TỪ main.py ĐỂ TRÁNH TRACE HỆ THỐNG
        if frame.f_code.co_filename != 'main.py':
            return trace_calls

        locals_copy = {}
        for k, v in frame.f_globals.items():
            if not k.startswith('__') and not isinstance(v, type) and not str(type(v)).startswith("<class 'function'>") and not str(type(v)).startswith("<class 'module'>"):
                locals_copy[f"[Global] {k}"] = trim_value(v)
                
        if frame.f_locals is not frame.f_globals:
            for k, v in frame.f_locals.items():
                if not k.startswith('__') and not isinstance(v, type) and not str(type(v)).startswith("<class 'function'>") and not str(type(v)).startswith("<class 'module'>"):
                    locals_copy[k] = trim_value(v)

        func_name = frame.f_code.co_name
        if func_name == '<module>': func_name = 'Global (Main)'
        trace_log.append({"line": frame.f_lineno, "func_name": func_name, "vars": locals_copy})
    return trace_calls

old_stdout = sys.stdout
sys.stdout = output_buffer

try:
    with _original_open("main.py", "r", encoding="utf-8") as f:
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
    with _original_open("error_line.txt", "w", encoding="utf-8") as f:
        f.write(str(error_line))
finally:
    sys.settrace(None)
    sys.stdout = old_stdout
    
end_time = time.perf_counter()
current, peak_memory = tracemalloc.get_traced_memory()
tracemalloc.stop()

if len(trace_log) >= MAX_STEPS:
    error_msg = f"Cảnh báo: Chương trình đã chạy vượt quá {MAX_STEPS} bước lặp. Visualizer bị dừng lại để bảo vệ hệ thống."

metrics = {"time_ms": round((end_time - start_time) * 1000, 2), "memory_kb": round(peak_memory / 1024, 2)}
with _original_open("metrics.json", "w", encoding="utf-8") as f: json.dump(metrics, f)
with _original_open("trace.json", "w", encoding="utf-8") as f: json.dump(trace_log, f)
with _original_open("output.txt", "w", encoding="utf-8") as f: f.write(output_buffer.getvalue())
if error_msg:
    with _original_open("error.txt", "w", encoding="utf-8") as f: f.write(error_msg)
