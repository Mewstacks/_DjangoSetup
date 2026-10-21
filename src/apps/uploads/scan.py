"""Optional antivirus scan through clamd's INSTREAM protocol (no extra dependency).

Set ``UPLOAD_CLAMAV_ADDR=host:port``. When set, a file that cannot be scanned is refused
(fail closed) unless ``UPLOAD_CLAMAV_REQUIRED=false``.
"""

from __future__ import annotations

import socket
import struct

from django.conf import settings

CHUNK = 64 * 1024


class ScanUnavailable(Exception):
    pass


def configured() -> bool:
    return bool(settings.UPLOAD_CLAMAV_ADDR)


def scan(data: bytes) -> str:
    """Return ``clean`` or ``infected``; raise ``ScanUnavailable`` when clamd cannot answer."""
    host, _, port = settings.UPLOAD_CLAMAV_ADDR.rpartition(":")
    try:
        with socket.create_connection((host, int(port)), timeout=15) as sock:
            sock.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), CHUNK):
                chunk = data[start : start + CHUNK]
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0") and len(reply) < 4096:
                part = sock.recv(1024)
                if not part:
                    break
                reply += part
    except (OSError, ValueError) as exc:
        raise ScanUnavailable(str(exc)) from exc
    text = reply.rstrip(b"\0\n").decode("utf-8", "replace")
    if text.endswith("OK"):
        return "clean"
    if text.endswith("FOUND"):
        return "infected"
    raise ScanUnavailable(text[:200] or "empty reply")
