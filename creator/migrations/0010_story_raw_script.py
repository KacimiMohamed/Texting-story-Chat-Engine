from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0009_alter_message_sfx_choice"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="raw_script",
            field=models.TextField(
                blank=True,
                null=True,
                help_text="Paste a raw script here to auto-generate messages.",
            ),
        ),
    ]

