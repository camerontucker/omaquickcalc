#!/usr/bin/env python3
"""Read plain-text paste only on explicit request, outside the shell process."""
from __future__ import annotations

import argparse
import json
import os
import resource
import selectors
import subprocess
import sys
from time import monotonic

MAX_BYTES = 16 * 1024
MAX_STDERR = 4096
MAX_READER_MEMORY = 128 * 1024 * 1024
MAX_CHARACTERS = 4096
TIMEOUT_SECONDS = 1.0


class PasteError(Exception):
    pass


def limit_reader_memory() -> None:
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    ceiling = MAX_READER_MEMORY
    if hard != resource.RLIM_INFINITY:
        ceiling = min(ceiling, hard)
    if soft != resource.RLIM_INFINITY:
        ceiling = min(ceiling, soft)
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, hard))


def read_bounded(command: list[str], deadline: float, limit: int) -> bytes:
    if monotonic() >= deadline:
        raise PasteError("Clipboard request timed out")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               preexec_fn=limit_reader_memory)
    selector = selectors.DefaultSelector()
    buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
    try:
        for stream in buffers:
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise PasteError("Clipboard request timed out")
            for key, _ in selector.select(remaining):
                stream = key.fileobj
                maximum = limit if stream is process.stdout else MAX_STDERR
                chunk = os.read(stream.fileno(), min(4096, maximum - len(buffers[stream]) + 1))
                if not chunk:
                    selector.unregister(stream)
                    continue
                buffers[stream].extend(chunk)
                if len(buffers[stream]) > maximum:
                    raise PasteError("Clipboard offer is too large")
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise PasteError("Clipboard request timed out")
        try:
            status = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            raise PasteError("Clipboard request timed out") from error
        if status != 0:
            raise PasteError("Clipboard text is unavailable")
        return bytes(buffers[process.stdout])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        selector.close()
        process.stdout.close()
        process.stderr.close()


def read_paste(primary: bool = False, maximum: int = MAX_CHARACTERS) -> str:
    if not 0 <= maximum <= MAX_CHARACTERS:
        raise PasteError("Invalid paste capacity")
    deadline = monotonic() + TIMEOUT_SECONDS
    command = ["wl-paste", "--no-newline"]
    if primary:
        command.append("--primary")
    types = read_bounded(command + ["--list-types"], deadline, MAX_STDERR).decode("utf-8", errors="strict").splitlines()
    mime = next((kind for kind in ("text/plain;charset=utf-8", "text/plain") if kind in types), "")
    if not mime:
        raise PasteError("Clipboard does not offer plain text")
    raw = read_bounded(command + ["--type", mime], deadline, MAX_BYTES)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PasteError("Clipboard text is not valid UTF-8") from error
    text = " ".join(text.replace("\x00", "").splitlines())
    if len(text.encode("utf-16-le")) // 2 > maximum:
        raise PasteError("Clipboard text does not fit this input")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", action="store_true")
    parser.add_argument("--max-characters", type=int, default=MAX_CHARACTERS)
    args = parser.parse_args()
    try:
        text = read_paste(args.primary, args.max_characters)
        payload = {"ok": True, "text": text}
    except (OSError, UnicodeError, subprocess.SubprocessError, PasteError) as error:
        payload = {"ok": False, "error": str(error)[:256]}
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
