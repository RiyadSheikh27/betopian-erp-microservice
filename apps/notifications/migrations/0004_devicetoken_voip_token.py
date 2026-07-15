from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_devicetoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicetoken",
            name="voip_token",
            field=models.TextField(blank=True, null=True),
        ),
    ]
