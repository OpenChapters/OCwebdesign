from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_full_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='share_builds',
            field=models.BooleanField(default=False),
        ),
    ]
