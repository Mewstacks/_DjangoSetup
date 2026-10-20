from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db: object) -> User:
    return User.objects.create_user(
        email="USER@Example.COM",
        password="correct-horse-battery-staple",
        full_name="Example User",
    )


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
