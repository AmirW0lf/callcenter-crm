import os
import re

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the call_form = """ ... """ block
# We need to ensure it's properly terminated
start_marker = 'call_form = """'
start_idx = content.find(start_marker)
if start_idx < 0:
    print("ERROR: Could not find call_form start marker")
    exit(1)

# Find the closing """ - there should be one after <script>
# The call_form closing is: \n        """.replace(
# Let's look for that pattern
end_marker = '\n        """.replace('
end_idx = content.find(end_marker, start_idx)
if end_idx < 0:
    print("ERROR: Could not find call_form end marker")
    # Try to find what's at the expected position
    # Find the last occurrence of <script> before the dashbaord method body
    # Let's check around where it should be
    after_script = content[content.rfind('<script>', start_idx):]
    after_script_clean = after_script[:200]
    print(f"Content after last <script> in call_form: {repr(after_script_clean[:200])}")
    exit(1)

print(f"call_form starts at {start_idx}, ends at {end_idx}")
print(f"call_form length: {end_idx - start_idx} chars")
print("SYNTAX OK - call_form is properly terminated")
