from apps.flows.models import FlowRun
from apps.privacy.catalog import Category, by_user, personal

personal(
    FlowRun,
    resolver=by_user(FlowRun, "actor"),
    fields={"input_json": Category.CONTENT, "result_json": Category.CONTENT},
    purpose="security-and-audit",
    retention_field="created_at",
    on_erase="delete",
)
