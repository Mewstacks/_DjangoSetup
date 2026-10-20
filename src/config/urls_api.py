from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.api import CsrfTokenView, LoginView, LogoutView, MeView
from apps.actions.rest import ActionCatalogView, ActionInvokeView
from apps.apikeys.api import ApiKeyViewSet
from apps.common.views import LivenessView, ReadinessView
from apps.examples.api import NoteViewSet
from apps.organizations.api import OrganizationViewSet
from apps.privacy.api import (
    ActiveNoticeView,
    ConsentViewSet,
    DataSubjectRequestViewSet,
    ProcessingPurposeViewSet,
)
from apps.privacy.public_api import (
    CookieConfigView,
    ExportDownloadView,
    PublicRequestView,
    PublicVerifyView,
    TransparencyView,
)
from apps.uploads.api import UploadViewSet
from apps.webhooks.api import DeliveryViewSet, EndpointViewSet

router = DefaultRouter(use_regex_path=False)
router.register("api-keys", ApiKeyViewSet, basename="api-key")
router.register("notes", NoteViewSet, basename="note")
router.register("uploads", UploadViewSet, basename="upload")
router.register("webhooks/endpoints", EndpointViewSet, basename="webhook-endpoint")
router.register("webhooks/deliveries", DeliveryViewSet, basename="webhook-delivery")
router.register("organizations", OrganizationViewSet, basename="organization")
router.register("privacy/purposes", ProcessingPurposeViewSet, basename="privacy-purpose")
router.register("privacy/consents", ConsentViewSet, basename="privacy-consent")
router.register("privacy/requests", DataSubjectRequestViewSet, basename="privacy-request")

urlpatterns = [
    path("actions/", ActionCatalogView.as_view(), name="action-catalog"),
    path("actions/<str:name>/", ActionInvokeView.as_view(), name="action-invoke"),
    path("health/live/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("privacy/notice/", ActiveNoticeView.as_view(), name="privacy-notice"),
    path("privacy/transparency/", TransparencyView.as_view(), name="privacy-transparency"),
    path("privacy/cookies/", CookieConfigView.as_view(), name="privacy-cookies"),
    path("privacy/public/requests/", PublicRequestView.as_view(), name="privacy-public-request"),
    path("privacy/public/verify/", PublicVerifyView.as_view(), name="privacy-public-verify"),
    path("privacy/exports/<str:token>/", ExportDownloadView.as_view(), name="privacy-export"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("", include(router.urls)),
]
