from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization


@pytest.mark.django_db
def test_organization_context_requires_an_active_membership(user: User) -> None:
    organization = Organization.objects.create(name="Other Company", slug="other-company")
    other_user = User.objects.create_user("other@example.com", "another-strong-password")
    Membership.objects.create(organization=organization, user=other_user)

    client = APIClient()
    client.force_login(user)
    denied = client.get(
        "/api/v1/auth/me/",
        HTTP_X_ORGANIZATION_ID=str(organization.id),
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "organization_not_found"


@pytest.mark.django_db
def test_organization_creation_assigns_owner_and_list_is_scoped(user: User) -> None:
    client = APIClient()
    client.force_authenticate(user)
    created = client.post(
        "/api/v1/organizations/",
        {"name": "Acme", "slug": "acme-saas"},
        format="json",
    )
    assert created.status_code == 201
    organization = Organization.objects.get(id=created.data["id"])
    membership = Membership.objects.get(organization=organization, user=user)
    assert membership.role == Membership.Role.OWNER

    assert created.data["current_user_role"] == Membership.Role.OWNER

    unrelated = Organization.objects.create(name="Unrelated", slug="unrelated-company")
    listed = client.get("/api/v1/organizations/")
    listed_ids = {item["id"] for item in listed.data["results"]}
    assert str(organization.id) in listed_ids
    assert str(unrelated.id) not in listed_ids
    assert listed.data["results"][0]["current_user_role"] == Membership.Role.OWNER


@pytest.mark.django_db
def test_listing_cost_does_not_grow_with_the_member_count(
    user: User,
    django_assert_max_num_queries: object,
) -> None:
    organization = Organization.objects.create(name="Acme", slug="acme-listing")
    Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)
    for index in range(25):
        Membership.objects.create(
            organization=organization,
            user=User.objects.create_user(f"member{index}@example.com", "a-strong-password"),
        )

    client = APIClient()
    client.force_authenticate(user)
    # The role now arrives as an annotation, so no membership rows are fetched at all.
    with django_assert_max_num_queries(3):  # type: ignore[operator]
        listed = client.get("/api/v1/organizations/")
    assert listed.data["results"][0]["current_user_role"] == Membership.Role.OWNER
