import re

def list_if_tags(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # regex to find all {% if ... %}, {% elif ... %}, {% else %}, {% endif %}
    pattern = re.compile(r'{%\s*(if|elif|else|endif)\b.*?%}', re.DOTALL)
    
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            print(f"{i}: {match.group()}")

if __name__ == "__main__":
    list_if_tags('dashboard/templates/dashboard/bot_dashboard.html')
