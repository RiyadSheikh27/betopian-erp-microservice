# Generated migration for adding profile fields to MeetingParticipant

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mom", "0008_remove_meeting_is_pinned_meetingnote_is_pinned"),
    ]

    operations = [
        migrations.AddField(
            model_name="meetingparticipant",
            name="employee_id",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="meetingparticipant",
            name="username",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="meetingparticipant",
            name="avatar_url",
            field=models.URLField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="meetingparticipant",
            name="designation",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
