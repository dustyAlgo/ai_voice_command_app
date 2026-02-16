# Generated manually to support size-aware voice search.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="size",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
