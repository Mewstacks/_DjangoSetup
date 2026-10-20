"""Flows used only by the tests. Sandbox-safe on purpose: this is how a real workflows.py looks."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from temporalio import workflow

from apps.flows.sdk import call_action, flow, local_flow


class GreetIn(BaseModel):
    organization_id: str
    actor_id: str
    title: str
    secret: str = ""


def _local_greet(payload: dict[str, Any]) -> dict[str, Any]:
    # The local form of the same business process: plain Python, same observable result.
    from apps.accounts.models import User
    from apps.actions.context import build_context
    from apps.actions.runtime import invoke
    from apps.organizations.models import Organization

    ctx = build_context(
        user=User.objects.get(pk=payload["actor_id"]),
        organization=Organization.objects.get(pk=payload["organization_id"]),
        channel="flow",
    )
    output, _ = invoke("notes.create", ctx, {"title": payload["title"], "body": payload["secret"]})
    return {"note_id": output["id"]}


@flow("test.greet", input=GreetIn, local=_local_greet, startable=True)
class Greet:
    """Create a note on behalf of an actor."""

    @workflow.run
    async def run(self, data: GreetIn) -> dict[str, Any]:
        created = await call_action(
            "notes.create",
            organization_id=data.organization_id,
            actor_id=data.actor_id,
            payload={"title": data.title, "body": data.secret},
        )
        return {"note_id": created["id"]}


class WaitIn(BaseModel):
    pass


@flow("test.approval", input=WaitIn)
class Approval:
    """Wait three days, then wait for a signal (Temporal only)."""

    def __init__(self) -> None:
        self.approved = False

    @workflow.signal
    def approve(self) -> None:
        self.approved = True

    @workflow.run
    async def run(self, data: WaitIn) -> str:
        await workflow.sleep(timedelta(days=3))
        await workflow.wait_condition(lambda: self.approved)
        return "approved"


class BadIn(BaseModel):
    organization_id: str
    actor_id: str


@flow("test.refused", input=BadIn)
class Refused:
    """Calls an action with invalid input: the refusal must not be retried."""

    @workflow.run
    async def run(self, data: BadIn) -> dict[str, Any]:
        return await call_action(
            "notes.create",
            organization_id=data.organization_id,
            actor_id=data.actor_id,
            payload={"title": ""},
        )


def _local_boom(payload: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("boom")


@local_flow("test.local_only_boom", scope="flows:write")
def local_only_boom(payload: dict[str, Any]) -> dict[str, Any]:
    """A flow that exists only on the local engine and always fails."""
    return _local_boom(payload)
