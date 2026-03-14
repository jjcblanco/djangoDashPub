import os
import sys

# 1. Cargar .env manualmente
def load_env_manually():
    try:
        # Buscar .env en el directorio actual o el anterior
        env_path = '.env'
        if not os.path.exists(env_path):
            env_path = os.path.join('..', '.env')
        
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value.strip('"').strip("'")
            print(f"[OK] .env cargado desde {env_path}")
        else:
            print("[!] AVISO: No se encontró el archivo .env")
    except Exception as e:
        print(f"[!] Error cargando .env: {e}")

load_env_manually()

# 2. Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
try:
    import django
    from django.core.management import call_command
    django.setup()
    print("[OK] Django configurado.")
except Exception as e:
    print(f"[ERROR CRÍTICO] No se pudo iniciar Django: {e}")
    sys.exit(1)

# 3. Ejecutar Migraciones
print("\n--- Ejecutando Migraciones en VPS ---")
try:
    call_command('migrate')
    print("\n[ÉXITO] Migraciones aplicadas correctamente.")
except Exception as e:
    print(f"\n[ERROR] Falló la migración: {e}")
    import traceback
    traceback.print_exc()
