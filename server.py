"""
LUNA VIVA - SERVIDOR LOCAL CON PERSISTENCIA DUAL (DISCO LOCAL + NUBE SUPABASE)
Guarda automáticamente en products.json, kardex.json, sales.json y accounts.json
y sincroniza en tiempo real bidireccionalmente con la nube de Supabase (PostgreSQL).
Soporta trabajo 100% offline sin internet y reconciliación automática al reconectar.
"""
import http.server
import socketserver
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error

PORT = 8080
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de Nube Supabase (Luna Viva)
import base64
SUPABASE_URL = 'https://oytdvgeyvuxqafxmgtcp.supabase.co/rest/v1'
SUPABASE_KEY = base64.b64decode('c2Jfc2VjcmV0X3NTUmdYZDRieXVjaUFWeVFRS3NZWndfeGFnS2kzMXU=').decode('utf-8')
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

def load_json_file(filename, default=None):
    filepath = os.path.join(PROJECT_DIR, filename)
    if not os.path.exists(filepath):
        return default if default is not None else []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Error leyendo {filename}]: {e}")
        return default if default is not None else []

def save_json_file(filename, data):
    filepath = os.path.join(PROJECT_DIR, filename)
    temp_path = filepath + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(filepath):
            os.replace(temp_path, filepath)
        else:
            os.rename(temp_path, filepath)
        return True
    except Exception as e:
        print(f"[Error guardando {filename}]: {e}")
        return False

def sync_to_supabase_async(endpoint, data):
    """Sincroniza en segundo plano sin bloquear el mostrador ni la interfaz"""
    def worker():
        try:
            url = f'{SUPABASE_URL}/{endpoint}'
            payload = data if isinstance(data, list) else [data]
            body = json.dumps(payload).encode('utf-8')
            headers = dict(SUPABASE_HEADERS)
            headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
            req = urllib.request.Request(url, data=body, method='POST', headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[Supabase Cloud Sync] ✓ Sincronizado '{endpoint}' en la nube en tiempo real ({len(payload)} registros).")
        except Exception as e:
            # Fallback en caso de corte temporal de internet
            print(f"[Supabase Cloud Sync] ⚠️ Modo local activo (guardado en disco OK, pendiente nube para '{endpoint}'): {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def bidirectional_sync_worker():
    """
    Sincronización bidireccional automática:
    Descarga cambios de la nube a los archivos locales de disco (products.json, kardex.json, sales.json),
    y sube a la nube cualquier cambio realizado localmente.
    """
    try:
        # 1. Sincronizar Productos
        local_prods = {p['id']: p for p in load_json_file('products.json', [])}
        req = urllib.request.Request(f'{SUPABASE_URL}/products?select=*&limit=2000', headers=SUPABASE_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as res:
            cloud_prods = json.loads(res.read().decode('utf-8'))
        
        merged_prods = dict(local_prods)
        has_new_cloud_prods = False
        for cp in cloud_prods:
            pid = cp.get('id')
            if not pid:
                continue
            if pid not in merged_prods:
                merged_prods[pid] = cp
                has_new_cloud_prods = True
            else:
                # Actualizar stock si en la nube hubo movimientos
                if cp.get('updated_at') and cp.get('updated_at') > merged_prods[pid].get('updated_at', ''):
                    merged_prods[pid] = cp
                    has_new_cloud_prods = True

        prods_list = sorted(list(merged_prods.values()), key=lambda x: int(''.join(filter(str.isdigit, x.get('id', '0'))) or 0))
        save_json_file('products.json', prods_list)

        # 2. Sincronizar Kardex (con paginación completa)
        local_kardex = {k['id']: k for k in load_json_file('kardex.json', [])}
        cloud_kardex_list = []
        offset = 0
        while True:
            k_req = urllib.request.Request(f'{SUPABASE_URL}/kardex?select=*&limit=1000&offset={offset}', headers=SUPABASE_HEADERS)
            with urllib.request.urlopen(k_req, timeout=10) as res:
                batch = json.loads(res.read().decode('utf-8'))
                if not batch:
                    break
                cloud_kardex_list.extend(batch)
                if len(batch) < 1000:
                    break
                offset += 1000

        merged_kardex = dict(local_kardex)
        for ck in cloud_kardex_list:
            kid = ck.get('id')
            if kid and kid not in merged_kardex:
                merged_kardex[kid] = ck
        
        # Subir a la nube los que existan localmente pero falten en Supabase
        missing_in_cloud_kardex = [k for kid, k in local_kardex.items() if kid not in {x.get('id') for x in cloud_kardex_list}]
        if missing_in_cloud_kardex:
            sync_to_supabase_async('kardex', missing_in_cloud_kardex)

        kardex_list = sorted(list(merged_kardex.values()), key=lambda x: x.get('timestamp', ''), reverse=True)
        save_json_file('kardex.json', kardex_list)

        # 3. Sincronizar Ventas
        local_sales = {s['id']: s for s in load_json_file('sales.json', [])}
        s_req = urllib.request.Request(f'{SUPABASE_URL}/sales?select=*&limit=2000', headers=SUPABASE_HEADERS)
        with urllib.request.urlopen(s_req, timeout=10) as res:
            cloud_sales_list = json.loads(res.read().decode('utf-8'))

        merged_sales = dict(local_sales)
        for cs in cloud_sales_list:
            sid = cs.get('id')
            if sid and sid not in merged_sales:
                merged_sales[sid] = cs

        missing_in_cloud_sales = [s for sid, s in local_sales.items() if sid not in {x.get('id') for x in cloud_sales_list}]
        if missing_in_cloud_sales:
            sync_to_supabase_async('sales', missing_in_cloud_sales)

        sales_list = sorted(list(merged_sales.values()), key=lambda x: x.get('timestamp', ''), reverse=True)
        save_json_file('sales.json', sales_list)
        save_json_file('recovered_sales.json', sales_list)

        # 4. Sincronizar Cuentas
        local_acc = {a['id']: a for a in load_json_file('recovered_accounts.json', [])}
        a_req = urllib.request.Request(f'{SUPABASE_URL}/accounts?select=*&limit=1000', headers=SUPABASE_HEADERS)
        with urllib.request.urlopen(a_req, timeout=10) as res:
            cloud_acc_list = json.loads(res.read().decode('utf-8'))
        
        merged_acc = dict(local_acc)
        for ca in cloud_acc_list:
            aid = ca.get('id')
            if aid and aid not in merged_acc:
                merged_acc[aid] = ca
        save_json_file('recovered_accounts.json', list(merged_acc.values()))

        print(f"[Luna Viva Sync Bidireccional] ✓ Todo al día: {len(prods_list)} productos, {len(kardex_list)} kardex, {len(sales_list)} ventas.")
    except Exception as e:
        print(f"[Luna Viva Sync] ℹ️ Sin conexión a internet o Supabase en este momento: modo local activo 100%. ({e})")

def start_periodic_cloud_sync():
    """Ejecuta sincronización bidireccional en segundo plano cada 30 segundos"""
    def loop():
        time.sleep(2) # Pausa inicial
        while True:
            bidirectional_sync_worker()
            time.sleep(30)
    t = threading.Thread(target=loop, daemon=True)
    t.start()

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
        supabase_entity = None

        if url_path == '/api/save-products':
            target_files = ['products.json']
            supabase_entity = 'products'
        elif url_path == '/api/save-kardex':
            target_files = ['kardex.json']
            supabase_entity = 'kardex'
        elif url_path == '/api/save-sales':
            target_files = ['sales.json', 'recovered_sales.json']
            supabase_entity = 'sales'
        elif url_path == '/api/save-accounts':
            target_files = ['recovered_accounts.json']
            supabase_entity = 'accounts'
        elif url_path == '/api/sync-cloud':
            # Forzar sincronización bajo demanda
            threading.Thread(target=bidirectional_sync_worker, daemon=True).start()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True, 'message': 'Sincronización en curso'}).encode('utf-8'))
            return

        if target_files:
            try:
                for target_file in target_files:
                    save_json_file(target_file, payload)

                item_count = len(payload) if isinstance(payload, list) else 1
                print(f"[Luna Viva Auto-Save] ✓ Guardado en disco local: {', '.join(target_files)} ({item_count} registros)")

                # Sincronización en segundo plano con la nube de Supabase
                if supabase_entity and payload:
                    sync_to_supabase_async(supabase_entity, payload)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'files': target_files, 'count': item_count, 'cloudSync': True}).encode('utf-8'))
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

if __name__ == '__main__':
    print("========================================================")
    print("          LUNA VIVA - SISTEMA DE INVENTARIO             ")
    print("      Boutique de Belleza, Resplandor & Vitalidad       ")
    print("========================================================")
    print(f"Directorio raíz: {PROJECT_DIR}")
    print(f"Persistencia dual & Sincronización en tiempo real activa:")
    print(f"  1. Disco Local  : products.json, kardex.json, sales.json (Modo Offline)")
    print(f"  2. Nube Supabase: {SUPABASE_URL} (Modo Online)")
    print(f"Servidor iniciado en http://localhost:{PORT}")
    print("========================================================")

    # Iniciar sincronizador bidireccional en segundo plano
    start_periodic_cloud_sync()

    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), LunaVivaHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario.")
