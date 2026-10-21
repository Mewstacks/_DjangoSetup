"""Close the holes in the trigger that 0003 installed.

* The trigger let *any* session delete after ``SET LOCAL app.audit_maintenance = 'on'``. It now
  allows a delete only for the role that owns the table, and the only sanctioned delete is
  ``audit_prune()``: a SECURITY DEFINER function nobody but the owner (and the runtime role named
  in ``AUDIT_RUNTIME_ROLE``) may execute. A runtime role that does not own the table can no
  longer delete, update or truncate anything.
* A CHECK constraint refuses rows outside the hash chain (no ``seq``, no ``hash``). It is
  ``NOT VALID`` on PostgreSQL so rows from before chaining existed do not block the migration;
  every new row is checked.

SQLite (development and tests) has neither triggers nor functions and skips the database part.
"""

import re

from django.conf import settings
from django.db import migrations, models

TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_block_mutation() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE'
     AND current_setting('app.audit_maintenance', true) = 'on'
     AND current_user = (SELECT pg_get_userbyid(c.relowner) FROM pg_class c WHERE c.oid = TG_RELID)
  THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'audit_auditevent is append-only (%% refused)', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

PRUNE_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_prune(p_chain text, p_up_to_seq bigint) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  removed bigint;
BEGIN
  PERFORM set_config('app.audit_maintenance', 'on', true);
  DELETE FROM audit_auditevent
   WHERE chain_key = p_chain AND seq IS NOT NULL AND seq <= p_up_to_seq;
  GET DIAGNOSTICS removed = ROW_COUNT;
  PERFORM set_config('app.audit_maintenance', 'off', true);
  RETURN removed;
END;
$$;
REVOKE ALL ON FUNCTION audit_prune(text, bigint) FROM PUBLIC;
"""

CONSTRAINT = """
ALTER TABLE audit_auditevent DROP CONSTRAINT IF EXISTS audit_event_is_chained;
ALTER TABLE audit_auditevent
  ADD CONSTRAINT audit_event_is_chained CHECK (seq IS NOT NULL AND hash <> '') NOT VALID;
"""

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(TRIGGER_FUNCTION)
    schema_editor.execute(PRUNE_FUNCTION)
    schema_editor.execute(CONSTRAINT)
    role = getattr(settings, "AUDIT_RUNTIME_ROLE", "")
    if role:
        if not IDENTIFIER.fullmatch(role):
            raise ValueError("AUDIT_RUNTIME_ROLE must be a plain PostgreSQL role name.")
        quoted = schema_editor.quote_name(role)
        schema_editor.execute(f"GRANT EXECUTE ON FUNCTION audit_prune(text, bigint) TO {quoted}")
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            migrating_as = cursor.fetchone()[0]
        if migrating_as != role:
            # The runtime may append and read the trail, never rewrite it.
            schema_editor.execute(
                f"REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditevent FROM {quoted}"
            )


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE audit_auditevent DROP CONSTRAINT IF EXISTS audit_event_is_chained"
    )
    schema_editor.execute("DROP FUNCTION IF EXISTS audit_prune(text, bigint)")
    schema_editor.execute(
        """
CREATE OR REPLACE FUNCTION audit_block_mutation() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('app.audit_maintenance', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'audit_auditevent is append-only (%% refused)', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""
    )


class Migration(migrations.Migration):
    dependencies = [("audit", "0003_immutable_trigger")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(forwards, backwards)],
            state_operations=[
                migrations.AddConstraint(
                    model_name="auditevent",
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            ("seq__isnull", False), models.Q(("hash", ""), _negated=True)
                        ),
                        name="audit_event_is_chained",
                    ),
                )
            ],
        )
    ]
