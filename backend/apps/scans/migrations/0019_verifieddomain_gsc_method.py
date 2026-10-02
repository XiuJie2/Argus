from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scans", "0018_siteproject_scanjob_project")]

    operations = [
        migrations.AlterField(
            model_name="verifieddomain",
            name="method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("dns_txt", "DNS TXT 記錄"),
                    ("meta_tag", "HTML meta 標籤"),
                    ("html_file", "驗證檔案"),
                    ("gsc", "Google Search Console"),
                ],
                default="",
                max_length=16,
            ),
        ),
    ]
