import machine
import time
import sys
import gc
import os

# ==========================================
# STIL - Boje
# ==========================================
BG_COLOR = 0x0000; WHITE = 0xFFFF; GREEN = 0x07E0; YELLOW = 0xFFE0; PURPLE = 0x780F
PRIMARY_COLOR, ACCENT_COLOR, SELECTED_COLOR = WHITE, GREEN, YELLOW
DANGER_COLOR, SUCCESS_COLOR, GRAY_COLOR = PURPLE, GREEN, PURPLE

# ==========================================
# PINOVI I KONFIGURACIJA
# ==========================================
TFT_SCLK, TFT_MOSI, TFT_MISO = 14, 13, 12
TFT_DC, TFT_CS, TFT_RST, TFT_BL = 2, 15, 4, 27
TOUCH_CS, TOUCH_IRQ = 33, 36
TOUCH_X_MIN, TOUCH_X_MAX, TOUCH_Y_MIN, TOUCH_Y_MAX = 281, 3848, 347, 3878
DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROTATION = 320, 240, 180

# ==========================================
# SETUP
# ==========================================
sys.path.append('/lib')
try: from ili9341 import Display
except ImportError: print("GREŠKA: Nema ili9341!"); sys.exit()

machine.Pin(TFT_BL, machine.Pin.OUT).value(1)
display_spi = machine.SPI(1, baudrate=80000000, sck=machine.Pin(TFT_SCLK), mosi=machine.Pin(TFT_MOSI), miso=machine.Pin(TFT_MISO))
display = Display(display_spi, cs=machine.Pin(TFT_CS), dc=machine.Pin(TFT_DC), rst=machine.Pin(TFT_RST), width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, rotation=DISPLAY_ROTATION)
display.clear(BG_COLOR)

touch_spi = machine.SPI(1, baudrate=2000000, sck=machine.Pin(14), mosi=machine.Pin(13), miso=machine.Pin(12))
touch_cs = machine.Pin(TOUCH_CS, machine.Pin.OUT, value=1)
touch_irq = machine.Pin(TOUCH_IRQ, machine.Pin.IN)

# ==========================================
# GLOBALNE VARIJABLE
# ==========================================
scripts, selected_script, last_selected_script = [], 0, -1
last_touch_time, is_dragging = 0, False

# ==========================================
# ASCII ART (novi, iz ascii-art.txt)
# ==========================================
ASCII_ART = """
.............::::::::::..:.....:::.......:::.....                                    ......:.:....  
...................:..:.............  ...........                                   .............  .
. .  .................:........... .  .........   .......                                 ...     ..
......... ......................            ..   .   ....                                      .....
...........     ..............               . ........ ..                                   .  ....
:..........                                    .. .  ......                                  ... .  
::::.......                                       .  ...                                            
::::......          ........                .--======:                                              
::::::..         ..   ...........         :==++++***#***                                           .
::-::.:......::...... ............       -=++**#########*                                   .. . ...
--::::..::..::...:..................  .  ***############*                                           
::::::::::-:::::::::::..  ...............*-+#########=-.+                                           
.:..::::::-::::::::::::................ .** -==-: =:--=::                                           
...  ..::::::......:.........::::....*=-::.. ..:. ::. :+*###*.                                      
      ...:::...  .............::..... ...-: .-=- -= -----                                           
       ....... ....  ...................=.  -:.:.::: .----                                          
           ..  ....:.................... .      .  .-:-:-:                                          
....           ....:.:.:....       .  .  :  .   ....:-::-                                           
......   . .....::.:.:.....                 ........:-::-                                 .         
....   ....:.....:...:....                .  :::::::=::-                                            
....    ...::...........                   .   .::.:::--                                            
...    ..........:.........  .             -..     :::- -                                           
.........       ..........                +:   --===-- .+-                                          
........    ..                          ====           =+++-                                        
            ..  .                    -+====+     -     ++++=+=.                                     
          .  ....               -++==++====+-   ---    ++++=+=====:                                 
.  ..  ...........         -==++=====++=====+    -    -++==-++==---====                             
         .. ..     ..    .+*+========++-====+   ---   +++==--+==-----====                           
                         ++*===++====++======-  -:-  -+++=--+==----==+====                          
                        +++*+==+++====+*=====+  --=- +++==-+==-----=+====+-                         
                        +++**===++=====+*==+=+:.----=+++=-+==-----=======++                         
                        =+++**===+==-===++=++++-----+++=-+==-----==+=====++                         
                        =+++**-==++==-====+=++++---=++=-+=-------=====-=+++=                        
                        ==+++*+===+=---====+=++++--++=-+==------==+-++-=++++                        
                        ==+++**===++=---=-==*=++*==+=-+=--------==+-++-=====                        
                        ==+++**+-====---=====+=++:+=++==-------===+=++-====+                        
                        ==+++***=====-----====+=*-=++==------=-===+=++-====+-                       
                       ===+*+***=-===------====++-++==---:-----===+=+=-====+=                       
                       +==+**+**--====-------====++==---::------==+++===-==++                       
                       +==+++++*--====-------====++==---:-------==+++==--==++                       
                       ====+++++--====--------==-++=----:-------==+++==---==+                       
                       ====++**+--====---------=-===----:-------===+=-----==+.                      
                       =-==+++++---===---------=-+=---:::--------====-----==+=                      
                       =--==++++:---=----------====----::--------====----=====                      
                       =--==++++::--==----------===----------------==-:----===                      
                       =--==++++::-==-----------==------------------=-------=-                      
                       =--==++++::--=-----------==++---------------==--:::----                      
                       =-===++++::-------::-----==-------:----------==--::--=:
"""

# ==========================================
# TOUCH I CRTANJE FUNKCIJE
# ==========================================
def get_touch():
    if touch_irq.value() != 0: return None, None
    x_raw, y_raw = citaj_touch_raw(0xD0), citaj_touch_raw(0x90)
    if not (TOUCH_X_MIN <= x_raw <= TOUCH_X_MAX and TOUCH_Y_MIN <= y_raw <= TOUCH_Y_MAX): return None, None
    x = int((x_raw - TOUCH_X_MIN) * DISPLAY_WIDTH / (TOUCH_X_MAX - TOUCH_X_MIN))
    y = int((y_raw - TOUCH_Y_MIN) * DISPLAY_HEIGHT / (TOUCH_Y_MAX - TOUCH_Y_MIN))
    return (DISPLAY_WIDTH - x, DISPLAY_HEIGHT - y) if DISPLAY_ROTATION == 180 else (x, y)

def citaj_touch_raw(komanda):
    touch_cs.value(0); time.sleep_us(10); touch_spi.write(bytearray([komanda])); data = touch_spi.read(2); touch_cs.value(1)
    return ((data[0] << 8) | data[1]) >> 3 if data else 0

def safe_draw(x, y, text, color, bg=BG_COLOR):
    try: display.draw_text8x8(x, y, str(text)[:(DISPLAY_WIDTH-x)//8], color, bg)
    except: pass

def draw_filled_rect(x, y, w, h, color):
    display.fill_rectangle(x, y, w, h, color)

def draw_filled_circle(x, y, r, color):
    for i in range(x - r, x + r + 1):
        for j in range(y - r, y + r + 1):
            if (i - x)**2 + (j - y)**2 <= r**2: display.draw_pixel(i, j, color)

def draw_button(x, y, w, h, text, color, filled=False):
    if filled: draw_filled_rect(x, y, w, h, color); text_color = BG_COLOR
    else: display.draw_rectangle(x, y, w, h, color); text_color = color
    safe_draw(x+(w-len(text)*8)//2, y+(h-8)//2, text, text_color, BG_COLOR if not filled else color)

# ==========================================
# NOVI BOOT EKRAN SA ASCII ART I LOADING BAR-OM
# =========================================
def get_char_density(char):
    """Vraća svjetlinu 0..5 na osnovu gustine znaka."""
    if char == ' ': return 0
    if char in '.,:;\'"!`': return 1
    if char in '-=~_*': return 2
    if char in '\\/|()[]{}<>': return 3
    if char in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789': return 4
    if char in '#%&@$': return 5
    return 3

def draw_loading_bar(x, y, width, height, percent):
    """Iscrtava loading bar na zadanim koordinatama (percent 0..100)."""
    # Okvir
    display.draw_rectangle(x, y, width, height, WHITE)
    # Ispuna
    fill_width = int(width * percent / 100)
    if fill_width > 0:
        draw_filled_rect(x, y, fill_width, height, GREEN)

def draw_ascii_art_progressive(block_size=3, row_delay_ms=10):
    """
    Crta ASCII art red po red od vrha prema dnu, uz istovremeno punjenje loading bara.
    - block_size = 3 (veća slika nego prije)
    - row_delay_ms = 10 ms po redu (brzo, ali i dalje vidljiva animacija)
    """
    lines = ASCII_ART.strip().split('\n')
    # Ukloni potpuno prazne linije na početku i kraju
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return

    art_width_chars = max(len(line) for line in lines)
    art_height_chars = len(lines)

    total_w = art_width_chars * block_size
    total_h = art_height_chars * block_size

    # Pozicioniranje: slika počinje od vrha (y=10) i horizontalno centrirana
    start_x = (DISPLAY_WIDTH - total_w) // 2
    start_y = 10

    # Loading bar će biti smješten ispod slike
    bar_width = 200
    bar_height = 12
    bar_x = (DISPLAY_WIDTH - bar_width) // 2
    bar_y = start_y + total_h + 15

    # Crtaj red po red
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            density = get_char_density(ch)
            if density == 0:
                continue
            # Boja (zelena skala)
            if density == 1:
                color = 0x0841   # tamnozelena
            elif density == 2:
                color = 0x07E0   # srednje zelena
            elif density == 3:
                color = 0x07F0   # svjetlija
            elif density == 4:
                color = 0x07FF   # svijetlo zelena/cijan
            else:  # density >=5
                color = WHITE
            x = start_x + col * block_size
            y = start_y + row * block_size
            if x + block_size <= DISPLAY_WIDTH and y + block_size <= DISPLAY_HEIGHT:
                draw_filled_rect(x, y, block_size, block_size, color)

        # Nakon svakog reda ažuriraj loading bar prema napretku
        percent = int((row + 1) * 100 / art_height_chars)
        draw_loading_bar(bar_x, bar_y, bar_width, bar_height, percent)

        # Pauza za efekat crtanja od vrha prema dnu
        time.sleep_ms(row_delay_ms)

def boot_screen():
    display.clear(BG_COLOR)
    draw_ascii_art_progressive(block_size=3, row_delay_ms=10)
    # Kratka pauza da se vidi krajnji izgled prije prelaska na launcher
    time.sleep(0.5)

# ==========================================
# LOGIKA LAUNCHERA
# ==========================================
def find_scripts():
    global scripts, selected_script; all_files = os.listdir('/')
    scripts = sorted([f for f in all_files if f.endswith('.py') and f not in ['main.py', 'boot.py']])
    selected_script = 0; print("Pronađene skripte:", scripts)

def run_script(script_name):
    print(f"Pokretanje: {script_name}..."); display.clear(BG_COLOR); safe_draw(20, 110, f"Pokretanje: {script_name}", YELLOW)
    time.sleep(0.5); gc.collect()
    try: execfile(script_name)
    except Exception as e:
        display.clear(BG_COLOR); safe_draw(10, 50, "GRESKA U SKRIPTI:", DANGER_COLOR); safe_draw(10, 70, str(e), WHITE)
        safe_draw(10, 120, "Povratak za 5s...", GRAY_COLOR); time.sleep(5)
    display.clear(BG_COLOR)
    global last_selected_script; last_selected_script = -1

# ==========================================
# UI LAUNCHERA
# ==========================================
def draw_header(title="janocic LAUNCHER v6.1"):
    draw_filled_rect(0, 0, 320, 20, DANGER_COLOR); safe_draw(5, 6, title, BG_COLOR, DANGER_COLOR)
    safe_draw(250, 6, f"{len(scripts)} skripti", BG_COLOR, DANGER_COLOR)

def draw_list_item(index, script_name, is_selected):
    list_y_start, item_height = 40, 28; y = list_y_start + index * item_height
    draw_filled_rect(0, y, 320, item_height, BG_COLOR);
    if not script_name: return
    color = SELECTED_COLOR if is_selected else PRIMARY_COLOR
    safe_draw(10, y + 8, f"{script_name}", color)
    if is_selected:
        draw_filled_circle(305, y + 12, 5, YELLOW)
        draw_button(180, y + 2, 100, 24, "POKRENI", SUCCESS_COLOR, filled=True)

def update_list_display():
    for i in range(7):
        script_name = scripts[i] if i < len(scripts) else None
        draw_list_item(i, script_name, i == selected_script)

def draw_launcher_ui():
    draw_header(); safe_draw(10, 25, "Odaberi program:", GRAY_COLOR)
    draw_button(220, 210, 90, 20, "OSVJEZI", ACCENT_COLOR)

# ==========================================
# TOUCH HANDLER
# ==========================================
def handle_touch():
    global selected_script, last_selected_script, last_touch_time, is_dragging
    x, y = get_touch()
    if x is None:
        if is_dragging: is_dragging = False
        return
    now = time.ticks_ms();
    if time.ticks_diff(now, last_touch_time) < 100 and not is_dragging: return
    last_touch_time = now
    list_y_start, item_height = 40, 28
    if not is_dragging and x > 280 and list_y_start <= y < list_y_start + 7 * item_height: is_dragging = True
    if is_dragging:
        new_sel = max(0, min(len(scripts) - 1, (y - list_y_start) // item_height))
        if selected_script != new_sel: selected_script = new_sel
        return
    if list_y_start <= y < list_y_start + 7 * item_height:
        tapped_index = (y - list_y_start) // item_height
        if selected_script == tapped_index and 180 <= x <= 280:
            if selected_script < len(scripts): run_script(scripts[selected_script])
            return
        if selected_script != tapped_index and tapped_index < len(scripts): selected_script = tapped_index
        return
    if 210 <= y <= 230 and 220 <= x <= 310:
        find_scripts(); last_selected_script = -1

def update_list_item(index):
    if 0 <= index < len(scripts): draw_list_item(index, scripts[index], index == selected_script)

# ==========================================
# GLAVNA PETLJA
# ==========================================
def main():
    global last_selected_script, selected_script
    boot_screen(); find_scripts()
    full_refresh = True
    next_gc_ms = time.ticks_add(time.ticks_ms(), 10000)
    while True:
        try:
            handle_touch()
            if full_refresh or last_selected_script == -1:
                display.clear(BG_COLOR); draw_launcher_ui(); update_list_display()
                last_selected_script = selected_script; full_refresh = False
            elif selected_script != last_selected_script:
                update_list_item(last_selected_script)
                update_list_item(selected_script)
                last_selected_script = selected_script
            time.sleep(0.05)
            now = time.ticks_ms()
            if time.ticks_diff(now, next_gc_ms) >= 0:
                gc.collect()
                next_gc_ms = time.ticks_add(now, 10000)
        except KeyboardInterrupt: break
        except Exception as e: print(f"Glavna greška: {e}")

main()
print("Launcher ugašen.")
