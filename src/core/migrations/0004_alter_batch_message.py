# Generated by Django 5.0.6 on 2024-07-07 19:24

from django.db import migrations, models


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
    ]
