"""local-runtime'ı subprocess ile çağırır — route kararı "local" olduğunda."""
import json
import subprocess

LOCAL_RUNTIME_CMD = ["python3", "-m", "local_runtime"]


def call_local_runtime(prompt: str, cwd: str | None = None) -> dict:
    result = subprocess.run(
        LOCAL_RUNTIME_CMD + ["--prompt", prompt],
        cwd=cwd, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)
