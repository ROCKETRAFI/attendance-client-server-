import socket
import os
import threading
from datetime import datetime
from urllib.parse import parse_qs

HOST = "0.0.0.0"
PORT = 8080

# ---------- Small HTTP helpers ----------
def http_response(status: str, headers: dict, body: bytes) -> bytes:
    head = f"HTTP/1.1 {status}\r\n"
    for k, v in headers.items():
        head += f"{k}: {v}\r\n"
    head += "\r\n"
    return head.encode() + body

def not_found(msg: str = "Not Found") -> bytes:
    body = f"<h1>404</h1><p>{msg}</p>".encode()
    return http_response("404 Not Found",
                         {"Content-Type": "text/html; charset=utf-8",
                          "Content-Length": str(len(body))},
                         body)

def serve_file(path: str, mime: str) -> bytes:
    if not os.path.exists(path):
        return not_found(f"File {path} not found")
    with open(path, "rb") as f:
        data = f.read()
    return http_response("200 OK",
                         {"Content-Type": mime,
                          "Content-Length": str(len(data))},
                         data)

INDEX_HTML = ("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>CN HTTP Test</title>
  <style>
    body{font-family:system-ui,Segoe UI,Arial;margin:2rem;}
    code{background:#f4f4f4;padding:.2rem .4rem;border-radius:4px}
  </style>
</head>
<body>
  <h1>Welcome to the Computer Networks HTTP Test</h1>
  <p>This page is served by a simple Python socket server.</p>
  <ul>
    <li>GET <code>/document.pdf</code> to download the PDF</li>
    <li>POST <code>/attendance</code> with <code>ID</code> and <code>Name</code> to record attendance</li>
  </ul>
</body>
</html>
""").encode()

# ---------- Request parsing ----------
def recv_all(conn: socket.socket) -> bytes:
    """
    Read until we've received headers and (if present) the entire body
    according to Content-Length. Uses a short timeout to avoid hanging.
    """
    conn.settimeout(1.0)
    chunks = []
    total = b""
    content_len = None
    try:
        while True:
            part = conn.recv(4096)
            if not part:
                break
            chunks.append(part)
            total = b"".join(chunks)

            # Once headers are in, try to satisfy Content-Length
            if b"\r\n\r\n" in total:
                head, body = total.split(b"\r\n\r\n", 1)
                # parse content-length if any
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        try:
                            content_len = int(line.split(b":", 1)[1].strip())
                        except Exception:
                            content_len = None
                        break
                if content_len is None:
                    # no body or chunked/unknown—return after headers+whatever arrived
                    return total
                else:
                    if len(body) >= content_len:
                        return head + b"\r\n\r\n" + body[:content_len]
    except socket.timeout:
        pass
    return total

def parse_request(raw: bytes):
    try:
        head, body = raw.split(b"\r\n\r\n", 1)
    except ValueError:
        return None, None, None, {}, b""

    lines = head.decode(errors="ignore").split("\r\n")
    if not lines or " " not in lines[0]:
        return None, None, None, {}, b""

    method, path, version = lines[0].split(" ", 2)
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return method, path, version, headers, body

# ---------- Handlers ----------
def handle_attendance(body_bytes: bytes, addr) -> bytes:
    """
    Accepts application/x-www-form-urlencoded payloads containing ID and Name.
    Saves to data/attendance.csv with timestamp and client IP:port.
    """
    form = parse_qs(body_bytes.decode(errors="ignore"))
    student_id = (form.get("ID") or form.get("id") or [""])[0]
    name = (form.get("Name") or form.get("name") or [""])[0]
    timestamp = datetime.now().isoformat(timespec="seconds")

    os.makedirs("data", exist_ok=True)
    line = f"{timestamp},{addr[0]}:{addr[1]},{student_id},{name}\n"
    with open(os.path.join("data", "attendance.csv"), "a", encoding="utf-8") as f:
        f.write(line)

    print(f"✅ Attendance recorded: {line.strip()}")
    msg = b"Attendance recorded successfully!"
    return http_response("200 OK",
                         {"Content-Type": "text/plain; charset=utf-8",
                          "Content-Length": str(len(msg))},
                         msg)

def app(conn: socket.socket, addr):
    raw = recv_all(conn)
    if not raw:
        conn.sendall(not_found("Empty request"))
        conn.close()
        return

    method, path, version, headers, body = parse_request(raw)

    # Log first line for clarity
    try:
        first = raw.split(b"\r\n", 1)[0].decode(errors="ignore")
    except Exception:
        first = "(unparsable request line)"
    print("\n--- Request from", addr, "---")
    print(first)

    if method == "GET" and path in ("/", "/index.html"):
        resp = http_response("200 OK",
                             {"Content-Type": "text/html; charset=utf-8",
                              "Content-Length": str(len(INDEX_HTML))},
                             INDEX_HTML)

    elif method == "GET" and path == "/document.pdf":
        resp = serve_file("document.pdf", "application/pdf")

    elif method == "GET" and path == "/wow.jpg":
        resp = serve_file("wow.jpg", "image/jpeg")

    elif method == "POST" and path == "/attendance":
        # adhere to content-length if present
        cl = int(headers.get("content-length", "0")) if headers else 0
        body = body[:cl] if cl else body
        resp = handle_attendance(body, addr)

    else:
        resp = not_found(f"Path {path} not handled")

    conn.sendall(resp)
    conn.close()

def worker(conn, addr):
    try:
        app(conn, addr)
    except Exception as e:
        print("Handler error:", e)
        try:
            conn.sendall(not_found("Server error"))
        except Exception:
            pass
        conn.close()

def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Server listening on http://{HOST}:{PORT} …")
        while True:
            conn, addr = s.accept()
            print("Accepted:", addr)
            threading.Thread(target=worker, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    serve()
