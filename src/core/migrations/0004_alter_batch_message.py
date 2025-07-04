# Generated by Django 5.0.6 on 2024-07-07 19:24

from django.db import migrations, models


def set_nulls_to_empty(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    Batch = apps.get_model("core", "Batch")
    for b in Batch.objects.using(db_alias).filter(message__isnull=True).all():
        b.message = ""
        b.save()

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_batch_created_alter_batch_modified_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batch",
            name="message",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(
            code=migrations.RunPython.noop,
            reverse_code=set_nulls_to_empty,
        ),
    ]
