from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Iterator
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from django.db import connection, transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.flows.engine import LocalEngine
from apps.organizations.models import Membership, Organization
from apps.webhooks import services
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint

pytestmark = pytest.mark.django_db(transaction=True)


class Receiver:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.location = ""
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                receiver.requests.append({"headers": dict(self.headers), "body": body})
                self.send_response(receiver.status)
                if receiver.location:
                    self.send_header("Location", receiver.location)
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()


@pytest.fixture
def receiver() -> Iterator[Receiver]:
    instance = Receiver()
    with override_settings(NETGUARD_ALLOW_PRIVATE=True):
        yield instance
    instance.close()


def make_endpoint(
    organization: Organization, url: str, events: list[str] | None = None
) -> tuple[WebhookEndpoint, str]:
    from apps.webhooks.models import new_secret

    secret = new_secret()
    endpoint = WebhookEndpoint.objects.create(
        organization=organization, url=url, events=events or ["*"], secret=secret
    )
    return endpoint, secret


def make_due() -> None:
    WebhookDelivery.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))


def test_endpoints_are_managed_by_admins_and_the_secret_is_shown_once(
    org_client: APIClient, organization: Organization, membership: Membership, receiver: Receiver
) -> None:
    created = org_client.post(
        "/api/v1/webhooks/endpoints/",
        {"url": receiver.url, "events": ["note.created"], "description": "ci"},
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created["Cache-Control"] == "no-store" and created.data["secret"].startswith("whsec_")
    listed = org_client.get("/api/v1/webhooks/endpoints/")
    assert (
        "secret" not in json.dumps(listed.data)
        or listed.data["results"][0]["secret"] != created.data["secret"]
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT secret FROM webhooks_webhookendpoint")
        assert cursor.fetchone()[0].startswith("enc:v2:")

    Membership.objects.filter(pk=membership.pk).update(role=Membership.Role.MEMBER)
    assert (
        org_client.post(
            "/api/v1/webhooks/endpoints/", {"url": receiver.url, "events": ["*"]}, format="json"
        ).status_code
        == 403
    )


def test_endpoint_urls_and_events_are_validated(org_client: APIClient, receiver: Receiver) -> None:
    with override_settings(NETGUARD_ALLOW_PRIVATE=False, DEBUG=False):
        for bad in (
            "http://example.com/x",
            "https://127.0.0.1/x",
            "https://169.254.169.254/latest",
        ):
            response = org_client.post(
                "/api/v1/webhooks/endpoints/", {"url": bad, "events": ["*"]}, format="json"
            )
            assert response.status_code == 422, bad
    bad_event = org_client.post(
        "/api/v1/webhooks/endpoints/", {"url": receiver.url, "events": ["nope.nope"]}, format="json"
    )
    assert bad_event.status_code == 400


def test_an_event_is_delivered_signed_and_carries_ids_not_documents(
    org_client: APIClient, organization: Organization, receiver: Receiver
) -> None:
    _, secret = make_endpoint(organization, receiver.url, ["note.created"])
    org_client.post(
        "/api/v1/actions/notes.create/", {"title": "Private title", "body": "secret"}, format="json"
    )
    assert services.dispatch_due()["delivered"] == 1
    request = receiver.requests[0]
    headers = {k.lower(): v for k, v in request["headers"].items()}
    body = request["body"]
    expected = hmac.new(
        secret.encode(), f"{headers['x-webhook-timestamp']}.".encode() + body, hashlib.sha256
    ).hexdigest()
    assert headers["x-webhook-signature"] == f"v1={expected}"
    payload = json.loads(body)
    assert payload["type"] == "note.created" and payload["id"] == headers["x-webhook-id"]
    assert set(payload["data"]) == {"note_id"} and "Private title" not in body.decode()
    assert WebhookDelivery.objects.get().status == "delivered"


def test_failures_back_off_then_give_up_and_the_endpoint_is_cut_off(
    organization: Organization, receiver: Receiver
) -> None:
    receiver.status = 500
    endpoint, _ = make_endpoint(organization, receiver.url)
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    with override_settings(WEBHOOK_DISABLE_AFTER=3):
        assert services.attempt(delivery.pk)["state"] == "retry"
        delivery.refresh_from_db()
        assert delivery.attempts == 1 and delivery.last_status_code == 500
        assert delivery.next_attempt_at > timezone.now() + timedelta(seconds=30)
        assert services.attempt(delivery.pk)["state"] == "skipped"  # not due yet
        for _ in range(2):
            make_due()
            services.attempt(delivery.pk)
    endpoint.refresh_from_db()
    assert not endpoint.is_active and endpoint.disabled_reason == "too_many_failures"
    assert AuditEvent.objects.filter(action="webhook.endpoint_disabled").exists()
    make_due()
    assert services.attempt(delivery.pk)["state"] == "dead"  # an inactive endpoint gets nothing


def test_a_recovering_receiver_gets_the_event_exactly_once_more(
    organization: Organization, receiver: Receiver
) -> None:
    receiver.status = 503
    endpoint, _ = make_endpoint(organization, receiver.url)
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    services.attempt(delivery.pk)
    receiver.status = 200
    make_due()
    assert services.attempt(delivery.pk)["state"] == "delivered"
    endpoint.refresh_from_db()
    assert endpoint.failure_streak == 0
    ids = {dict(r["headers"])["X-Webhook-Id"] for r in receiver.requests}
    assert ids == {str(event.pk)} and len(receiver.requests) == 2  # same id: receivers dedupe
    assert services.attempt(delivery.pk)["state"] == "skipped"  # delivered is final


def test_two_workers_never_send_the_same_delivery(
    organization: Organization, receiver: Receiver
) -> None:
    endpoint, _ = make_endpoint(organization, receiver.url)
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    WebhookDelivery.objects.filter(pk=delivery.pk).update(
        locked_until=timezone.now() + timedelta(minutes=1)
    )
    assert services.attempt(delivery.pk)["state"] == "skipped" and not receiver.requests


def test_secret_rotation_signs_with_both_secrets_during_the_overlap(
    organization: Organization, receiver: Receiver
) -> None:
    endpoint, old = make_endpoint(organization, receiver.url)
    fresh = endpoint.rotate()
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    services.attempt(delivery.pk)
    headers = {k.lower(): v for k, v in receiver.requests[0]["headers"].items()}
    body, stamp = receiver.requests[0]["body"], int(headers["x-webhook-timestamp"])
    signatures = headers["x-webhook-signature"].split()
    assert f"v1={services.sign(fresh, stamp, body)}" in signatures
    assert f"v1={services.sign(old, stamp, body)}" in signatures
    WebhookEndpoint.objects.filter(pk=endpoint.pk).update(
        previous_secret_expires_at=timezone.now() - timedelta(seconds=1)
    )
    endpoint.refresh_from_db()
    assert endpoint.secrets_for_signing() == [fresh]


def test_redirects_are_never_followed_and_internal_targets_are_never_called(
    organization: Organization, receiver: Receiver
) -> None:
    receiver.status, receiver.location = 302, "http://169.254.169.254/latest/meta-data"
    endpoint, _ = make_endpoint(organization, receiver.url)
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    assert services.attempt(delivery.pk)["state"] == "retry"  # 302 is a failure, not a hop
    assert len(receiver.requests) == 1
    WebhookEndpoint.objects.filter(pk=endpoint.pk).update(url="https://127.0.0.1:9/x")
    with override_settings(NETGUARD_ALLOW_PRIVATE=False, DEBUG=False):
        make_due()
        services.attempt(delivery.pk)
    delivery.refresh_from_db()
    assert len(receiver.requests) == 1 and "internal" in delivery.last_error


def test_events_follow_the_transaction_that_announces_them(
    organization: Organization, receiver: Receiver
) -> None:
    make_endpoint(organization, receiver.url)
    with pytest.raises(RuntimeError), transaction.atomic():
        services.emit("note.created", organization, {"note_id": "x"})
        raise RuntimeError("rolled back")
    assert not services.WebhookEvent.objects.exists() and not WebhookDelivery.objects.exists()
    with transaction.atomic():
        services.emit("note.created", organization, {"note_id": "x"})
    assert WebhookDelivery.objects.count() == 1


def test_only_subscribed_active_endpoints_receive_an_event(
    organization: Organization, receiver: Receiver
) -> None:
    make_endpoint(organization, receiver.url, ["note.archived"])
    inactive, _ = make_endpoint(organization, receiver.url)
    WebhookEndpoint.objects.filter(pk=inactive.pk).update(is_active=False)
    assert services.emit("note.created", organization, {"note_id": "x"}) is None
    assert services.emit("note.archived", organization, {"note_id": "x"}) is not None
    with pytest.raises(ValueError):
        services.emit("made.up", organization, {})


def test_other_organizations_endpoints_and_deliveries_are_invisible(
    organization: Organization, other_org_client: APIClient, receiver: Receiver
) -> None:
    endpoint, _ = make_endpoint(organization, receiver.url)
    assert other_org_client.get(f"/api/v1/webhooks/endpoints/{endpoint.pk}/").status_code == 404
    assert other_org_client.get("/api/v1/webhooks/endpoints/").data["count"] == 0


def test_the_deliver_flow_runs_on_the_local_engine(
    organization: Organization, receiver: Receiver
) -> None:
    endpoint, _ = make_endpoint(organization, receiver.url)
    event = services.WebhookEvent.objects.create(
        organization=organization, event_type="webhook.test", payload_json="{}"
    )
    delivery = WebhookDelivery.objects.create(
        organization=organization, event=event, endpoint=endpoint
    )
    run = LocalEngine().start("webhooks.deliver", {"delivery_id": str(delivery.pk)})
    assert json.loads(run.result_json)["state"] == "delivered"
