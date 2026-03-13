import re

file_path = 'dashboard/templates/dashboard/bot_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to find the split endif
# id="notifEnabledSwitch" {% if global_settings.notifications_enabled %}checked{% endif
#                                 %}>
pattern = re.compile(r'{% if global_settings\.notifications_enabled %}checked{% endif\s+%}', re.MULTILINE)

new_content = pattern.sub(r'{% if global_settings.notifications_enabled %}checked{% endif %}', content)

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Sucessfully fixed the split endif tag.")
else:
    # Try a broader match if the specific one failed
    print("Specific pattern not found, trying broader match...")
    pattern2 = re.compile(r'{%\s*if global_settings\.notifications_enabled\s*%}checked{%\s*endif\s*%}', re.MULTILINE | re.DOTALL)
    # Actually let's just look for the literal strings
    if '{% endif\n' in content:
        content = content.replace('{% endif\n', '{% endif %}\n')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Fixed by literal replacement of {% endif\n")
    else:
        print("Could not find the problematic tag with either method.")
