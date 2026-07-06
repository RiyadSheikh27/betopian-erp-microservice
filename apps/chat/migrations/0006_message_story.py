import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0005_callsession"),
        ("story", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="story",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reply_messages",
                to="story.story",
            ),
        ),
    ]
