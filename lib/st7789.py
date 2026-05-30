"""
ST7789V display driver for MicroPython
Optimized for Honey Pot project
"""
import time
from micropython import const


class ST7789:
    # ST7789V Commands
    SWRESET = const(0x01)
    SLPOUT = const(0x11)
    NORON = const(0x13)
    INVON = const(0x21)
    DISPOFF = const(0x28)
    DISPON = const(0x29)
    CASET = const(0x2A)
    RASET = const(0x2B)
    RAMWR = const(0x2C)
    MADCTL = const(0x36)
    COLMOD = const(0x3A)

    def __init__(self, spi, cs, dc, rst, width=240, height=320):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.width = width
        self.height = height
        
        # Initialize pins
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=1)
        
        self.reset()
        self.init_display()

    def reset(self):
        """Hard reset the display"""
        self.rst(0)
        time.sleep_ms(10)
        self.rst(1)
        time.sleep_ms(10)

    def write_cmd(self, cmd):
        """Write command to display"""
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, data):
        """Write data to display"""
        self.dc(1)
        self.cs(0)
        if isinstance(data, int):
            self.spi.write(bytearray([data]))
        else:
            self.spi.write(data)
        self.cs(1)

    def init_display(self):
        """Initialize ST7789V display"""
        self.write_cmd(self.SWRESET)
        time.sleep_ms(150)
        
        self.write_cmd(self.SLPOUT)
        time.sleep_ms(10)
        
        self.write_cmd(self.COLMOD)
        self.write_data(0x55)  # 16-bit color
        
        self.write_cmd(self.MADCTL)
        self.write_data(0x00)  # Default orientation
        
        self.write_cmd(self.INVON)  # Invert colors
        
        self.write_cmd(self.NORON)
        time.sleep_ms(10)
        
        self.write_cmd(self.DISPON)
        time.sleep_ms(10)

    def set_window(self, x0, y0, x1, y1):
        """Set drawing window"""
        self.write_cmd(self.CASET)
        self.write_data(x0 >> 8)
        self.write_data(x0 & 0xFF)
        self.write_data(x1 >> 8)
        self.write_data(x1 & 0xFF)
        
        self.write_cmd(self.RASET)
        self.write_data(y0 >> 8)
        self.write_data(y0 & 0xFF)
        self.write_data(y1 >> 8)
        self.write_data(y1 & 0xFF)
        
        self.write_cmd(self.RAMWR)

    def fill(self, color):
        """Fill entire screen with color"""
        self.set_window(0, 0, self.width - 1, self.height - 1)
        
        # Convert color to bytes
        color_bytes = bytearray([color >> 8, color & 0xFF])
        
        # Fill screen
        chunk_size = 1024
        total_pixels = self.width * self.height
        
        for i in range(0, total_pixels, chunk_size):
            remaining = min(chunk_size, total_pixels - i)
            data = color_bytes * remaining
            self.write_data(data)

    def text(self, text, x, y, color):
        """Simple text drawing (placeholder - draws rectangles for now)"""
        # For now, just draw a small rectangle to mark text position
        self.fill_rect(x, y, len(text) * 8, 8, color)

    def fill_rect(self, x, y, width, height, color):
        """Fill rectangle with color"""
        if x + width > self.width or y + height > self.height:
            return
        
        self.set_window(x, y, x + width - 1, y + height - 1)
        
        color_bytes = bytearray([color >> 8, color & 0xFF])
        pixels = width * height
        
        chunk_size = 1024
        for i in range(0, pixels, chunk_size):
            remaining = min(chunk_size, pixels - i)
            data = color_bytes * remaining
            self.write_data(data)