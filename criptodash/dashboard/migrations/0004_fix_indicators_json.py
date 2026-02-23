from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_rename_dashboard_t_pairre_3c9a2f_idx_dashboard_t_pair_re_a4c770_idx_and_more'),
        ('dashboard', '0002_remove_indicators_constraint'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE dashboard_tradesignal MODIFY indicators LONGTEXT NULL;
            """,
            reverse_sql="ALTER TABLE dashboard_tradesignal MODIFY indicators JSON NULL;",
        ),
    ]
