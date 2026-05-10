#!/usr/bin/env python3
"""
VAPT Assessment Platform — Sync Server
Run: python3 server.py
Access via Tailscale at http://<pi-tailscale-ip>:7331
"""
import http.server, json, os, socket, threading, uuid
from datetime import datetime, timezone

DATA_DIR  = os.path.join(os.path.dirname(__file__), 'data')
HTML_FILE = os.path.join(os.path.dirname(__file__), 'index.html')
PORT      = 7331
_lock     = threading.Lock()

os.makedirs(DATA_DIR, exist_ok=True)

ORGS_FILE = os.path.join(DATA_DIR, 'orgs.json')


def read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return default


def write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f)


def state_path(org_id):
    return os.path.join(DATA_DIR, f'state_{org_id}.json')


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        p = self.path.split('?')[0]

        if p in ('/', '/index.html'):
            with open(HTML_FILE, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

        elif p == '/orgs':
            with _lock:
                orgs = read_json(ORGS_FILE, [])
            # Attach progress summary to each org
            result = []
            for org in orgs:
                st = read_json(state_path(org['id']), {})
                checked = st.get('checked', {})
                result.append({**org, 'checkedCount': sum(1 for v in checked.values() if v)})
            self.send_json(200, result)

        elif p.startswith('/state/'):
            org_id = p.split('/state/')[1].strip('/')
            with _lock:
                data = read_json(state_path(org_id), {})
            self.send_json(200, data)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        p = self.path.split('?')[0]

        if p == '/orgs':
            try:
                body = json.loads(self.read_body())
                name   = str(body.get('name', '')).strip()
                client = str(body.get('client', '')).strip()
                if not name:
                    self.send_json(400, {'error': 'name required'})
                    return
                org = {
                    'id':        uuid.uuid4().hex[:12],
                    'name':      name,
                    'client':    client,
                    'createdAt': datetime.now(timezone.utc).isoformat(),
                }
                with _lock:
                    orgs = read_json(ORGS_FILE, [])
                    orgs.append(org)
                    write_json(ORGS_FILE, orgs)
                    write_json(state_path(org['id']), {})
                self.send_json(201, org)
            except Exception as e:
                self.send_json(400, {'error': str(e)})

        elif p.startswith('/state/'):
            org_id = p.split('/state/')[1].strip('/')
            try:
                data = json.loads(self.read_body())
                with _lock:
                    write_json(state_path(org_id), data)
                self.send_json(200, {'ok': True})
            except Exception as e:
                self.send_json(400, {'error': str(e)})

        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        p = self.path.split('?')[0]
        if p.startswith('/orgs/'):
            org_id = p.split('/orgs/')[1].strip('/')
            with _lock:
                orgs = read_json(ORGS_FILE, [])
                orgs = [o for o in orgs if o['id'] != org_id]
                write_json(ORGS_FILE, orgs)
                sp = state_path(org_id)
                if os.path.exists(sp):
                    os.remove(sp)
            self.send_json(200, {'ok': True})
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    ip = get_local_ip()
    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'\n  VAPT Assessment Platform\n')
    print(f'  Localhost  : http://localhost:{PORT}')
    print(f'  Network    : http://{ip}:{PORT}')
    print(f'  Tailscale  : http://<pi-tailscale-ip>:{PORT}')
    print(f'  Data dir   : {DATA_DIR}')
    print(f'\n  Ctrl+C to stop\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('  Stopped.')
