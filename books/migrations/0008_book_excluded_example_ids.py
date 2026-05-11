from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0007_book_include_examples_book_include_solutions'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='excluded_example_ids',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
