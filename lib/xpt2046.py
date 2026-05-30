import time

class Touch:
    """Klasa za upravljanje XPT2046 touchscreen-om"""
    def __init__(self, cs, int_pin, spi, width=320, height=240, x_min=0, x_max=4095, y_min=0, y_max=4095):
        self.cs = cs
        self.int_pin = int_pin
        self.int_pin.init(int_pin.IN)
        self.spi = spi
        self.width = width
        self.height = height
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

    def get_touch(self):
        """
        Vraća kalibrirane koordinate dodira na XPT2046 touchscreen-u
        ako postoji dodir.
        
        Returns:
        - (x, y): Kalibrirane koordinate
        - (None, None): Ako nema dodir
        """
        # Provjera je li ekran dodirnut
        if self.int_pin.value() != 0:
            return None, None

        # Čitanje sirovih X i Y koordinata
        x_raw = self._read_value(0xD0)  # X koordinata (komanda)
        y_raw = self._read_value(0x90)  # Y koordinata (komanda)

        # Kalibracija i transformacija
        x = self._calibrate(x_raw, self.x_min, self.x_max, self.width)
        y = self._calibrate(y_raw, self.y_min, self.y_max, self.height)

        # Ograniči na dimenzije ekrana
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))

        return x, y

    def _calibrate(self, raw, min_val, max_val, size):
        """
        Kalibracija sirovih dodirnih podataka prema dimenzijama ekrana.
        
        Params:
        - raw: Sirovi dodirni podaci od XPT2046
        - min_val: Minimalna dodirna vrijednost
        - max_val: Maksimalna dodirna vrijednost
        - size: Veličina ekrana (širina ili visina)
        
        Returns:
        - Kalibrirani podatak
        """
        return int((raw - min_val) * size / (max_val - min_val))

    def _read_value(self, command):
        """
        Čitanje sirovih dodirnih podataka iz XPT2046 koristeći SPI komunikaciju.
        
        Params:
        - command: SPI komanda za čitanje X ili Y koordinata
        
        Returns:
        - Sirova vrijednost
        """
        self.cs.value(0)
        time.sleep_us(10)
        self.spi.write(bytearray([command]))
        data = self.spi.read(2)
        self.cs.value(1)

        if data and len(data) == 2:
            return (data[0] << 8 | data[1]) >> 3
        return 0