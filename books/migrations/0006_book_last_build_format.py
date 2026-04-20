# Generated for build format retention support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0005_book_html_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='last_build_format',
            field=models.CharField(
                choices=[('pdf', 'PDF'), ('html', 'HTML'), ('both', 'PDF + HTML')],
                default='pdf',
                help_text='Format selected for the most recent build; used by Retry.',
                max_length=8,
            ),
        ),
    ]
