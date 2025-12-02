# Generated migration to remove CHECK constraint on indicators field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),  # Ajusta esto al número de tu última migración
    ]

    operations = [
        migrations.RunSQL(
            # Remove the CHECK constraint on indicators field
            sql="""
                ALTER TABLE dashboard_tradesignal 
                DROP CHECK dashboard_tradesignal_chk_1;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
