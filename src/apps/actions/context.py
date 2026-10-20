"""Who is calling an action, and what they may touch.

``ActionContext`` is deliberately thin and free of ``HttpRequest``: an action must run the same
from REST, an MCP call, a Temporal activity or the CLI, and only the first has a request.
Everything an action needs from the caller is here; everything it needs from the database goes
through :meth:`ActionContext.scoped`, the one sanctioned way to reach tenant data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

from django.db.models import Model, QuerySet

from apps.common.exceptions import Forbidden, NotFound
from apps.organizations.models import Membership, Organization, OrganizationScopedModel

ALL_SCOPES = "*"
WRITE_ROLES = frozenset({Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MEMBER})

ScopedT = TypeVar("ScopedT", bound=OrganizationScopedModel)


@dataclass(slots=True)
class ActionContext:
    user: Any
    organization: Organization
    membership: Membership
    scopes: frozenset[str]
    channel: str
    request_id: str | None = None
    credential_id: str | None = None
    client_ip: str | None = None
    target: Model | None = field(default=None, repr=False)
    notes: list[str] = field(default_factory=list, repr=False)
    changes: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @property
    def role(self) -> str:
        return str(self.membership.role)

    @property
    def can_write(self) -> bool:
        """Auditors and billing contacts read; they never change tenant data."""
        return self.role in WRITE_ROLES

    def has_scope(self, scope: str) -> bool:
        return ALL_SCOPES in self.scopes or scope in self.scopes

    def scoped(self, model: type[ScopedT]) -> QuerySet[ScopedT]:
        """The only way an action reaches tenant data: rows of the caller's organization."""
        if not issubclass(model, OrganizationScopedModel):
            raise TypeError(f"{model.__name__} is not organization-scoped.")
        queryset: QuerySet[ScopedT] = model.objects.filter(organization=self.organization)  # type: ignore[attr-defined]
        return queryset

    def get(self, model: type[ScopedT], pk: Any) -> ScopedT:
        """One row of the caller's organization, or NotFound (never 'exists elsewhere')."""
        try:
            return self.scoped(model).get(pk=pk)
        except (model.DoesNotExist, ValueError, TypeError) as exc:
            raise NotFound(
                f"{str(model._meta.verbose_name or model.__name__).capitalize()} not found."
            ) from exc

    def record_change(
        self,
        op: str,
        instance: Model,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        label: str = "",
    ) -> None:
        """Declare what this call changed so it can be listed and undone (see journal.py)."""
        self.changes.append(
            {
                "op": op,
                "target_type": instance._meta.label_lower,
                "target_id": str(instance.pk),
                "label": label[:200],
                "before": before or {},
                "after": after or {},
            }
        )

    def set_target(self, instance: Model) -> None:
        """Name the record this call acted on; it ends up in the audit event."""
        self.target = instance


def build_context(
    *,
    user: Any,
    organization: Organization,
    channel: str,
    scopes: frozenset[str] | None = None,
    request_id: str | None = None,
    credential_id: str | None = None,
    client_ip: str | None = None,
) -> ActionContext:
    """A context for ``user`` in ``organization``, re-reading membership *now*.

    The role is never copied into a token or a workflow input: demoting or removing somebody
    must take effect on their very next call.
    """
    membership = Membership.objects.filter(
        organization=organization, user=user, is_active=True
    ).first()
    if membership is None or not getattr(user, "is_active", False) or not organization.is_active:
        raise Forbidden("Access to this organization has ended.", code="membership_inactive")
    return ActionContext(
        user=user,
        organization=organization,
        membership=membership,
        scopes=scopes if scopes is not None else frozenset({ALL_SCOPES}),
        channel=channel,
        request_id=request_id,
        credential_id=credential_id,
        client_ip=client_ip,
    )
