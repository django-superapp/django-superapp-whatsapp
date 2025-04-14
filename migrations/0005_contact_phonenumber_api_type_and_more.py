# Generated by Django 5.1.7 on 2025-04-05 11:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp', '0004_alter_message_options_phonenumber_access_token_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('phone_number', models.CharField(max_length=50, unique=True, verbose_name='Phone Number')),
                ('whatsapp_chat_id', models.CharField(blank=True, help_text='Used by WAHA API', max_length=100, null=True, verbose_name='WhatsApp Chat ID')),
                ('profile_picture_url', models.URLField(blank=True, null=True, verbose_name='Profile Picture URL')),
                ('is_business', models.BooleanField(default=False, verbose_name='Is Business')),
                ('is_verified', models.BooleanField(default=False, verbose_name='Is Verified')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
            ],
            options={
                'verbose_name': 'Contact',
                'verbose_name_plural': 'Contacts',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='api_type',
            field=models.CharField(choices=[('official', 'Official WhatsApp Business API'), ('waha', 'WAHA API')], default='official', max_length=10, verbose_name='API Type'),
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='waha_endpoint',
            field=models.URLField(blank=True, help_text='Full URL to WAHA API (e.g., http://localhost:3000)', null=True, verbose_name='WAHA API Endpoint'),
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='waha_password',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='WAHA Password'),
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='waha_session',
            field=models.CharField(default='default', max_length=100, verbose_name='WAHA Session'),
        ),
        migrations.AddField(
            model_name='phonenumber',
            name='waha_username',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='WAHA Username'),
        ),
        migrations.AlterField(
            model_name='message',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('received', 'Received'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read'), ('failed', 'Failed')], default='received', max_length=10, verbose_name='status'),
        ),
        migrations.AlterField(
            model_name='phonenumber',
            name='phone_number_id',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Phone Number ID'),
        ),
        migrations.AddField(
            model_name='message',
            name='contact',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='messages', to='whatsapp.contact'),
        ),
    ]
