# Generated by Django 2.2.3 on 2019-08-22 14:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('idenick_app', '0003_auto_20190822_2240'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employeerequest',
            name='employee',
            field=models.ForeignKey(db_column='usersid', on_delete=django.db.models.deletion.CASCADE, to='idenick_app.Employee'),
        ),
    ]
