from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0008_remove_message_image_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="sfx_choice",
            field=models.CharField(
                default="ping",
                help_text="Sound played when this message appears (files in assets/sfx).",
                max_length=64,
            ),
        ),
    ]
