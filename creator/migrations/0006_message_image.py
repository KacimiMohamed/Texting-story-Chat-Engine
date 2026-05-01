from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0005_story_sender"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="chat_images/"),
        ),
    ]
