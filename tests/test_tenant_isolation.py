from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings
from django.urls import include, path
from rest_framework import serializers
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Membership, Organization
from apps.organizations.viewsets import OrganizationScopedViewSet
from config.urls_api import router

SCOPED_PREFIXES = [
    prefix
    for prefix, viewset, _ in router.registry
    if isinstance(viewset, type) and issubclass(viewset, OrganizationScopedViewSet)
]


class ScopedMembershipSerializer(serializers.ModelSerializer[Membership]):
    class Meta:
        model = Membership
        # ``organization`` is intentionally writable here to prove that the base viewset,
        # not the serializer, is what forbids tenant reassignment on update.
        fields = ("id", "role", "organization")


class ScopedMembershipViewSet(OrganizationScopedViewSet):  # type: ignore[type-arg]
    """Stand-in resource, so the base class is exercised over HTTP before real ones exist."""

    queryset = Membership.objects.all().order_by("created_at")
    serializer_class = ScopedMembershipSerializer


# A throwaway URL map that mounts the stand-in resource, activated per-test with
# ``override_settings(ROOT_URLCONF=__name__)``. This gives the tenant guarantees real
# integration coverage without registering an example business resource in production.
_test_router = DefaultRouter()
_test_router.register("scoped-memberships", ScopedMembershipViewSet, basename="scoped-membership")
urlpatterns = [path("api/v1/", include(_test_router.urls))]


@pytest.mark.django_db
def test_the_base_viewset_filters_by_the_selected_organization(
    organization: Organization,
    membership: Membership,
) -> None:
    outsider = User.objects.create_user("outsider2@example.com", "another-strong-password")
    other = Organization.objects.create(name="Globex", slug="globex-two")
    Membership.objects.create(organization=other, user=outsider)

    request = RequestFactory().get("/")
    request.organization = organization  # type: ignore[attr-defined]
    view = ScopedMembershipViewSet()
    view.request = request  # type: ignore[assignment]

    assert list(view.get_queryset()) == [membership]


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_cross_tenant_detail_is_not_found(
    other_org_client: APIClient,
    membership: Membership,
) -> None:
    response = other_org_client.get(f"/api/v1/scoped-memberships/{membership.id}/")
    assert response.status_code == 404


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_cross_tenant_list_does_not_leak(
    other_org_client: APIClient,
    membership: Membership,
) -> None:
    response = other_org_client.get("/api/v1/scoped-memberships/")
    assert response.status_code == 200
    listed_ids = {row["id"] for row in response.data["results"]}
    assert str(membership.id) not in listed_ids


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_cross_tenant_update_is_not_found(
    other_org_client: APIClient,
    membership: Membership,
) -> None:
    response = other_org_client.patch(
        f"/api/v1/scoped-memberships/{membership.id}/",
        {"role": Membership.Role.ADMIN},
        format="json",
    )
    assert response.status_code == 404


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_cross_tenant_delete_is_not_found(
    other_org_client: APIClient,
    membership: Membership,
) -> None:
    response = other_org_client.delete(f"/api/v1/scoped-memberships/{membership.id}/")
    assert response.status_code == 404


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_update_cannot_reassign_the_row_to_another_tenant(
    org_client: APIClient,
    organization: Organization,
    membership: Membership,
) -> None:
    other = Organization.objects.create(name="Initech", slug="initech")
    response = org_client.patch(
        f"/api/v1/scoped-memberships/{membership.id}/",
        {"organization": str(other.id)},
        format="json",
    )
    assert response.status_code == 200
    membership.refresh_from_db()
    assert membership.organization_id == organization.id


@override_settings(ROOT_URLCONF=__name__)
@pytest.mark.django_db
def test_scoped_route_refuses_a_request_without_a_selected_organization(
    user: User,
) -> None:
    client = APIClient()
    client.force_login(user)  # authenticated, but no X-Organization-ID header
    response = client.get("/api/v1/scoped-memberships/")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.skipif(not SCOPED_PREFIXES, reason="no organization-scoped routes registered yet")
def test_a_foreign_organization_header_is_never_accepted(
    other_org_client: APIClient,
    organization: Organization,
) -> None:
    """Sweeps every scoped route registered in production, for resources added later."""

    for prefix in SCOPED_PREFIXES:
        response = other_org_client.get(
            f"/api/v1/{prefix}/",
            HTTP_X_ORGANIZATION_ID=str(organization.id),
        )
        assert response.status_code == 404, prefix


@pytest.mark.django_db
@pytest.mark.skipif(not SCOPED_PREFIXES, reason="no organization-scoped routes registered yet")
def test_scoped_routes_refuse_requests_without_a_selected_organization(
    user: object,
    org_client: APIClient,
) -> None:
    org_client.credentials()  # drop the X-Organization-ID header
    for prefix in SCOPED_PREFIXES:
        response = org_client.get(f"/api/v1/{prefix}/")
        assert response.status_code == 403, prefix
