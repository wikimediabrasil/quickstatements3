# Generated by Django 5.0.9 on 2025-05-10 00:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_alter_batchcommand_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Label',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_id', models.CharField(db_index=True, max_length=20)),
                ('language', models.CharField(db_index=True, max_length=5)),
                ('value', models.CharField(max_length=300)),
            ],
        ),
        migrations.AddConstraint(
            model_name='label',
            constraint=models.UniqueConstraint(fields=('entity_id', 'language'), name='unique_language_per_entity'),
        ),
        migrations.AddField(
            model_name='batchcommand',
            name='labels',
            field=models.ManyToManyField(to='core.label'),
        ),
    ]
