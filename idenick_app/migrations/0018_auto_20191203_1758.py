# Generated by Django 2.2.5 on 2019-12-03 09:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idenick_app', '0017_auto_20191130_0312'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='timezone',
            field=models.DurationField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='timezone',
            field=models.DurationField(blank=True, default=None, null=True),
        ),
    ]
