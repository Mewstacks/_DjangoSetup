from __future__ import annotations

import io
import socket
import threading
import zipfile
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.organizations.models import Membership, Organization
from apps.uploads.models import UploadedFile

pytestmark = pytest.mark.django_db

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92"
    b"\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def docx_bytes(payload: bytes = b"hello") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", payload)
    return buffer.getvalue()


def send(
    client: APIClient, name: str, data: bytes, content_type: str = "application/octet-stream"
) -> Any:
    return client.post(
        "/api/v1/uploads/",
        {"file": SimpleUploadedFile(name, data, content_type=content_type)},
        format="multipart",
    )


def test_a_real_png_is_stored_under_a_name_the_client_did_not_pick(
    org_client: APIClient, organization: Organization
) -> None:
    response = send(org_client, "../../etc/pass wd.png", PNG, "text/html")
    assert response.status_code == 201, response.data
    row = UploadedFile.objects.get()
    assert row.content_type == "image/png"  # sniffed, not the claimed text/html
    assert "/" not in row.original_name and ".." not in row.original_name
    assert row.file.name.startswith(f"uploads/{organization.pk}/")
    assert "wd" not in row.file.name and not row.file.name.endswith(".png")
    assert AuditEvent.objects.filter(action="upload.created").exists()


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("evil.html", b"<script>alert(1)</script>"),
        ("evil.svg", b"<svg onload=alert(1)/>"),
        ("report.php.png", PNG),  # a second extension hides a server-side type
        ("fake.png", b"MZ\x90\x00 not an image"),  # content is not a png
        ("fake.pdf", PNG),  # content is another type
        ("binary.txt", b"abc\x00def"),
        ("noext", b"hello"),
        ("empty.txt", b""),
    ],
)
def test_content_and_extension_must_agree(org_client: APIClient, name: str, data: bytes) -> None:
    response = send(org_client, name, data)
    assert response.status_code in (400, 422), (name, response.status_code)
    assert not UploadedFile.objects.exists()


def test_office_files_are_zip_checked(org_client: APIClient) -> None:
    assert send(org_client, "ok.docx", docx_bytes()).status_code == 201
    bomb = docx_bytes(b"0" * 5_000_000)
    with override_settings(UPLOAD_MAX_ZIP_RATIO=10):
        assert send(org_client, "bomb.docx", bomb).status_code == 422
    with override_settings(UPLOAD_MAX_UNCOMPRESSED_BYTES=1000):
        assert send(org_client, "big.docx", bomb).status_code == 422
    assert send(org_client, "plain.docx", b"PK\x03\x04 not really").status_code == 422


def test_size_cap(org_client: APIClient) -> None:
    with override_settings(UPLOAD_MAX_BYTES=10):
        assert send(org_client, "a.txt", b"x" * 11).status_code == 413
        assert send(org_client, "a.txt", b"x" * 10).status_code == 201


def test_download_is_an_attachment_with_hardening_headers(org_client: APIClient) -> None:
    created = send(org_client, "notes.txt", b"hello")
    response = org_client.get(f"/api/v1/uploads/{created.data['id']}/download/")
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response["Content-Security-Policy"]
    assert b"".join(response.streaming_content) == b"hello"


def test_other_organizations_cannot_see_or_fetch_files(
    org_client: APIClient, other_org_client: APIClient
) -> None:
    created = send(org_client, "notes.txt", b"hello")
    pk = created.data["id"]
    assert other_org_client.get(f"/api/v1/uploads/{pk}/").status_code == 404
    assert other_org_client.get(f"/api/v1/uploads/{pk}/download/").status_code == 404
    assert other_org_client.delete(f"/api/v1/uploads/{pk}/").status_code == 404
    assert other_org_client.get("/api/v1/uploads/").data["count"] == 0


def test_auditors_read_but_do_not_upload(org_client: APIClient, membership: Membership) -> None:
    Membership.objects.filter(pk=membership.pk).update(role=Membership.Role.AUDITOR)
    assert send(org_client, "a.txt", b"hello").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_delete_removes_the_blob_and_audits(org_client: APIClient) -> None:
    created = send(org_client, "notes.txt", b"hello")
    row = UploadedFile.objects.get()
    storage, name = row.file.storage, row.file.name
    assert storage.exists(name)
    assert org_client.delete(f"/api/v1/uploads/{created.data['id']}/").status_code == 204
    assert not UploadedFile.objects.exists()
    assert not storage.exists(name)
    assert AuditEvent.objects.filter(action="upload.deleted").exists()


class FakeClam:
    def __init__(self, reply: bytes) -> None:
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.addr = f"127.0.0.1:{self.server.getsockname()[1]}"
        self.reply = reply
        self.received = b""
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        conn, _ = self.server.accept()
        with conn:
            conn.recv(10)  # zINSTREAM\0
            while True:
                header = b""
                while len(header) < 4:
                    header += conn.recv(4 - len(header))
                length = int.from_bytes(header, "big")
                if length == 0:
                    break
                got = 0
                while got < length:
                    chunk = conn.recv(length - got)
                    got += len(chunk)
                    self.received += chunk
            conn.sendall(self.reply)

    def close(self) -> None:
        self.server.close()


def test_clamav_verdicts_and_fail_closed(org_client: APIClient) -> None:
    clean = FakeClam(b"stream: OK\0")
    with override_settings(UPLOAD_CLAMAV_ADDR=clean.addr):
        assert send(org_client, "a.txt", b"hello").status_code == 201
    assert UploadedFile.objects.get().scan_status == "clean" and clean.received == b"hello"
    clean.close()

    infected = FakeClam(b"stream: Eicar-Test-Signature FOUND\0")
    with override_settings(UPLOAD_CLAMAV_ADDR=infected.addr):
        assert send(org_client, "b.txt", b"eicar").status_code == 422
    infected.close()
    assert UploadedFile.objects.count() == 1

    with override_settings(UPLOAD_CLAMAV_ADDR="127.0.0.1:1"):
        assert send(org_client, "c.txt", b"hello").status_code == 503
        with override_settings(UPLOAD_CLAMAV_REQUIRED=False):
            assert send(org_client, "c.txt", b"hello").status_code == 201
