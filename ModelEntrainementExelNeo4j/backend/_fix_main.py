import sys
path = r'C:\Users\firas\Desktop\ModelEntrainementExelNeo4j\ModelEntrainementExelNeo4j\backend\main.py'
with open(path, encoding='utf-8', errors='replace') as f:
    content = f.read()

old_line = 'uvicorn.run(app, host="0.0.0.0", port=8000, reuse_port=True)'
if old_line in content:
    new_lines = """import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("0.0.0.0", 8000))
    sock.close()
    uvicorn.run(app, host="0.0.0.0", port=8000, reuse_port=True)"""
    content = content.replace(old_line, new_lines)
    print("Old line found. Replacing...")
    
    # Remove the import uvicorn if it exists right before, and add socket import
    content = content.replace(
        'if __name__ == "__main__":\n    import uvicorn',
        'if __name__ == "__main__":\n    import uvicorn\n    import socket'
    )
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done. File updated.")
else:
    print("Old line NOT found. Printing surrounding context:")
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'uvicorn.run' in line or '__main__' in line:
            print(f"  Line {i+1}: {line!r}")