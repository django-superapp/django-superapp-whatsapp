# Generated by Django 5.1.8 on 2025-04-05 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0006_alter_message_media_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='media_url',
            field=models.FileField(blank=True, null=True, upload_to='whatsapp_media/', verbose_name='Media URL'),
        ),
    ]
