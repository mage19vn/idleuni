import json
from celery import shared_task
from . import views

@shared_task(bind=True)
def trace_code_task(self, code, language, inputs):
    try:
        if language == "python":
            result = views.trace_python(code, inputs)
        elif language == "cpp":
            result = views.trace_cpp(code, inputs)
        else:
            return {"error": "Ngôn ngữ không được hỗ trợ", "trace": [], "output": ""}
            
        return result
    except Exception as e:
        return {"error": str(e), "trace": [], "output": ""}
