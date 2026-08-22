#!/usr/bin/env python3
"""Bounded reader for OmaQuickCalc's user-writable local state."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


STATE_LIMITS = {
    "config": 64 * 1024,
    "history": 16 * 1024 * 1024,
    "launch": 16 * 1024,
    "launcher": 64 * 1024,
}

EXIT_MISSING = 10
EXIT_TOO_LARGE = 11
EXIT_INVALID = 12


class StateFileTooLarge(ValueError):
    """The state file exceeds its configured byte ceiling."""


class StateFileInvalid(ValueError):
    """The state path is not a regular UTF-8 file."""


def read_state(path: Path, byte_limit: int) -> str:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise StateFileInvalid("state path is not a regular file")
    with os.fdopen(descriptor, "rb") as stream:
        if metadata.st_size > byte_limit:
            raise StateFileTooLarge("state file exceeds its byte limit")
        content = stream.read(byte_limit + 1)
    if len(content) > byte_limit:
        raise StateFileTooLarge("state file exceeds its byte limit")
    try:
        return content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise StateFileInvalid("state file is not valid UTF-8") from error


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("read",))
    parser.add_argument("--kind", choices=tuple(STATE_LIMITS), required=True)
    parser.add_argument("--path", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        content = read_state(args.path, STATE_LIMITS[args.kind])
    except FileNotFoundError:
        return EXIT_MISSING
    except StateFileTooLarge:
        return EXIT_TOO_LARGE
    except (OSError, StateFileInvalid):
        return EXIT_INVALID
    sys.stdout.buffer.write(content.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
