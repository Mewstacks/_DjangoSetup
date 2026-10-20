# Decisions

Short records of choices that shape the code. Each states the reason and the cost.

1. **Actions are the only way in.** One registry feeds REST, MCP, Temporal and the CLI. Cost: an
   extra layer for trivial CRUD, which `OrganizationScopedViewSet` still serves.
2. **pydantic is the single schema source** for actions (REST docs, MCP input schema, activity
   types). No parallel DRF serializers for actions.
3. **Celery removed.** Background work is `django.tasks` with a Temporal backend, or the
   immediate backend when Temporal is off. Cost: no Celery ecosystem.
4. **Temporal is optional, the local engine is honest.** Same `flows.start()`, with a published
   capability matrix; non-portable flows say so. Cost: two implementations to test.
5. **Sync activities on a thread pool.** Django's ORM is synchronous; connections are closed
   around each activity.
6. **Workflows import no Django.** The sandbox forbids it; activities do the work.
7. **Temporal payloads are encrypted** by a codec, and arguments are ids.
8. **Audit chain per organization** with an advisory lock at insert, plus a trigger. Cost: write
   contention on very hot organizations; batch sealing is the escape hatch.
9. **Every model is classified for LGPD** by a failing test.
10. **allauth for accounts**, DOT for OAuth. Cost: two libraries; benefit: audited flows for MFA,
    verification and consent.
11. **Closed sign-up by default.** Open systems are an explicit choice.
12. **One image, many roles; no platform lock-in.** Fly is one target among others.
