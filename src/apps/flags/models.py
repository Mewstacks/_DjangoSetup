from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class Flag(UUIDTimeStampedModel):
    """A switch operators can flip without a deploy. Unknown flags evaluate to off."""

    key = models.SlugField(max_length=80, unique=True)
    description = models.CharField(max_length=240, blank=True)
    default_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ("key",)

    def __str__(self) -> str:
        return self.key


class FlagRule(UUIDTimeStampedModel):
    """One way to override a flag: for a user, for an organization, or for a share of callers.

    Exactly one targeting mode is set. Precedence at evaluation: user, then organization, then
    percentage, then the flag's default.
    """

    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name="rules")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    percentage = models.PositiveSmallIntegerField(null=True, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, organization__isnull=True, percentage__isnull=True)
                    | models.Q(
                        user__isnull=True, organization__isnull=False, percentage__isnull=True
                    )
                    | models.Q(
                        user__isnull=True, organization__isnull=True, percentage__isnull=False
                    )
                ),
                name="flag_rule_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=models.Q(percentage__isnull=True) | models.Q(percentage__lte=100),
                name="flag_rule_percentage_range",
            ),
        ]

    def clean(self) -> None:
        targets = [self.user_id, self.organization_id, self.percentage]
        if sum(t is not None for t in targets) != 1:
            raise ValidationError("Set exactly one of user, organization or percentage.")


class Setting(UUIDTimeStampedModel):
    """A runtime value overriding a declared default, globally or for one organization."""

    key = models.CharField(max_length=120)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    value_json = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("key", "organization"), name="unique_setting_per_scope"
            ),
            models.UniqueConstraint(
                fields=("key",),
                condition=models.Q(organization__isnull=True),
                name="unique_global_setting",
            ),
        ]

    @property
    def value(self) -> Any:
        return json.loads(self.value_json)
