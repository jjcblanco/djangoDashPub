#!/usr/bin/env python
"""
Script de verificación de instalación
Ejecutar: python verify_setup.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

def print_header(text):
    print("\n" + "="*50)
    print(f"  {text}")
    print("="*50)

def check_file(path, description):
    exists = os.path.exists(path)
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {path}")
    return exists

def main():
    print_header("VERIFICACIÓN DE INSTALACIÓN - CRIPTODASH")
    
    # 1. Verificar archivos
    print("\n📁 VERIFICANDO ARCHIVOS...")
    files_ok = True
    
    files_to_check = [
        ("criptodash/settings.py", "Archivo de configuración"),
        ("dashboard/auth_views.py", "Vistas de autenticación"),
        ("dashboard/urls.py", "URLs del dashboard"),
        ("dashboard/templates/dashboard/login.html", "Template de login"),
        ("dashboard/templates/dashboard/register.html", "Template de registro"),
        ("dashboard/templates/dashboard/profile.html", "Template de perfil"),
        ("dashboard/templates/dashboard/index.html", "Template de inicio"),
        ("requirements.txt", "Dependencias Python"),
    ]
    
    for file_path, description in files_to_check:
        full_path = os.path.join("criptodash", file_path)
        if not check_file(full_path, description):
            files_ok = False
    
    # 2. Verificar configuraciones en settings.py
    print("\n🔧 VERIFICANDO CONFIGURACIONES...")
    try:
        django.setup()
        from django.conf import settings
        
        # MySQL
        db_engine = settings.DATABASES['default']['ENGINE']
        is_mysql = 'mysql' in db_engine
        print(f"{'✅' if is_mysql else '❌'} Base de datos: {db_engine}")
        
        # allauth
        has_allauth = 'allauth' in settings.INSTALLED_APPS
        print(f"{'✅' if has_allauth else '❌'} django-allauth instalado")
        
        # Sites
        has_sites = 'django.contrib.sites' in settings.INSTALLED_APPS
        print(f"{'✅' if has_sites else '❌'} django.contrib.sites instalado")
        
        # Google OAuth
        has_google = 'allauth.socialaccount.providers.google' in settings.INSTALLED_APPS
        print(f"{'✅' if has_google else '❌'} Google OAuth configurado")
        
        # Authentication backends
        backends = settings.AUTHENTICATION_BACKENDS
        has_model_backend = any('ModelBackend' in b for b in backends)
        has_allauth_backend = any('allauth' in b for b in backends)
        print(f"{'✅' if has_model_backend else '❌'} Backend de Django configurado")
        print(f"{'✅' if has_allauth_backend else '❌'} Backend de allauth configurado")
        
    except Exception as e:
        print(f"❌ Error verificando configuraciones: {e}")
    
    # 3. Verificar dependencias
    print("\n📦 VERIFICANDO DEPENDENCIAS...")
    required_packages = [
        'django',
        'django_allauth',
        'mysqlclient',
        'django_plotly_dash',
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (no instalado)")
    
    # 4. Verificar rutas
    print("\n🛣️  VERIFICANDO RUTAS...")
    try:
        from django.urls import get_resolver
        resolver = get_resolver()
        
        required_urls = [
            'custom_login',
            'custom_register',
            'custom_logout',
            'profile',
            'dashboard_index',
        ]
        
        url_names = [pattern.name for pattern in resolver.url_patterns 
                    if pattern.name and pattern.name in required_urls]
        
        for url_name in required_urls:
            is_found = any(url_name in url_names or 
                          any(url_name in str(p) for p in resolver.url_patterns))
            print(f"{'✅' if url_name in url_names else '⚠️ '} {url_name}")
        
    except Exception as e:
        print(f"⚠️  Error verificando rutas: {e}")
    
    # Resumen final
    print_header("RESUMEN")
    
    if files_ok:
        print("""
✅ VERIFICACIÓN COMPLETADA EXITOSAMENTE

Próximos pasos:
1. Asegúrate de que MySQL está ejecutándose
2. Ejecuta: python manage.py migrate
3. Ejecuta: python manage.py createsuperuser
4. Ejecuta: python manage.py runserver
5. Accede a: http://localhost:8000

Para configurar Google OAuth:
- Sigue la guía en: AUTENTICACION_GUIA.md
- O comienza rápido con: INICIO_RAPIDO.md
        """)
    else:
        print("""
⚠️  ALGUNOS ARCHIVOS FALTAN

Por favor:
1. Asegúrate de estar en el directorio correcto
2. Ejecuta: python verify_setup.py desde la carpeta raíz del proyecto
3. Si persiste, reinstala usando: python manage.py migrate
        """)

if __name__ == '__main__':
    main()
