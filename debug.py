import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
filepath = 'app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
for i in range(max(0, len(lines)-20), len(lines)):
    clean = ''.join(c if ord(c) < 128 else '?' for c in lines[i].rstrip())
    print(f'{i+1}: {clean}')

# Also check lines 905-915 (around where the error is)
print('\n--- Lines 905-915 ---')
for i in range(904, min(915, len(lines))):
    clean = ''.join(c if ord(c) < 128 else '?' for c in lines[i].rstrip())
    print(f'{i+1}: {clean}')
