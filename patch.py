import pathlib
import json

p = pathlib.Path('compiler/views.py')
txt = p.read_text('utf-8')

# Inject get_sandbox_volume_name
patch = """import socket

SANDBOX_VOLUME_NAME = None
def get_sandbox_volume_name():
    global SANDBOX_VOLUME_NAME
    if SANDBOX_VOLUME_NAME: return SANDBOX_VOLUME_NAME
    try:
        cid = socket.gethostname()
        import subprocess
        import json
        out = subprocess.run(["docker", "inspect", cid, "--format", "{{json .Mounts}}"], capture_output=True, text=True).stdout
        mounts = json.loads(out)
        for m in mounts:
            if m.get("Destination") == "/sandbox_data":
                SANDBOX_VOLUME_NAME = m.get("Name")
                return SANDBOX_VOLUME_NAME
    except Exception:
        pass
    SANDBOX_VOLUME_NAME = "sandbox_data"
    return SANDBOX_VOLUME_NAME

SECRET_KEY_AES ="""

txt = txt.replace('SECRET_KEY_AES =', patch)
txt = txt.replace('unicorns_sandbox_data', '{get_sandbox_volume_name()}')

p.write_text(txt, 'utf-8')
