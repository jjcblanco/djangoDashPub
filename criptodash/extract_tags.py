import re

def extract_all_tags(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # regex for any Django tag {% ... %}
    # We use non-greedy matching but allow spanning lines
    pattern = re.compile(r'{%.*?%}', re.DOTALL)
    
    matches = pattern.finditer(content)
    for match in matches:
        line_no = content.count('\n', 0, match.start()) + 1
        tag_content = match.group()
        # If the tag is split across lines, show it
        if '\n' in tag_content:
            print(f"SPLIT TAG at line {line_no}: {repr(tag_content)}")
        else:
            print(f"{line_no}: {tag_content}")

if __name__ == "__main__":
    extract_all_tags('dashboard/templates/dashboard/bot_dashboard.html')
