from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("creator", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="sfx_choice",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("ping", "Ping"),
                    ("vine_boom", "Vine Boom"),
                    ("bruh", "Bruh"),
                    ("camera_shutter", "Camera Shutter"),
                    ("notification", "Notification"),
                ],
                default="ping",
                max_length=32,
            ),
        ),
    ]
