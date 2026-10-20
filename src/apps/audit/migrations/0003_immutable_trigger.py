"""PostgreSQL trigger: UPDATE, DELETE and TRUNCATE on the audit table raise.

The ORM already refuses these; the trigger refuses them for everyone else (a console, a
migration gone wrong, a compromised application account). The retention job sets
``app.audit_maintenance = 'on'`` inside its own transaction to be allowed to DELETE. Other
databases (SQLite in development and tests) skip this migration.
"""

from django.db import migrations

CREATE = """
CREATE OR REPLACE FUNCTION audit_block_mutation() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' AND current_setting('app.audit_maintenance', true) = 'on' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'audit_auditevent is append-only (%% refused)', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_auditevent_immutable ON audit_auditevent;
CREATE TRIGGER audit_auditevent_immutable
  BEFORE UPDATE OR DELETE ON audit_auditevent
  FOR EACH ROW EXECUTE FUNCTION audit_block_mutation();

DROP TRIGGER IF EXISTS audit_auditevent_no_truncate ON audit_auditevent;
CREATE TRIGGER audit_auditevent_no_truncate
  BEFORE TRUNCATE ON audit_auditevent
  FOR EACH STATEMENT EXECUTE FUNCTION audit_block_mutation();
"""

DROP = """
DROP TRIGGER IF EXISTS audit_auditevent_immutable ON audit_auditevent;
DROP TRIGGER IF EXISTS audit_auditevent_no_truncate ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_block_mutation();
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(DROP)


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_hash_chain")]
    operations = [migrations.RunPython(forwards, backwards)]
