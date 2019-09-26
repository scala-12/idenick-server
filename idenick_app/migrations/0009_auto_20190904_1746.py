# Generated by Django 2.2.3 on 2019-09-04 09:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('idenick_app', '0008_auto_20190903_1846'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='device_group',
            field=models.ForeignKey(db_column='devicegroupsid', null=True, on_delete=django.db.models.deletion.CASCADE, to='idenick_app.DeviceGroup'),
        ),
        migrations.AlterUniqueTogether(
            name='device',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='device',
            name='organization',
        ),
    ]
