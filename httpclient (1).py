import socket
import os
import webbrowser
from urllib.parse import urlencode

SERVER_IP = input("Enter the server IP address (e.g., 127.0.0.1 or your host's IP): ").strip()
SERVER_PORT = 8080

http_method = input("Enter HTTP method (GET or POST): ").strip().upper()
request_path = input("Enter request path (e.g., /index.html, /document.pdf, /wow.jpg, /attendance): ").strip()

body_bytes = b""
headers = {
    "Host": SERVER_IP,
    "Connection": "close",
}

# Build request
if http_method == "POST" and request_path == "/attendance":
    student_id = input("Enter your Student ID: ").strip()
    name = input("Enter your Name: ").strip()
    form = {"ID": student_id, "Name": name}
    body_bytes = urlencode(form).encode()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Content-Length"] = str(len(body_bytes))

elif http_method == "POST":
    # Generic POST body if user wants another endpoint
    text = input("Enter data to send in POST request: ")
    body_bytes = text.encode()
    headers["Content-Type"] = "text/plain"
    headers["Content-Length"] = str(len(body_bytes))
else:
    # GET
    headers["Content-Length"] = None  # no body

# Construct the raw HTTP request
request_lines = [f"{http_method} {request_path} HTTP/1.1"]
for k, v in headers.items():
    if v is not None:
        request_lines.append(f"{k}: {v}")
raw_request = ("\r\n".join(request_lines) + "\r\n\r\n").encode() + body_bytes

print("\n--- Sending HTTP Request ---\n")
try:
    # Print headers and possibly the text body (if small)
    if body_bytes and len(body_bytes) < 512:
        print(raw_request.decode(errors="ignore"))
    else:
        print(("\r\n".join(request_lines) + "\r\n\r\n").encode().decode())
        if body_bytes:
            print("(binary or long body omitted)")
except Exception:
    print("(request contains binary data)")

# Send & receive
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((SERVER_IP, SERVER_PORT))
    sock.sendall(raw_request)

    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk

# Parse response
if b"\r\n\r\n" not in response:
    print("\nError: Invalid HTTP response.")
    print(response[:2000])
    raise SystemExit(1)

raw_headers, body = response.split(b"\r\n\r\n", 1)
print("\n--- Response Headers ---\n")
print(raw_headers.decode(errors="ignore"))

# Save artifacts based on path
if http_method == "GET":
    if request_path in ("/", "/index.html"):
        out = "downloaded_page.html"
        with open(out, "wb") as f:
            f.write(body)
        print(f"Saved {out}")
        try:
            webbrowser.open("file://" + os.path.abspath(out))
        except Exception:
            pass

    elif request_path == "/document.pdf":
        out = "received.pdf"
        with open(out, "wb") as f:
            f.write(body)
        print(f"Saved {out}")

    elif request_path == "/wow.jpg":
        out = "wow.jpg"
        with open(out, "wb") as f:
            f.write(body)
        print(f"Saved {out}")

elif http_method == "POST" and request_path == "/attendance":
    print("\n--- Server Message ---\n")
    try:
        print(body.decode())
    except Exception:
        print("(binary data)")
