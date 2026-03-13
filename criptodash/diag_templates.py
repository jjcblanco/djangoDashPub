import os
import django
from django.template import Template, Context, loader
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

def check_template(template_name):
    try:
        t = loader.get_template(template_name)
        print(f"Template {template_name} loaded successfully.")
        # Try a basic render with dummy bot data
        dummy_context = {
            'bots': [],
            'recent_trades': [],
            'available_pairs': [],
            'exchange_balance': {'free': 0},
            'funding_history': []
        }
        t.render(dummy_context)
        print(f"Template {template_name} rendered successfully with dummy data.")
    except Exception as e:
        print(f"Error in template {template_name}:")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_template('dashboard/bot_dashboard.html')
