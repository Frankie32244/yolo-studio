"""Double-click start.cmd: bootstrap once, then serve the bundled UI locally."""
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ is required; Python 3.11/3.12 is recommended.")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("frontend/dist is missing. Run npm install and npm run build in frontend first.")
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if Path(sys.prefix).resolve() != environment.resolve():
        if not python.is_file():
            print("[1/3] Preparing the local Python environment...", flush=True)
            subprocess.check_call([sys.executable, "-m", "venv", str(environment)])
        try:
            return subprocess.call([str(python), str(Path(__file__).resolve())])
        except KeyboardInterrupt:
            return 0

    requirements = ROOT / "backend/requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = environment / ".yolo-dependencies"
    if not stamp.exists() or stamp.read_text().strip() != fingerprint:
        print("[2/3] Installing dependencies. First launch needs Internet and may take several minutes...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
        stamp.write_text(fingerprint)

    # Use a free loopback port when another YOLO Studio instance already uses 8000.
    for port in range(8000, 8021):
        try:
            with socket.socket() as test:
                test.bind(("127.0.0.1", port))
            break
        except OSError:
            continue
    else:
        raise RuntimeError("No free local port in 8000-8020.")
    os.environ.setdefault("YOLO_MODEL", str(ROOT / "yolov8n.pt"))
    os.environ.setdefault("YOLO_DATA_DIR", str(ROOT / "data"))
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / ".yolo-config"))
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn

    url = f"http://127.0.0.1:{port}"
    def open_when_ready():
        for _ in range(120):
            try:
                with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except OSError:
                pass
            time.sleep(.5)
    threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"[3/3] YOLO Studio: {url}\nKeep this window open. Press Ctrl+C to stop.", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, workers=1)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
