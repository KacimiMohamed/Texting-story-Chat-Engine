from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("creator", "0004_character_elevenlabs_voice_id_message_audio_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="sender",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sent_stories",
                to="creator.character",
            ),
        ),
    ]
