# Generated by Django 4.2.1 on 2024-02-16 07:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('editable_messages', '0007_alter_tgmessageseries_language_code'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tgmessageseries',
            options={'permissions': [('can_change_ready_messages', 'Can change ready messages')], 'verbose_name': 'Сообщение бота', 'verbose_name_plural': 'Сообщения бота'},
        ),
    ]
