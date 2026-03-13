import os
import django
from django.template import Template, Context, loader
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

def check_template_detailed(template_name):
    try:
        t = loader.get_template(template_name)
        print(f"Template {template_name} parsed successfully.")
    except Exception as e:
        print(f"Error in template {template_name}:")
        print(e)
        if hasattr(e, 'token'):
            token = e.token
            print(f"Token: {token.contents} at line {token.lineno}")
        if hasattr(e, 'template_debug'):
            debug = e.template_debug
            print(f"Debug info: {debug}")

if __name__ == "__main__":
    check_template_detailed('dashboard/bot_dashboard.html')
