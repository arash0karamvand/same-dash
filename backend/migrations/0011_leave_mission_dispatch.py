from django.db import migrations, models


def seed_mission_status(apps, schema_editor):
    AttendanceStatus = apps.get_model("backend", "AttendanceStatus")
    AttendanceStatus.objects.update_or_create(
        code="mission",
        defaults={"label": "ماموریت", "sort_order": 3, "is_active": True},
    )


def unseed_mission_status(apps, schema_editor):
    AttendanceStatus = apps.get_model("backend", "AttendanceStatus")
    AttendanceStatus.objects.filter(code="mission").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0010_rfm_cashback"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffattendance",
            name="leave_hours",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="leave_pay_type",
            field=models.CharField(
                blank=True,
                choices=[("paid", "با حقوق"), ("unpaid", "بدون حقوق")],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="mission_dest_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="mission_dest_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("branch", "شعبه"),
                    ("warehouse", "انبار"),
                    ("factory", "کارخانه"),
                    ("outside", "خارج از شرکت"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="staffattendance",
            name="mission_dest_label",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.RunPython(seed_mission_status, unseed_mission_status),
    ]
