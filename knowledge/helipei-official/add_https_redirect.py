import os
import re

redirect_script = """<script>
    if (location.protocol === 'http:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
      location.replace(`https:${location.href.substring(location.protocol.length)}`);
    }
  </script>"""

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "location.protocol === 'http:'" in content:
        return # already added

    # Find <head> and insert script right after
    new_content = re.sub(r'(<head.*?>)', r'\1\n  ' + redirect_script, content, flags=re.IGNORECASE)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Added redirect to {filepath}")

for root, dirs, files in os.walk('.'):
    if 'node_modules' in root or '.trae' in root or '.claude' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            process_file(os.path.join(root, file))

print("Done")
