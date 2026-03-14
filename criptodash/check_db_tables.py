import os
import django
from django.db import connection

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

def check_tables():
    tables = connection.introspection.table_names()
    print("--- Tablas detectadas en la DB ---")
    essential_tables = [
        'dashboard_whalewallet',
        'dashboard_whaletransaction',
        'dashboard_patterninsight'
    ]
    
    for table in essential_tables:
        exists = table in tables
        print(f"{table}: {'[OK]' if exists else '[MISSING]!!!'}")
        
    if all(table in tables for table in essential_tables):
        print("\n--- Columnas en dashboard_whaletransaction ---")
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE dashboard_whaletransaction")
            for row in cursor.fetchall():
                print(row)

if __name__ == "__main__":
    check_tables()
