from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_fix_indicators_json'),
    ]

    operations = [
        migrations.RunSQL(
            # Explicitly modify to LONGTEXT to drop any lingering JSON_VALID constraints
            sql="""
                ALTER TABLE dashboard_tradesignal MODIFY indicators LONGTEXT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
