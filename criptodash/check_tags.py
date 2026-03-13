import re

def check_balance_robust(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # regex for Django tags: {% tag ... %}
    pattern = re.compile(r'{%\s*(if|elif|else|endif|for|empty|endfor|block|endblock|with|endwith)\b[^%]*%}')
    
    stack = []
    
    # We'll use finditer to iterate over all matches in the whole content
    for match in pattern.finditer(content):
        tag = match.group(1)
        # Find line number
        line_no = content.count('\n', 0, match.start()) + 1
        
        if tag in ('if', 'for', 'block', 'with'):
            stack.append((tag, line_no))
        elif tag == 'endif':
            if not stack:
                print(f"Error: Orphaned 'endif' on line {line_no}")
            elif stack[-1][0] != 'if':
                print(f"Error: 'endif' on line {line_no} mismatch with '{stack[-1][0]}' from line {stack[-1][1]}")
            else:
                stack.pop()
        elif tag == 'endfor':
            if not stack:
                print(f"Error: Orphaned 'endfor' on line {line_no}")
            elif stack[-1][0] != 'for':
                print(f"Error: 'endfor' on line {line_no} mismatch with '{stack[-1][0]}' from line {stack[-1][1]}")
            else:
                stack.pop()
        elif tag == 'endblock':
            if not stack:
                print(f"Error: Orphaned 'endblock' on line {line_no}")
            elif stack[-1][0] != 'block':
                print(f"Error: 'endblock' on line {line_no} mismatch with '{stack[-1][0]}' from line {stack[-1][1]}")
            else:
                stack.pop()
        elif tag == 'endwith':
            if not stack:
                print(f"Error: Orphaned 'endwith' on line {line_no}")
            elif stack[-1][0] != 'with':
                print(f"Error: 'endwith' on line {line_no} mismatch with '{stack[-1][0]}' from line {stack[-1][1]}")
            else:
                stack.pop()
    
    if stack:
        print("Unclosed tags remaining:")
        for tag, line in stack:
            print(f"- {tag} started on line {line}")

if __name__ == "__main__":
    check_balance_robust('dashboard/templates/dashboard/bot_dashboard.html')
