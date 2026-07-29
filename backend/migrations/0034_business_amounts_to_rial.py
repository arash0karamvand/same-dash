"""تبدیل مبالغ عملیاتی از تومان به ریال — اسناد AccountingEntry از قبل ریال هستند."""

from django.db import migrations, models

from logic.accounting_money import BUSINESS_MONEY_MODEL_FIELDS, TOMAN_TO_RIAL


def multiply_business_amounts(apps, schema_editor):
    factor = TOMAN_TO_RIAL
    for model_name, fields in BUSINESS_MONEY_MODEL_FIELDS:
        Model = apps.get_model("backend", model_name)
        for obj in Model.objects.all().iterator():
            changed = False
            for name in fields:
                val = getattr(obj, name, None)
                if val is None or val == 0:
                    continue
                setattr(obj, name, val * factor)
                changed = True
            if changed:
                obj.save()


def divide_business_amounts(apps, schema_editor):
    factor = TOMAN_TO_RIAL
    for model_name, fields in BUSINESS_MONEY_MODEL_FIELDS:
        Model = apps.get_model("backend", model_name)
        for obj in Model.objects.all().iterator():
            changed = False
            for name in fields:
                val = getattr(obj, name, None)
                if val is None or val == 0:
                    continue
                setattr(obj, name, val // factor)
                changed = True
            if changed:
                obj.save()


def refresh_sms_templates(apps, schema_editor):
    Settings = apps.get_model("backend", "SmsClubSettings")
    for s in Settings.objects.all():
        tpl = (s.order_placed_template or "").replace("تومان", "ریال")
        if tpl != s.order_placed_template:
            s.order_placed_template = tpl
            s.save(update_fields=["order_placed_template"])


class Migration(migrations.Migration):

    dependencies = [
        ("backend", "0033_accounting_entry_manual_type"),
    ]

    operations = [
        migrations.RunPython(multiply_business_amounts, divide_business_amounts),
        migrations.RunPython(refresh_sms_templates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sale",
            name="discount",
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=18, verbose_name="تخفیف (ریال)"
            ),
        ),
        migrations.AlterField(
            model_name="officeorder",
            name="discount",
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=18, verbose_name="تخفیف (ریال)"
            ),
        ),
    ]