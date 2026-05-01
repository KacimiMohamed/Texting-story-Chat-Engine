# Generated manually to bootstrap the project structure.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Character",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "color",
                    models.CharField(
                        help_text="Hex color (e.g. #22c55e)", max_length=20
                    ),
                ),
                (
                    "avatar",
                    models.ImageField(blank=True, null=True, upload_to="avatars/"),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Story",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("bg_color", models.CharField(default="#ffffff", max_length=20)),
                (
                    "characters",
                    models.ManyToManyField(
                        blank=True, related_name="stories", to="creator.character"
                    ),
                ),
            ],
            options={"verbose_name_plural": "stories", "ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text", models.TextField()),
                (
                    "image_file",
                    models.ImageField(blank=True, null=True, upload_to="messages/"),
                ),
                (
                    "delay",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Delay in milliseconds before showing this message.",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="messages",
                        to="creator.character",
                    ),
                ),
                (
                    "story",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="messages",
                        to="creator.story",
                    ),
                ),
            ],
            options={"ordering": ["story", "order", "created_at", "id"]},
        ),
    ]
