from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.urls.resolvers import URLPattern, URLResolver
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny, IsAdminUser

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/", include("config.urls_api")),
    # Accounts: JSON for apps and SPAs (browser and app clients), HTML for OAuth login/consent.
    path("api/v1/accounts/", include("allauth.headless.urls")),
    path("accounts/", include("allauth.urls")),
]

if settings.OAUTH_ENABLED:
    from apps.oauth.urls import root_urlpatterns as oauth_root_patterns

    urlpatterns += [
        *oauth_root_patterns,
        path("o/", include("apps.oauth.urls")),
    ]

if settings.API_DOCS_ENABLED:
    # Public in development; behind an admin session anywhere else.
    docs_permissions = [AllowAny] if settings.DEBUG else [IsAdminUser]
    urlpatterns.extend(
        [
            path(
                "api/schema/",
                SpectacularAPIView.as_view(permission_classes=docs_permissions),
                name="api-schema",
            ),
            path(
                "api/docs/",
                SpectacularSwaggerView.as_view(
                    url_name="api-schema", permission_classes=docs_permissions
                ),
                name="api-docs",
            ),
        ]
    )

if settings.ADMIN_ENABLED:
    # The admin's own login form would sidestep verified e-mail and MFA; send it through allauth.
    from allauth.account.decorators import secure_admin_login

    admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]
    urlpatterns.append(path("admin/", admin.site.urls))
