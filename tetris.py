# tetris.py - Tetris za ESP32 s touch kontrolama (60 FPS, ispravljeno)
# Sve nijanse zelene, fluidan gameplay, cijeli ekran

import machine
import time
import random
import gc
import sys
from machine import Pin, SPI

# ========== HARDWARE ==========
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

# Touch
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

def get_touch():
    """Vraća (x, y) ili (None, None) ako nema dodira."""
    if touch_irq.value() != 0:
        return None, None
    x_raw = citaj_raw(0xD0)
    y_raw = citaj_raw(0x90)
    if not (TOUCH_X_MIN <= x_raw <= TOUCH_X_MAX and TOUCH_Y_MIN <= y_raw <= TOUCH_Y_MAX):
        return None, None
    x = int((x_raw - TOUCH_X_MIN) * DISPLAY_WIDTH / (TOUCH_X_MAX - TOUCH_X_MIN))
    y = int((y_raw - TOUCH_Y_MIN) * DISPLAY_HEIGHT / (TOUCH_Y_MAX - TOUCH_Y_MIN))
    if DISPLAY_ROTATION == 180:
        x = DISPLAY_WIDTH - x
        y = DISPLAY_HEIGHT - y
    return x, y

def citaj_raw(komanda):
    touch_cs.value(0)
    time.sleep_us(10)
    touch_spi.write(bytearray([komanda]))
    data = touch_spi.read(2)
    touch_cs.value(1)
    if data and len(data) == 2:
        return ((data[0] << 8) | data[1]) >> 3
    return 0

# ========== TETRIS KONSTANTE ==========
GRID_W = 10
GRID_H = 20
BLOCK_SIZE = 12
PLAY_X = (DISPLAY_WIDTH - GRID_W * BLOCK_SIZE) // 2   # = 100
PLAY_Y = 0
SCORE_X = PLAY_X + GRID_W * BLOCK_SIZE + 10
SCORE_Y = 20

# Nijanse zelene
COLORS = [0x0460, 0x07E0, 0x07F0, 0x07FF]   # tamna, srednja, svijetla, bjelkasta

SHAPES = [
    [[1,1,1,1]],                                # I
    [[1,1],[1,1]],                              # O
    [[0,1,0],[1,1,1]],                          # T
    [[1,0,0],[1,1,1]],                          # L
    [[0,0,1],[1,1,1]],                          # J
    [[0,1,1],[1,1,0]],                          # S
    [[1,1,0],[0,1,1]]                           # Z
]

# ========== GAME STATE ==========
grid = [[0]*GRID_W for _ in range(GRID_H)]
score = 0
game_over = False
current_piece = None
current_x = 0
current_y = 0
fall_time = 0
FALL_INTERVAL = 400   # ms

# Touch geste
last_touch_x = None
last_touch_y = None
last_touch_time = 0
MOVE_THRESHOLD = 30   # piksela
TAP_THRESHOLD = 15

# ========== FUNKCIJE ==========
def random_piece():
    shape = random.choice(SHAPES)
    color = random.choice(COLORS)
    return {'shape': shape, 'color': color}

def spawn_new_piece():
    global current_piece, current_x, current_y, game_over
    current_piece = random_piece()
    shape = current_piece['shape']
    current_x = GRID_W // 2 - len(shape[0]) // 2
    current_y = 0
    if collision(current_x, current_y, shape):
        game_over = True
        return False
    draw_piece()
    return True

def collision(x, y, shape):
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                gx = x + j
                gy = y + i
                if gx < 0 or gx >= GRID_W or gy >= GRID_H or (gy >= 0 and grid[gy][gx]):
                    return True
    return False

def merge_piece():
    global score
    shape = current_piece['shape']
    color = current_piece['color']
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                grid[current_y + i][current_x + j] = color
    # Brisanje redova
    lines = 0
    y = GRID_H - 1
    while y >= 0:
        if all(grid[y]):
            del grid[y]
            grid.insert(0, [0]*GRID_W)
            lines += 1
        else:
            y -= 1
    if lines:
        score += [0, 100, 300, 500, 800][lines]
        full_refresh_grid()   # iscrtaj cijelu mrežu (promijenila se)

def move_left():
    global current_x
    if not collision(current_x-1, current_y, current_piece['shape']):
        erase_piece()
        current_x -= 1
        draw_piece()
        return True
    return False

def move_right():
    global current_x
    if not collision(current_x+1, current_y, current_piece['shape']):
        erase_piece()
        current_x += 1
        draw_piece()
        return True
    return False

def rotate_piece():
    shape = current_piece['shape']
    rotated = [list(row) for row in zip(*shape[::-1])]
    if not collision(current_x, current_y, rotated):
        erase_piece()
        current_piece['shape'] = rotated
        draw_piece()
        return True
    return False

def hard_drop():
    global current_y
    while not collision(current_x, current_y+1, current_piece['shape']):
        current_y += 1
    merge_piece()
    spawn_new_piece()
    draw_score()

def soft_drop():
    global current_y
    if not collision(current_x, current_y+1, current_piece['shape']):
        erase_piece()
        current_y += 1
        draw_piece()
        return False
    else:
        merge_piece()
        spawn_new_piece()
        draw_score()
        return True   # znači da je došlo do spajanja

# ========== CRTANJE ==========
def draw_block(x, y, color):
    draw_filled_rect(PLAY_X + x*BLOCK_SIZE, PLAY_Y + y*BLOCK_SIZE,
                     BLOCK_SIZE-1, BLOCK_SIZE-1, color)

def draw_piece():
    shape = current_piece['shape']
    color = current_piece['color']
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                draw_block(current_x + j, current_y + i, color)

def erase_piece():
    shape = current_piece['shape']
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                draw_block(current_x + j, current_y + i, BG_COLOR)

def full_refresh_grid():
    # Iscrtaj cijelu mrežu (sporo, ali samo kad treba)
    for y in range(GRID_H):
        for x in range(GRID_W):
            color = grid[y][x]
            if color:
                draw_block(x, y, color)
            else:
                draw_block(x, y, BG_COLOR)
    # Okvir
    display.draw_rectangle(PLAY_X-1, PLAY_Y-1,
                           GRID_W*BLOCK_SIZE+2, GRID_H*BLOCK_SIZE+2, WHITE)

def draw_score():
    draw_filled_rect(SCORE_X, SCORE_Y, 100, 40, BG_COLOR)
    safe_draw(SCORE_X, SCORE_Y, "SCORE", WHITE)
    safe_draw(SCORE_X, SCORE_Y+12, str(score), COLORS[2])

def draw_game_over():
    w, h = 200, 40
    x = (DISPLAY_WIDTH - w)//2
    y = (DISPLAY_HEIGHT - h)//2
    draw_filled_rect(x, y, w, h, RED)
    safe_draw(x+30, y+12, "GAME OVER", WHITE)
    safe_draw(x+40, y+28, "Dodirni", WHITE)

def reset_game():
    global grid, score, game_over
    grid = [[0]*GRID_W for _ in range(GRID_H)]
    score = 0
    game_over = False
    display.clear(BG_COLOR)
    full_refresh_grid()
    spawn_new_piece()
    draw_score()

# ========== TOUCH OBRADA ==========
def handle_touch():
    global last_touch_x, last_touch_y, last_touch_time, game_over
    x, y = get_touch()
    if x is None:
        last_touch_x = None
        return

    if game_over:
        reset_game()
        return

    now = time.ticks_ms()
    if last_touch_x is not None:
        dx = x - last_touch_x
        dy = y - last_touch_y
        dt = time.ticks_diff(now, last_touch_time)
        # Ako je brzi pokret (unutar 200ms)
        if dt < 200:
            # Horizontalni swipe -> lijevo/desno
            if abs(dx) > MOVE_THRESHOLD and abs(dy) < MOVE_THRESHOLD:
                if dx < 0:
                    move_left()
                else:
                    move_right()
                last_touch_x = None  # spriječi ponovnu obradu
                return
            # Vertikalni swipe dolje -> hard drop
            if dy > MOVE_THRESHOLD and abs(dx) < MOVE_THRESHOLD:
                hard_drop()
                last_touch_x = None
                return
            # Tap (mali pomak)
            if abs(dx) < TAP_THRESHOLD and abs(dy) < TAP_THRESHOLD:
                rotate_piece()
                last_touch_x = None
                return
    # Ako nije prepoznat swipe/tap, postavi trenutnu točku za sljedeći put
    last_touch_x = x
    last_touch_y = y
    last_touch_time = now

# ========== GLAVNA PETLJA ==========
def main():
    global game_over, fall_time
    reset_game()
    fall_time = time.ticks_ms()
    frame = 0
    gc_interval_frames = 120
    while True:
        now = time.ticks_ms()
        # Automatski pad
        if not game_over and time.ticks_diff(now, fall_time) > FALL_INTERVAL:
            fall_time = now
            if soft_drop():   # ako se dogodilo spajanje, resetiraj timer
                fall_time = time.ticks_ms()

        # Obrada dodira
        handle_touch()

        # Povremeno oslobađanje memorije
        frame += 1
        if frame >= gc_interval_frames:
            gc.collect()
            frame = 0

        time.sleep_ms(16)   # ~60 FPS

if __name__ == "__main__":
    main()
