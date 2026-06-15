import re

with open('compiler/views.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace is_safe_*
c = re.sub(r'def is_safe_python_code[\s\S]*?return None', 'def is_safe_python_code(code: str) -> str:\n    return None', c)
c = re.sub(r'def is_safe_cpp_code[\s\S]*?return None', 'def is_safe_cpp_code(code: str) -> str:\n    return None', c)

# Python tracing
c = c.replace(
'''            python_exe = "python" if os.name == 'nt' else "python3"
            subprocess.run(
                [python_exe, "tracer.py"], cwd=temp_dir, input=inputs, timeout=3,
                capture_output=True, text=True, env=get_safe_env(),
                preexec_fn=set_resource_limits if HAS_RESOURCE and os.name != 'nt' else None
            )''',
'''            subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "-v", f"{temp_dir}:/sandbox", "-i", "unicorns-python:latest", "python", "tracer.py"],
                cwd=temp_dir, input=inputs, timeout=5,
                capture_output=True, text=True
            )'''
)

# C++ compiling
c = c.replace(
'''        compile_process = subprocess.run(
            ["g++", "-g", "-O0", cpp_name, "-o", exe_name],
            cwd=temp_dir, capture_output=True, text=True, env=get_safe_env()
        )''',
'''        compile_process = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{temp_dir}:/sandbox", "unicorns-cpp:latest", "g++", "-g", "-O0", cpp_name, "-o", exe_name],
            cwd=temp_dir, capture_output=True, text=True
        )'''
)

# C++ running
c = c.replace(
'''        try:
            if HAS_RESOURCE and os.name != 'nt':
                try:
                    exec_process = subprocess.run(
                        ["/usr/bin/time", "-f", "%M", exe_path], cwd=temp_dir, input=inputs, timeout=2, 
                        capture_output=True, text=True, env=get_safe_env(), preexec_fn=set_resource_limits
                    )
                    if exec_process.stderr:
                        lines = exec_process.stderr.strip().split('\\n')
                        try:
                            memory_kb = float(lines[-1])
                            exec_process.stderr = '\\n'.join(lines[:-1]) 
                        except ValueError: pass
                except FileNotFoundError:
                    exec_process = subprocess.run([exe_path], cwd=temp_dir, input=inputs, timeout=2, env=get_safe_env(), capture_output=True, text=True, preexec_fn=set_resource_limits)
            else:
                exec_process = subprocess.run([exe_path], cwd=temp_dir, input=inputs, timeout=2, env=get_safe_env(), capture_output=True, text=True)
                
            end_time = time.perf_counter()
            time_ms = round((end_time - start_time) * 1000, 2)
        except subprocess.TimeoutExpired:''',
'''        try:
            exec_process = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "-v", f"{temp_dir}:/sandbox", "-i", "unicorns-cpp:latest", f"./{exe_name}"],
                cwd=temp_dir, input=inputs, timeout=3, capture_output=True, text=True
            )
            end_time = time.perf_counter()
            time_ms = round((end_time - start_time) * 1000, 2)
        except subprocess.TimeoutExpired:'''
)

# C++ trace compile
c = c.replace(
'''            trace_compile = subprocess.run(
                ["g++", "-g", "-O0", inst_cpp_name, "-o", inst_exe_name],
                cwd=temp_dir, capture_output=True, text=True, env=get_safe_env()
            )''',
'''            trace_compile = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "-v", f"{temp_dir}:/sandbox", "unicorns-cpp:latest", "g++", "-g", "-O0", inst_cpp_name, "-o", inst_exe_name],
                cwd=temp_dir, capture_output=True, text=True
            )'''
)

# C++ trace run
c = c.replace(
'''            if trace_compile.returncode == 0:
                subprocess.run(
                    [os.path.join(temp_dir, inst_exe_name)],
                    cwd=temp_dir, input=inputs, timeout=3, capture_output=True, text=True, env=get_safe_env()
                )''',
'''            if trace_compile.returncode == 0:
                subprocess.run(
                    ["docker", "run", "--rm", "--network", "none", "-v", f"{temp_dir}:/sandbox", "-i", "unicorns-cpp:latest", f"./{inst_exe_name}"],
                    cwd=temp_dir, input=inputs, timeout=5, capture_output=True, text=True
                )'''
)

with open('compiler/views.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("Replacement Complete")
