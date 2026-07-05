# Generated manually

from django.db import migrations


def remove_legacy_roles(apps, schema_editor):
    from logic.role_definitions import seed_builtin_roles

    seed_builtin_roles()


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0013_product_catalog"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_roles, migrations.RunPython.noop),
    ]
