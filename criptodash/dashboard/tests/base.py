"""
Base de tests con SQLite in-memory y caché en memoria local.

Evita depender de MySQL/Redis: override de DATABASES a SQLite in-memory
y CACHES a LocMemCache. Las migraciones de dashboard corren contra
SQLite (0039/0040 son portables).
"""
from django.test import TestCase, override_settings

SQLITE_DB = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}


@override_settings(DATABASES=SQLITE_DB, CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
})
class SQLiteTestCase(TestCase):
    """TestCase con SQLite in-memory y LocMemCache (sin Redis)."""
    pass
