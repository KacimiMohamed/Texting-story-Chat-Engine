from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0006_message_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="text",
            field=models.TextField(blank=True, null=True),
        ),
    ]
