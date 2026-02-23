import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

def check_structure():
    with connection.cursor() as cursor:
        cursor.execute("SHOW CREATE TABLE dashboard_tradesignal")
        row = cursor.fetchone()
        if row:
            print("--- TABLE DEFINITION ---")
            print(row[1])
            print("------------------------")
        else:
            print("Table dashboard_tradesignal not found.")

if __name__ == "__main__":
    check_structure()
