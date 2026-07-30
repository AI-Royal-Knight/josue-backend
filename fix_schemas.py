import re
import os
import glob

files_to_fix = glob.glob('app/**/*.py', recursive=True)

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, "r") as f:
        content = f.read()
        
    if "APIView" not in content and "def get(self, request" not in content and "def post(self, request" not in content:
        continue

    # Add import if missing
    if "from drf_spectacular.utils import extend_schema" not in content:
        content = "from drf_spectacular.utils import extend_schema\n" + content

    lines = content.split('\n')
    new_lines = []
    
    for idx, line in enumerate(lines):
        # Check if it's a view method
        match = re.match(r'^(\s+)def (get|post|patch|put|delete)\(self, request.*', line)
        if match:
            indent = match.group(1)
            method = match.group(2)
            
            # Check if there's already an extend_schema above it
            has_decorator = False
            for i in range(1, 5):
                if idx - i >= 0:
                    prev_line = lines[idx - i].strip()
                    if prev_line.startswith('@extend_schema') or prev_line.startswith('@swagger_auto_schema'):
                        has_decorator = True
                        break
                    if prev_line.startswith('def ') or prev_line.startswith('class '):
                        break
            
            if not has_decorator:
                if method in ['get', 'delete']:
                    new_lines.append(f"{indent}@extend_schema(responses={{200: dict}})")
                else:
                    new_lines.append(f"{indent}@extend_schema(request=dict, responses={{200: dict}})")
        
        new_lines.append(line)
        
    with open(filepath, "w") as f:
        f.write('\n'.join(new_lines))

print("Done views")
