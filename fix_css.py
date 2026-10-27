import sys
filepath = 'app.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = '.call-log-empty{color:var(--muted);font-size:14px;padding:10px 0;font-style:italic}'
new = old + '.status-pending{background:var(--sand);color:var(--deep)}.status-done{background:#dce8df;color:#256;border:1px solid #4a9}.status-cancelled{background:#ead5dc;color:#a22;border:1px solid #c66}'

if old in content:
    content = content.replace(old, new, 1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: CSS status pill styles added")
else:
    print("FAILED: Could not find old string")
    idx = content.find('call-log-empty')
    if idx >= 0:
        print(f"Found 'call-log-empty' at position {idx}")
        print(repr(content[idx:idx+120]))
    else:
        print("String 'call-log-empty' not found in file!")
