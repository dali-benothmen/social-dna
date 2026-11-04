import os
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass
from typing import BinaryIO

from socialdna.core.exceptions import DependencyUnavailable, MediaProcessingError


@dataclass(frozen=True)
class ProcessOutput:
    stdout: str
    stderr: str


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise DependencyUnavailable(
            f"{name} is required for local media analysis but was not found.",
            next_action="Install FFmpeg/ffprobe using your OS package manager, then retry.",
        )
    return executable


def run_process(
    arguments: list[str],
    *,
    timeout: float = 300,
    stdout_limit: int = 16_000_000,
    stderr_limit: int = 64_000,
) -> ProcessOutput:
    """Drain both pipes with bounded memory, kill the child on timeout or cancellation."""
    try:
        process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        raise MediaProcessingError(f"Cannot start media tool: {exc}") from exc
    stdout, stderr = bytearray(), bytearray()
    overflow = threading.Event()

    def stop() -> None:
        try:
            if os.name == "posix":
                # Descendants can retain pipes even after the direct child exits.
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except ProcessLookupError:
            pass

    def drain(stream: BinaryIO, buffer: bytearray, limit: int, tail: bool) -> None:
        try:
            while chunk := stream.read(8192):
                buffer.extend(chunk)
                if len(buffer) > limit:
                    if tail:
                        del buffer[:-limit]
                    else:
                        del buffer[limit:]
                        overflow.set()
                        stop()
        finally:
            stream.close()

    assert process.stdout is not None and process.stderr is not None
    readers = [
        threading.Thread(target=drain, args=(process.stdout, stdout, stdout_limit, False)),
        threading.Thread(target=drain, args=(process.stderr, stderr, stderr_limit, True)),
    ]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stop()
        raise MediaProcessingError(f"Media tool exceeded its {timeout:g}-second timeout.") from exc
    finally:
        stop()
        process.wait()
        for reader in readers:
            reader.join()
    result = ProcessOutput(
        stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
    )
    if overflow.is_set():
        raise MediaProcessingError("Media tool output exceeded its configured size limit.")
    if process.returncode:
        raise MediaProcessingError(
            f"Media tool failed (exit {process.returncode}): " + result.stderr[-4000:]
        )
    return result


def tool_version(name: str) -> str:
    result = run_process([require_tool(name), "-version"], timeout=10)
    return result.stdout.splitlines()[0]
