STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Unificar: usar solo la carpeta static del app 'dashboard'
STATICFILES_DIRS = [
    BASE_DIR / 'dashboard' / 'static',   # fuente de archivos estáticos durante desarrollo
]