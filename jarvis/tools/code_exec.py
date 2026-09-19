import subprocess
import sys
import tempfile
import os
import yaml
from pathlib import Path

from jarvis.config_runtime import load_config as _runtime_load_config

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"

def _load_config():
    return _runtime_load_config()

def run_python(code: str) -> str:
    """Execute Python code in a subprocess sandbox. Returns stdout/stderr."""
    timeout = _load_config()["tools"]["code_timeout"]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        fname = f.name
    try:
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Code execution timed out after {timeout}s."
    except Exception as e:
        return f"Execution error: {e}"
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass
