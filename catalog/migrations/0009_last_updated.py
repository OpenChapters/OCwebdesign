from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_author_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="chapter",
            name="last_updated",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
