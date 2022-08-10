import importlib
import os

for backend in os.listdir(os.path.dirname(__file__)):
    full_path = os.path.join(os.path.dirname(__file__), backend)
    if os.path.isdir(full_path) and "__pycache__" not in backend and os.path.exists(os.path.join(full_path, f"{backend}_backend.py")):
        importlib.import_module(f"octo_pipeline_python.backends.{backend}.{backend}_backend")
