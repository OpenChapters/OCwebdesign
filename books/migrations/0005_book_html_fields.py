# Generated for book HTML output support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0004_add_doi'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='html_path',
            field=models.CharField(
                blank=True,
                help_text='Filesystem path to the directory containing the built HTML output.',
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name='book',
            name='html_built_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
