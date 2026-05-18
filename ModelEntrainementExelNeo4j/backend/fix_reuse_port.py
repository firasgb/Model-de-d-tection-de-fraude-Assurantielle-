import sys
sys.path.insert(0, r'C:\Users\firas\Desktop\ModelEntrainementExelNeo4j\ModelEntrainementExelNeo4j\backend')

with open(r'C:\Users\firas\Desktop\ModelEntrainementExelNeo4j\ModelEntrainementExelNeo4j\backend\main.py', encoding='utf-8', errors='replace') as f:
    content = f.read()

old = 'uvicorn.run(app, host="0.0.0.0", port=8000)'
new = 'uvicorn.run(app, host="0.0.0.0", port=8000, reuse_port=True)'

if old in content:
    content = content.replace(old, new)
    with open(r'C:\Users\firas\Desktop\ModelEntrainementExelNeo4j\ModelEntrainementExelNeo4j\backend\main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed: reuse_port=True added')
else:
    print('Pattern not found, checking what is there...')
    for i, line in enumerate(content.split('\n')):
        if 'uvicorn.run' in line:
            print(f'  Line {i+1}: {line!r}')