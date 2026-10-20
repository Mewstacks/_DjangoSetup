from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.api import CsrfTokenView, LoginView, LogoutView, MeView
from apps.common.views import LivenessView, ReadinessView
from apps.organizations.api import OrganizationViewSet
from apps.privacy.api import ConsentViewSet, DataSubjectRequestViewSet, ProcessingPurposeViewSet

router = DefaultRouter(use_regex_path=False)
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("privacy/purposes", ProcessingPurposeViewSet, basename="privacy-purpose")
router.register("privacy/consents", ConsentViewSet, basename="privacy-consent")
router.register("privacy/requests", DataSubjectRequestViewSet, basename="privacy-request")

urlpatterns = [
    path("health/live/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("", include(router.urls)),
]
