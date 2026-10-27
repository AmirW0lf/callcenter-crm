import sys
import os

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Move the follow-up-sidebar from before call-save to after call-save
fu_block = '          <div id="follow-up-sidebar" class="panel call-logs-sidebar" hidden>\n            <div class="top"><h2>تاریخچه پیگیری‌ها</h2></div>\n            <div id="follow-up-sidebar-list" class="call-logs-list"></div>\n          </div>\n'

# Remove it from its current position (before call-save)
old = fu_block + '          <section class="panel call-save">'
new = '          <section class="panel call-save">'

count = content.count(old)
print(f"Found {count} occurrences of the pattern to remove")

if count > 0:
    content = content.replace(old, new, 1)
    
    # Now add it after </section> but before </div>
    insert_marker = '        </div>\n        <script>'
    insert_count = content.count(insert_marker)
    print(f"Found {insert_count} occurrences of insert marker")
    
    idx = content.find(insert_marker)
    if idx >= 0:
        # Insert after the </section> that comes before </div>
        content = content[:idx] + fu_block + '        </div>\n        <script>'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Verify
        verify_content = open(filepath, 'r', encoding='utf-8').read()
        if 'follow-up-sidebar' in verify_content:
            idx2 = verify_content.find('follow-up-sidebar')
            before = verify_content[idx2-60:idx2]
            after = verify_content[idx2:idx2+120]
            print(f"SUCCESS! follow-up-sidebar now positioned after:")
            print(f"  Before: {repr(before)}")
            print(f"  After: {repr(after)}")
        else:
            print("ERROR: follow-up-sidebar not found after operation!")
    else:
        print("ERROR: Could not find insert marker")
else:
    print("ERROR: Could not find the pattern to remove")
    # Debug
    idx_fu = content.find('follow-up-sidebar')
    idx_cs = content.find('call-save')
    if idx_fu >= 0 and idx_cs >= 0:
        print(f"follow-up-sidebar at {idx_fu}, call-save at {idx_cs}")
        between = content[idx_fu:idx_cs+50]
        print(f"Content between them: {repr(between[:200])}")
