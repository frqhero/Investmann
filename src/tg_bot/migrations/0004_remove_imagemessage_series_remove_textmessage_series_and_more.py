# Generated by Django 4.2.1 on 2024-01-26 18:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tg_bot', '0003_messageseries_textmessage_imagemessage_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imagemessage',
            name='series',
        ),
        migrations.RemoveField(
            model_name='textmessage',
            name='series',
        ),
        migrations.DeleteModel(
            name='DocumentMessage',
        ),
        migrations.DeleteModel(
            name='ImageMessage',
        ),
        migrations.DeleteModel(
            name='MessageSeries',
        ),
        migrations.DeleteModel(
            name='TextMessage',
        ),
    ]