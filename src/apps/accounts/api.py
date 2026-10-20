from __future__ import annotations

from typing import Any, cast

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


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [AllowAny]
    throttle_classes = [IPAnonRateThrottle, IPScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=MeSerializer)
    def post(self, request: Request) -> Response:
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
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={status.HTTP_204_NO_CONTENT: None})
    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
