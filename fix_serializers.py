import re
import os
import glob

files_to_fix = glob.glob('app/**/*serializers.py', recursive=True)

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, "r") as f:
        content = f.read()

    # Add import if missing
    if "from drf_spectacular.utils import extend_schema_field" not in content and "SerializerMethodField" in content:
        content = "from drf_spectacular.utils import extend_schema_field\n" + content

    lines = content.split('\n')
    new_lines = []
    
    for idx, line in enumerate(lines):
        # Check if it's a get_ method for SerializerMethodField
        match = re.match(r'^(\s+)def get_([a-zA-Z0-9_]+)\(self, obj.*', line)
        if match:
            indent = match.group(1)
            
            # Check if there's already an extend_schema_field above it
            has_decorator = False
            for i in range(1, 4):
                if idx - i >= 0:
                    prev_line = lines[idx - i].strip()
                    if prev_line.startswith('@extend_schema_field'):
                        has_decorator = True
                        break
                    if prev_line.startswith('def ') or prev_line.startswith('class '):
                        break
            
            if not has_decorator:
                new_lines.append(f"{indent}@extend_schema_field(serializers.CharField(allow_null=True))")
        
        new_lines.append(line)
        
    with open(filepath, "w") as f:
        f.write('\n'.join(new_lines))

print("Done serializers")
