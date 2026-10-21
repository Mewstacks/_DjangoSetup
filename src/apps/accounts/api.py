from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.throttling import IPAnonRateThrottle, IPScopedRateThrottle


class MeSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "date_joined")
        read_only_fields = ("id", "email", "date_joined")


class MeView(generics.RetrieveUpdateAPIView[User]):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> User:
        return cast(User, self.request.user)

    def perform_update(self, serializer: serializers.BaseSerializer[User]) -> None:
        # A bare save() rewrites every column from this request's stale copy, which could
        # undo a concurrent password change or deactivation.
        instance = cast(User, serializer.instance)
        for attr, value in serializer.validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=[*serializer.validated_data.keys(), "updated_at"])


class LoginSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class CsrfTokenSerializer(serializers.Serializer[dict[str, str]]):
    csrf_token = serializers.CharField()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [IPAnonRateThrottle]

    @extend_schema(responses=CsrfTokenSerializer)
    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request)})


def _needs_new_flow(user: User) -> bool:
    from allauth.account.models import EmailAddress
    from allauth.mfa.utils import is_mfa_enabled

    if is_mfa_enabled(user):
        return True
    if settings.ACCOUNT_EMAIL_VERIFICATION == "mandatory":
        return not EmailAddress.objects.filter(user=user, verified=True).exists()
    return False


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [IPAnonRateThrottle, IPScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=MeSerializer)
    def post(self, request: Request) -> Response:
        if not settings.LEGACY_LOGIN_ENABLED:
            return Response(
                {"error": {"code": "not_found", "detail": "Sign in through /api/v1/accounts/."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().casefold()
        # django-axes flags a lockout by setting an attribute on the request it is given,
        # and AxesMiddleware later reads that flag off the Django HttpRequest. DRF's
        # Request proxies attribute reads but not writes, so the underlying request has
        # to be passed here or the lockout response is silently dropped.
        user = authenticate(
            request=request._request,
            username=email,
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"error": {"code": "invalid_credentials", "detail": "Invalid credentials."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        # Deprecated: this password-only door predates verified e-mail and MFA. It must never be
        # a way around either, so anything the new flow would ask for is refused here.
        if _needs_new_flow(user):
            return Response(
                {
                    "error": {
                        "code": "use_accounts_flow",
                        "detail": "Sign in through /api/v1/accounts/.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, user)
        response = Response(MeSerializer(user).data)
        response["Deprecation"] = "true"
        response["Link"] = '</api/v1/accounts/browser/v1/auth/login>; rel="successor-version"'
        return response


class LogoutView(APIView):
    @extend_schema(request=None, responses={status.HTTP_204_NO_CONTENT: None})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
