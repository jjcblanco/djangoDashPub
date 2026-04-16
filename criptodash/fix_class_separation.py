#!/usr/bin/env python3
"""
Fix missing newline between 'return 0' and 'class HyperliquidWhaleTracker'
Run: python fix_class_separation.py
"""

import os
import re

def main():
    file_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'services.py')
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"📄 Reading {file_path}...")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the problematic pattern: 'return 0' followed immediately by 'class'
    # with optional whitespace but no newline
    pattern = r'(return\s+0)\s*(class\s+HyperliquidWhaleTracker:)'
    
    # Search for the pattern
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print(f"✅ Found problematic pattern at position {match.start()}")
        print(f"   Match: {match.group()[:50]}...")
        
        # Replace with proper separation
        new_content = re.sub(pattern, r'\1\n\n\2', content, flags=re.DOTALL)
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        print("✅ Fixed: Added newline between 'return 0' and 'class HyperliquidWhaleTracker'")
        
        # Show the fixed lines
        lines = new_content.split('\n')
        for i, line in enumerate(lines):
            if 'class HyperliquidWhaleTracker:' in line:
                start = max(0, i-3)
                end = min(len(lines), i+2)
                print(f"\n📝 Fixed lines {start+1}-{end+1}:")
                for j in range(start, end):
                    print(f"{j+1:4}: {lines[j]}")
                break
    else:
        print("⚠️ Pattern not found. Checking for other issues...")
        
        # Check if classes are properly separated
        class_pattern = r'(return\s+0[^\\n]*)(class\s+\w+:)'
        matches = list(re.finditer(class_pattern, content, re.DOTALL))
        if matches:
            print(f"Found {len(matches)} potential issues:")
            for m in matches:
                print(f"  - {m.group()[:60]}...")
            
            # Fix all
            new_content = re.sub(class_pattern, r'\1\n\n\2', content, flags=re.DOTALL)
            with open(file_path, 'w') as f:
                f.write(new_content)
            print("✅ Fixed all class separation issues")
        else:
            print("✅ No class separation issues found")
    
    # Also ensure there are two blank lines between top-level classes
    print("\n🔍 Ensuring proper class separation (PEP 8)...")
    lines = content.split('\n')
    new_lines = []
    in_multiline_string = False
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Check if this line starts a class definition (not indented)
        if line.strip().startswith('class ') and not line.startswith(' ' * 4):
            # Look ahead to see if next line is also a class
            if i + 1 < len(lines) and lines[i + 1].strip().startswith('class '):
                # Need a blank line between them
                new_lines.append('')
    
    if len(new_lines) != len(lines):
        with open(file_path, 'w') as f:
            f.write('\n'.join(new_lines))
        print("✅ Added missing blank lines between classes")
    
    # Test compilation
    print("\n🧪 Testing compilation...")
    import subprocess
    result = subprocess.run(['python', '-m', 'py_compile', file_path], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Compilation successful")
    else:
        print(f"❌ Compilation failed:")
        print(result.stderr)
    
    return True

if __name__ == '__main__':
    print("🔧 Fixing class separation syntax error")
    print("="*60)
    main()
    print("\n🚀 Next: Restart Celery with: sudo systemctl restart celery")