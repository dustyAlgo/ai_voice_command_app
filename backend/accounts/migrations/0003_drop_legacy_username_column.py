from django.db import migrations


def drop_legacy_username_column(apps, schema_editor):
    table_name = "accounts_user"
    column_name = "username"

    with schema_editor.connection.cursor() as cursor:
        table_description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
        existing_columns = {col.name for col in table_description}

    if column_name not in existing_columns:
        return

    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}" CASCADE')
    elif vendor == "sqlite":
        # Modern SQLite versions support DROP COLUMN.
        schema_editor.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}"')
    else:
        # Fallback best-effort for other engines.
        schema_editor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_managers"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_username_column, migrations.RunPython.noop),
    ]
