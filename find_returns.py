import os
import ast

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except Exception:
            return

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.endswith('Event'):
            for child in ast.walk(node):
                if isinstance(child, ast.Return):
                    if child.value is None:
                        continue
                    if isinstance(child.value, ast.Name) and child.value.id == 'None':
                        continue
                    if node.name in ('eventFilter', 'event'):
                        continue # These are allowed to return bool
                    if isinstance(child.value, ast.Call) and isinstance(child.value.func, ast.Attribute) and child.value.func.attr == node.name:
                        continue # super().somethingEvent(event) which might return None
                    print(f"{filepath}:{child.lineno} - {node.name} returns a value")

for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.py'):
            check_file(os.path.join(root, f))
