import json
import re

with open('mongodb_export.json', 'r') as f:
    docs = json.load(f)

problem_keys = []
for doc in docs:
    identifier = doc.get('identifier', '')
    key = identifier.replace('/', '_').replace(':', '_').replace('.', '_')
    if not key or not re.match(r'^[a-zA-Z0-9_-]+$', key):
        problem_keys.append((identifier, key))

print(f'Found {len(problem_keys)} problematic keys')
if problem_keys[:10]:
    print('Examples:')
    for orig, sanitized in problem_keys[:10]:
        print(f'  Original: {orig!r}')
        print(f'  Sanitized: {sanitized!r}')
        print()
