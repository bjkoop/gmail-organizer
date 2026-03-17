import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def _is_server_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except Exception:
        return False


def _ensure_dependencies(project_dir: Path) -> None:
    requirements = project_dir / "requirements.txt"
    if not requirements.exists():
        return

    try:
        import flask  # noqa: F401
        import googleapiclient  # noqa: F401
    except Exception:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            cwd=str(project_dir),
        )


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    app_file = project_dir / "app.py"
    url = "http://127.0.0.1:5000/"

    if not app_file.exists():
        print("Kon app.py niet vinden. Start dit script vanuit de projectmap.")
        return 1

    _ensure_dependencies(project_dir)

    process = subprocess.Popen([sys.executable, str(app_file)], cwd=str(project_dir))

    for _ in range(40):
        if _is_server_ready(url):
            webbrowser.open(url)
            break
        if process.poll() is not None:
            print("De server is onverwacht gestopt.")
            return process.returncode or 1
        time.sleep(0.5)

    print("Gmail Organizer draait. Sluit dit venster om te stoppen.")

    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
