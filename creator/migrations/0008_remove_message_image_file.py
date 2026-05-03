from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0007_alter_message_text"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="message",
            name="image_file",
        ),
    ]
