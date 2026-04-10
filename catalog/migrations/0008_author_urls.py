from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0007_populate_mse_discipline"),
    ]

    operations = [
        migrations.AddField(
            model_name="chapter",
            name="author_urls",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
