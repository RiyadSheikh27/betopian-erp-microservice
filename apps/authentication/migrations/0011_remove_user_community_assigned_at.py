from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_user_is_online_user_last_seen"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="community_assigned_at",
        ),
    ]
