# Generated by Django 2.2.8 on 2020-07-12 23:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0018_auto_20181223_0538'),
    ]

    operations = [
        migrations.AlterField(
            model_name='processcontent',
            name='process',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='content', to='tools.Process'),
        ),
    ]