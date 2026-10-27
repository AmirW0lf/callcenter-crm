with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f"Total lines: {len(lines)}")
for i, line in enumerate(lines):
    if 'def ' in line and 'follow' in line.lower():
        print(f"Line {i+1}: {line.rstrip()}")
# Also try to find the method without 'def' prefix
print("---Searching for followup_action---")
for i, line in enumerate(lines):
    if 'followup_action' in line:
        print(f"Line {i+1}: {line.rstrip()[:200]}")
