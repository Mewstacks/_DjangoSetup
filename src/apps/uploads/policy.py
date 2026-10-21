"""What may be uploaded. Everything here is about the bytes, never the client's claims.

The extension is the only thing the client picks, and it must agree with what the content is.
The content type served back is the sniffed one, never the one sent with the upload.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

import filetype
from django.conf import settings

from apps.common.exceptions import Invalid, TooLarge

# extension -> sniffed MIME types that are acceptable for it. Text formats have no signature
# and are checked as text instead (see TEXT_EXTENSIONS).
BINARY_TYPES: dict[str, frozenset[str]] = {
    "pdf": frozenset({"application/pdf"}),
    "png": frozenset({"image/png"}),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "gif": frozenset({"image/gif"}),
    "webp": frozenset({"image/webp"}),
    "docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        }
    ),
    "xlsx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        }
    ),
    "pptx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        }
    ),
    "zip": frozenset({"application/zip"}),
}
TEXT_EXTENSIONS = {"txt": "text/plain", "csv": "text/csv", "json": "application/json"}
ZIP_BASED = frozenset({"docx", "xlsx", "pptx", "zip"})
# Never allowed, whatever the settings say: they run in a browser or on a server.
FORBIDDEN = frozenset(
    {"html", "htm", "xhtml", "svg", "js", "mjs", "php", "exe", "dll", "bat", "cmd", "sh", "jar"}
)
SNIFF_BYTES = 8192
_UNSAFE_NAME = re.compile(r"[^\w.\- ()]+", re.UNICODE)


@dataclass(frozen=True)
class Verdict:
    extension: str
    content_type: str
    display_name: str


def allowed_extensions() -> frozenset[str]:
    configured = {e.lower().lstrip(".") for e in settings.UPLOAD_ALLOWED_EXTENSIONS}
    return frozenset(configured - FORBIDDEN)


def clean_name(raw: str) -> str:
    """A display-only name: no path, no control characters, bounded. Never used as a path."""
    base = raw.replace("\\", "/").rsplit("/", 1)[-1]
    base = _UNSAFE_NAME.sub("_", base).strip(" .")
    return (base or "file")[:120]


def check_zip(data: bytes) -> None:
    max_total = int(settings.UPLOAD_MAX_UNCOMPRESSED_BYTES)
    max_ratio = int(settings.UPLOAD_MAX_ZIP_RATIO)
    max_entries = int(settings.UPLOAD_MAX_ZIP_ENTRIES)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise Invalid("The archive is damaged.") from exc
    if len(infos) > max_entries:
        raise Invalid("The archive has too many entries.")
    total = 0
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"):
            raise Invalid("The archive has an unsafe path.")
        if info.flag_bits & 0x1:
            raise Invalid("Encrypted archives are not accepted.")
        total += info.file_size
        if total > max_total:
            raise Invalid("The archive expands too much.")
    if len(data) and total / len(data) > max_ratio:
        raise Invalid("The archive compression ratio is not accepted.")


def inspect(name: str, head: bytes, full: bytes | None, size: int) -> Verdict:
    """Raise a DomainError unless ``name`` and its bytes are acceptable.

    ``head`` is the first bytes; ``full`` is the whole content (needed for archives and text).
    """
    if size <= 0:
        raise Invalid("The file is empty.")
    if size > int(settings.UPLOAD_MAX_BYTES):
        raise TooLarge("The file is too large.")
    display = clean_name(name)
    parts = display.lower().split(".")
    extension = parts[-1] if len(parts) > 1 else ""
    # Every dotted segment is checked, so "report.php.png" cannot hide a second extension.
    if any(part in FORBIDDEN for part in parts[1:]):
        raise Invalid("This file type is not accepted.")
    if extension not in allowed_extensions():
        raise Invalid("This file type is not accepted.")

    if extension in TEXT_EXTENSIONS:
        sample = full if full is not None else head
        if b"\x00" in sample:
            raise Invalid("The content does not match the file type.")
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Invalid("The content does not match the file type.") from exc
        return Verdict(extension, TEXT_EXTENSIONS[extension], display)

    expected = BINARY_TYPES.get(extension)
    if expected is None:
        raise Invalid("This file type is not accepted.")
    kind = filetype.guess(head[:SNIFF_BYTES])
    if kind is None or kind.mime not in expected:
        raise Invalid("The content does not match the file type.")
    if extension in ZIP_BASED:
        if full is None:
            raise Invalid("The archive could not be inspected.")
        check_zip(full)
    return Verdict(extension, kind.mime, display)
