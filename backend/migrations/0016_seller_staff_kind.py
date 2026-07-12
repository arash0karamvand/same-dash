from django.db import migrations, models


def classify_existing_staff(apps, schema_editor):
    Seller = apps.get_model("backend", "Seller")
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    manager_groups = {"admin", "sales_manager"}
    manager_user_ids = set(
        User.objects.filter(groups__name__in=manager_groups).values_list("id", flat=True)
    )
    manager_user_ids.update(User.objects.filter(is_superuser=True).values_list("id", flat=True))

    Seller.objects.filter(user_id__in=manager_user_ids).update(staff_kind="manager")


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0015_product_fabric_customer_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="seller",
            name="staff_kind",
            field=models.CharField(
                choices=[("seller", "فروشنده"), ("manager", "مدیر")],
                db_index=True,
                default="seller",
                max_length=20,
                verbose_name="نوع پرسنل",
            ),
        ),
        migrations.RunPython(classify_existing_staff, migrations.RunPython.noop),
    ]
