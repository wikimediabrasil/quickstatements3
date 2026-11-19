from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_alter_batchcommand_operation'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='batchcommand',
            index=models.Index(fields=['created'], name='core_batchcommand_created_idx'),
        ),
    ]
