"""FastAPI-Server, der die Coach-CLI pro Sitzung in einer PTY bereitstellt.

Architektur (bewusst schlank, ein vertikaler MVP wie die CLI selbst):

    Browser (xterm.js)  ──WebSocket──▶  dieser Server  ──PTY──▶  `python -m ki_bewerbungs_coach`

* Jede WebSocket-Verbindung startet einen eigenen Kindprozess in einer
  eigenen Pseudo-TTY und einem eigenen temporären Arbeitsverzeichnis.
* Es wird ausschließlich das feste Coach-Modul gestartet – keine Shell.
  Dadurch kann ein Besucher keine beliebigen Befehle ausführen.
* Ressourcenschutz: begrenzte gleichzeitige Sitzungen, Idle-Timeout und
  hartes Sitzungslimit. Bei einer kostenlosen Modell-Konfiguration (z. B.
  OpenRouter :free) entsteht dadurch keine Kostenfalle.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

# PTY-Bausteine sind Unix-only. Import bewusst hier, damit ein Import des
# Moduls auf einem Nicht-Unix-System eine verständliche Meldung erzeugt.
try:
    import fcntl
    import pty
    import struct
    import termios
except ImportError as exc:  # pragma: no cover - nur auf Nicht-Unix relevant
    raise RuntimeError(
        "Die Web-Terminal-Schicht benötigt eine Unix-PTY (Linux/macOS). "
        "Für Windows bitte im Docker-Container betreiben."
    ) from exc


# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


HOST = os.getenv("WEB_HOST", "0.0.0.0")
PORT = _int_env("WEB_PORT", 8000)
MAX_SESSIONS = max(1, _int_env("WEB_MAX_SESSIONS", 5))
IDLE_TIMEOUT_SECONDS = max(30, _int_env("WEB_IDLE_TIMEOUT_SECONDS", 300))
MAX_SESSION_SECONDS = max(60, _int_env("WEB_MAX_SESSION_SECONDS", 1800))
DEFAULT_COLS = max(20, _int_env("WEB_DEFAULT_COLS", 100))
DEFAULT_ROWS = max(10, _int_env("WEB_DEFAULT_ROWS", 32))

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="KI Bewerbungs Coach – Web")

# Statische Assets (u. a. der mitgelieferte Monospace-Font für ein
# browserunabhängiges Rendering des Maskottchens).
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------- #
# Sitzungszähler (einfacher Concurrency-Schutz)
# --------------------------------------------------------------------------- #

_active_sessions = 0
_sessions_lock = asyncio.Lock()


async def _acquire_slot() -> bool:
    global _active_sessions
    async with _sessions_lock:
        if _active_sessions >= MAX_SESSIONS:
            return False
        _active_sessions += 1
        return True


async def _release_slot() -> None:
    global _active_sessions
    async with _sessions_lock:
        _active_sessions = max(0, _active_sessions - 1)


# --------------------------------------------------------------------------- #
# PTY-Hilfen
# --------------------------------------------------------------------------- #

def _set_winsize(fd: int, rows: int, cols: int) -> None:
    """Setzt die Fenstergröße der PTY, damit `rich` korrekt umbricht."""
    rows = max(10, min(rows, 200))
    cols = max(20, min(cols, 400))
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass


def _child_environment(session_dir: Path, rows: int, cols: int) -> dict[str, str]:
    """Erbt die Prozessumgebung (Modell-/Providervariablen) und ergänzt TTY-Infos."""
    env = dict(os.environ)
    env.update(
        {
            "TERM": "xterm-256color",
            "COLUMNS": str(cols),
            "LINES": str(rows),
            "PYTHONUNBUFFERED": "1",
            # Ergebnisdatei bleibt in der ephemeren Sitzung; nichts wird persistiert.
            "OUTPUT_FILE": "bewerbung_output.md",
            # `.env` im Sitzungsverzeichnis vermeiden: Konfiguration kommt aus echten Env-Vars.
        }
    )
    env.pop("PWD", None)
    return env


# --------------------------------------------------------------------------- #
# Routen
# --------------------------------------------------------------------------- #

@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def terminal_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    if not await _acquire_slot():
        await websocket.send_bytes(
            "\r\n  Aktuell sind alle Demo-Plätze belegt. "
            "Bitte in ein paar Minuten erneut versuchen.\r\n".encode("utf-8")
        )
        await websocket.close()
        return

    session_dir = Path(tempfile.mkdtemp(prefix="coach-session-"))
    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, DEFAULT_ROWS, DEFAULT_COLS)

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "ki_bewerbungs_coach",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        start_new_session=True,
        cwd=str(session_dir),
        env=_child_environment(session_dir, DEFAULT_ROWS, DEFAULT_COLS),
    )
    os.close(slave_fd)

    loop = asyncio.get_running_loop()
    output_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    state = {"last_input": time.monotonic(), "started": time.monotonic()}

    def _on_master_readable() -> None:
        try:
            data = os.read(master_fd, 65536)
        except OSError:
            data = b""
        if data:
            output_queue.put_nowait(data)
        else:
            try:
                loop.remove_reader(master_fd)
            except (ValueError, OSError):
                pass
            output_queue.put_nowait(None)

    loop.add_reader(master_fd, _on_master_readable)

    async def pump_output() -> None:
        while True:
            chunk = await output_queue.get()
            if chunk is None:
                return
            try:
                await websocket.send_bytes(chunk)
            except (WebSocketDisconnect, RuntimeError):
                return

    async def pump_input() -> None:
        while True:
            try:
                raw = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                # RuntimeError: Empfang nach bereits erfolgtem Disconnect.
                return
            try:
                message = json.loads(raw)
            except (ValueError, TypeError):
                continue
            kind = message.get("type")
            if kind == "stdin":
                state["last_input"] = time.monotonic()
                data = str(message.get("data", ""))
                try:
                    os.write(master_fd, data.encode("utf-8"))
                except OSError:
                    return
            elif kind == "resize":
                _set_winsize(
                    master_fd,
                    int(message.get("rows", DEFAULT_ROWS)),
                    int(message.get("cols", DEFAULT_COLS)),
                )

    async def watchdog() -> None:
        while True:
            await asyncio.sleep(5)
            now = time.monotonic()
            if now - state["last_input"] > IDLE_TIMEOUT_SECONDS:
                await _notify(websocket, "\r\n  Sitzung wegen Inaktivität beendet.\r\n")
                return
            if now - state["started"] > MAX_SESSION_SECONDS:
                await _notify(websocket, "\r\n  Maximale Sitzungsdauer erreicht.\r\n")
                return

    tasks = [
        asyncio.create_task(pump_output()),
        asyncio.create_task(pump_input()),
        asyncio.create_task(watchdog()),
        asyncio.create_task(proc.wait()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        _terminate_process(proc)
        try:
            loop.remove_reader(master_fd)
        except (ValueError, OSError):
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        shutil.rmtree(session_dir, ignore_errors=True)
        await _release_slot()
        try:
            await websocket.close()
        except RuntimeError:
            pass


async def _notify(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_bytes(message.encode("utf-8"))
    except (WebSocketDisconnect, RuntimeError):
        pass


def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    """Beendet den Kindprozess samt Prozessgruppe robust."""
    if proc.returncode is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.terminate()
        except ProcessLookupError:
            return
    # Kurze Nachfrist, dann hart beenden.
    for _ in range(20):
        if proc.returncode is not None:
            return
        time.sleep(0.05)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def run() -> None:
    """Entry-Point für `ki-bewerbungs-coach-web` / `python -m ki_bewerbungs_coach.web`."""
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level=os.getenv("WEB_LOG_LEVEL", "info"))
