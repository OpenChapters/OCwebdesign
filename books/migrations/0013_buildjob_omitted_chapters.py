from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0012_defer_epub"),
    ]

    operations = [
        migrations.AddField(
            model_name="buildjob",
            name="omitted_chapters",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
