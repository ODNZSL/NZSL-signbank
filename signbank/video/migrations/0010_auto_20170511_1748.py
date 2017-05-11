# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-05-11 14:48
from __future__ import unicode_literals

from django.db import migrations, models
import signbank.video.models


class Migration(migrations.Migration):

    dependencies = [
        ('video', '0009_auto_20170509_1929'),
    ]

    operations = [
        migrations.AlterField(
            model_name='glossvideo',
            name='posterfile',
            field=models.FileField(blank=True, default=b'', help_text='Still image representation of the video.', storage=signbank.video.models.GlossVideoStorage(), upload_to=b'glossvideo/posters', verbose_name='Poster file'),
        ),
    ]
