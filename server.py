#!/usr/bin/env python3
"""
LUNA VIVA - SERVIDOR LOCAL CON PERSISTENCIA AUTOMÁTICA EN DISCO
Guarda automáticamente en products.json, kardex.json, sales.json y accounts.json
en cada adición, edición, ajuste de stock o venta.
"""
import http.server
import socketserver
import json
import os
import sys

PORT = 8080
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

class LunaVivaHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_DIR, **kwargs)

    def do_POST(self):
        url_path = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': f'JSON inválido: {str(e)}'}).encode('utf-8'))
            return

        target_files = []
        if url_path == '/api/save-products':
            target_files = ['products.json']
        elif url_path == '/api/save-kardex':
            target_files = ['kardex.json']
        elif url_path == '/api/save-sales':
            target_files = ['sales.json', 'recovered_sales.json']
        elif url_path == '/api/save-accounts':
            target_files = ['recovered_accounts.json']

        if target_files:
            try:
                for target_file in target_files:
                    file_path = os.path.join(PROJECT_DIR, target_file)
                    # Escritura atómica vía archivo temporal
                    temp_path = file_path + '.tmp'
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2)
                    if os.path.exists(file_path):
                        os.replace(temp_path, file_path)
                    else:
                        os.rename(temp_path, file_path)

                item_count = len(payload) if isinstance(payload, list) else 1
                print(f"[Luna Viva Auto-Save] ✓ Guardado en disco: {', '.join(target_files)} ({item_count} registros)")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'files': target_files, 'count': item_count}).encode('utf-8'))
                return
            except Exception as err:
                print(f"[Luna Viva Auto-Save] ✗ Error guardando {target_files}: {err}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(err)}).encode('utf-8'))
                return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

print("========================================================")
print("          LUNA VIVA - SERVIDOR DE INVENTARIO            ")
print("      Boutique de Belleza, Resplandor & Vitalidad       ")
print("========================================================")
print(f"Directorio raíz: {PROJECT_DIR}")
print(f"Auto-guardado activo en disco (products.json, kardex.json)")
print(f"Servidor iniciado en http://localhost:{PORT}")
print("========================================================")

socketserver.TCPServer.allow_reuse_address = True
try:
    with socketserver.TCPServer(("", PORT), LunaVivaHandler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServidor detenido por el usuario.")

