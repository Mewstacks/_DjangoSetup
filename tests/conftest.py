from __future__ import annotations

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db: object) -> User:
    from allauth.account.models import EmailAddress

    created = User.objects.create_user(
        email="USER@Example.COM",
        password="correct-horse-battery-staple",
        full_name="Example User",
    )
    EmailAddress.objects.create(user=created, email=created.email, primary=True, verified=True)
    return created


@pytest.fixture
def authenticated_client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def organization(db: object) -> Organization:
    return Organization.objects.create(name="Acme", slug="acme")


@pytest.fixture
def membership(organization: Organization, user: User) -> Membership:
    return Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.OWNER,
    )


@pytest.fixture
def org_client(user: User, organization: Organization, membership: Membership) -> APIClient:
    """A client that is logged in and has already selected ``organization``.

    OrganizationContextMiddleware reads ``request.user`` off the Django request, which
    ``force_authenticate`` never populates, so a real session login is required here.
    """

    client = APIClient()
    client.force_login(user)
    client.credentials(HTTP_X_ORGANIZATION_ID=str(organization.id))
    return client


@pytest.fixture
def other_org_client(db: object) -> APIClient:
    """A client from a second tenant, for proving that scoping actually holds."""

    outsider = User.objects.create_user("outsider@example.com", "another-strong-password")
    other_organization = Organization.objects.create(name="Globex", slug="globex")
    Membership.objects.create(
        organization=other_organization,
        user=outsider,
        role=Membership.Role.OWNER,
    )
    client = APIClient()
    client.force_login(outsider)
    client.credentials(HTTP_X_ORGANIZATION_ID=str(other_organization.id))
    return client


@pytest.fixture(scope="session", autouse=True)
def _allow_truncate_between_tests(django_db_setup: object, django_db_blocker: object) -> None:
    """Django's ``flush`` between transactional tests issues TRUNCATE, which the audit table's
    PostgreSQL trigger (rightly) refuses. Tests switch that one trigger off; the test that
    proves the trigger works switches it back on for its own duration."""
    if connection.vendor != "postgresql":
        return
    with django_db_blocker.unblock(), connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute("ALTER TABLE audit_auditevent DISABLE TRIGGER audit_auditevent_no_truncate")
