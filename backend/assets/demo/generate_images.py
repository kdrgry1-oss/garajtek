"""Demo içerik görsellerini (ürün çizimleri, hero slaytları, küçük bannerlar) üretir.

İnternetten stok fotoğraf kullanılmaz: tüm görseller burada Pillow ile vektör tarzında çizilir
(beyaz/açık zemin, yumuşak gölge, marka sarısı vurgular) ve WebP olarak img/ altına yazılır.
Çıktılar repoda versiyonlanır; yeniden üretmek için:

    python backend/assets/demo/generate_images.py

Gerekli: Pillow + Open Sans TTF dosyaları (OPEN_SANS_DIR ortam değişkeni; yoksa sistemdeki
DejaVu Sans kullanılır — yalnız banner yazıları etkilenir).
"""
from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "img")
SS = 2  # süper örnekleme (kenar yumuşatma)

# Electro / GarajTek paleti
INK = "#333e48"
INK2 = "#1f262c"
STEEL = "#5b6670"
STEEL2 = "#8c99a3"
STEEL3 = "#cfd8dc"
STEEL4 = "#e9eef1"
YEL = "#fed700"
YEL2 = "#e5c100"
RED = "#df3737"
RED2 = "#b92c2c"
BLUE = "#1f6fd1"
BLUE2 = "#16529c"
WHITE = "#ffffff"
TIRE = "#22292f"


def _font(weight: str, size: int):
    d = os.environ.get("OPEN_SANS_DIR", "")
    names = {
        "light": "OpenSans_300Light.ttf", "regular": "OpenSans_400Regular.ttf",
        "semibold": "OpenSans_600SemiBold.ttf", "bold": "OpenSans_700Bold.ttf", "xbold": "OpenSans_800ExtraBold.ttf",
    }
    for root, _dirs, files in os.walk(d) if d else []:
        if names[weight] in files:
            return ImageFont.truetype(os.path.join(root, names[weight]), size)
    fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight in ("bold", "xbold", "semibold") \
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(fallback, size)


def shade(hex_color: str, f: float) -> str:
    """f<1 koyulaştır, f>1 açıklaştır."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if f <= 1:
        r, g, b = (int(c * f) for c in (r, g, b))
    else:
        k = f - 1
        r, g, b = (int(c + (255 - c) * k) for c in (r, g, b))
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


class Pen:
    """1000x1000 tasarım alanında çizim (SS ile ölçeklenir)."""

    def __init__(self, size=1000):
        self.size = size
        self.im = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, *xy):
        return [v * SS for v in xy]

    def rect(self, x0, y0, x1, y1, fill, r=0, outline=None, width=0):
        self.d.rounded_rectangle(self._p(x0, y0, x1, y1), radius=r * SS, fill=fill,
                                 outline=outline, width=int(width * SS))

    def poly(self, pts, fill):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)

    def ell(self, cx, cy, rx, ry, fill, outline=None, width=0):
        self.d.ellipse(self._p(cx - rx, cy - ry, cx + rx, cy + ry), fill=fill, outline=outline, width=int(width * SS))

    def circ(self, cx, cy, r, fill, outline=None, width=0):
        self.ell(cx, cy, r, r, fill, outline, width)

    def line(self, pts, fill, width):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=int(width * SS), joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.circ(x, y, width / 2, fill)

    def arc(self, cx, cy, r, a0, a1, fill, width):
        self.d.arc(self._p(cx - r, cy - r, cx + r, cy + r), a0, a1, fill=fill, width=int(width * SS))

    def text(self, xy, s, font, fill, anchor="la"):
        self.d.text((xy[0] * SS, xy[1] * SS), s, font=font, fill=fill, anchor=anchor)

    # --- birleşik parçalar
    def cyl_h(self, x0, y0, x1, y1, color):
        """Yatay silindir (tank) — gölgeli."""
        h = y1 - y0
        self.rect(x0, y0, x1, y1, color, r=h / 2)
        self.rect(x0 + h * 0.25, y0 + h * 0.12, x1 - h * 0.25, y0 + h * 0.3, shade(color, 1.35), r=h * 0.09)
        self.rect(x0 + h * 0.2, y1 - h * 0.22, x1 - h * 0.2, y1 - h * 0.08, shade(color, 0.8), r=h * 0.07)

    def wheel(self, cx, cy, r, hub=STEEL3):
        self.circ(cx, cy, r, TIRE)
        self.circ(cx, cy, r * 0.62, STEEL)
        self.circ(cx, cy, r * 0.5, hub)
        self.circ(cx, cy, r * 0.18, STEEL)

    def caster(self, cx, cy, r):
        self.rect(cx - r * 0.7, cy - r * 1.9, cx + r * 0.7, cy - r * 0.6, STEEL, r=r * 0.2)
        self.wheel(cx, cy, r)

    def gauge(self, cx, cy, r):
        self.circ(cx, cy, r, INK)
        self.circ(cx, cy, r * 0.82, WHITE)
        for a in range(200, 341, 20):
            t = math.radians(a)
            self.line([(cx + math.cos(t) * r * 0.6, cy + math.sin(t) * r * 0.6),
                       (cx + math.cos(t) * r * 0.72, cy + math.sin(t) * r * 0.72)], INK, max(2, r * 0.05))
        self.line([(cx, cy), (cx + r * 0.45, cy - r * 0.35)], RED, max(3, r * 0.08))
        self.circ(cx, cy, r * 0.1, INK)

    def car(self, x0, y0, w, color=INK, glass=STEEL3):
        """Yandan görünüm sedan (y0: tavan üstü)."""
        h = w * 0.36
        s = w / 100.0
        body = [(x0 + 4 * s, y0 + 22 * s), (x0 + 22 * s, y0 + 21 * s), (x0 + 34 * s, y0 + 2 * s), (x0 + 70 * s, y0 + 1 * s),
                (x0 + 84 * s, y0 + 19 * s), (x0 + 97 * s, y0 + 23 * s), (x0 + 100 * s, y0 + 30 * s), (x0 + 99 * s, y0 + h),
                (x0 + 1 * s, y0 + h), (x0, y0 + 28 * s)]
        self.poly(body, color)
        self.poly([(x0 + 26 * s, y0 + 20 * s), (x0 + 36 * s, y0 + 6 * s), (x0 + 51 * s, y0 + 5.5 * s), (x0 + 51 * s, y0 + 20 * s)], glass)
        self.poly([(x0 + 54 * s, y0 + 20 * s), (x0 + 54 * s, y0 + 5.5 * s), (x0 + 68 * s, y0 + 5 * s), (x0 + 79 * s, y0 + 19.5 * s)], glass)
        self.rect(x0 + 92 * s, y0 + 24 * s, x0 + 99 * s, y0 + 27 * s, YEL, r=1 * s)
        self.rect(x0 + 1 * s, y0 + 25 * s, x0 + 5 * s, y0 + 28 * s, RED, r=1 * s)
        self.wheel(x0 + 22 * s, y0 + h, 10 * s)
        self.wheel(x0 + 80 * s, y0 + h, 10 * s)


# ============================================================ ürün çizimleri
def art_lift2(p: Pen, c=YEL):
    p.rect(150, 120, 230, 900, c, r=10)
    p.rect(770, 120, 850, 900, c, r=10)
    p.rect(168, 140, 212, 880, shade(c, 0.85), r=6)
    p.rect(788, 140, 832, 880, shade(c, 0.85), r=6)
    p.rect(130, 100, 870, 130, INK, r=8)  # üst köprü
    p.rect(120, 890, 260, 920, INK, r=6)
    p.rect(740, 890, 880, 920, INK, r=6)
    p.rect(240, 330, 290, 860, STEEL2, r=8)  # hidrolik
    p.car(260, 430, 480, INK)
    p.rect(225, 610, 420, 632, STEEL, r=6)
    p.rect(580, 610, 775, 632, STEEL, r=6)
    p.rect(395, 595, 430, 612, YEL2, r=3)
    p.rect(570, 595, 605, 612, YEL2, r=3)
    p.rect(210, 420, 240, 520, RED, r=6)  # kumanda


def art_scissor(p: Pen, c=RED):
    p.car(220, 300, 560, INK)
    p.rect(150, 520, 850, 560, c, r=8)
    p.rect(150, 548, 850, 560, shade(c, 0.75))
    for x in (230, 640):
        p.line([(x, 560), (x + 140, 840)], shade(c, 0.85), 34)
        p.line([(x + 140, 560), (x, 840)], c, 34)
        p.circ(x + 70, 700, 16, INK)
    p.rect(120, 840, 880, 880, INK, r=8)
    p.poly([(850, 520), (930, 560), (850, 560)], STEEL2)
    p.poly([(150, 520), (70, 560), (150, 560)], STEEL2)


def art_moto(p: Pen, c=BLUE):
    p.rect(110, 640, 890, 700, c, r=10)
    p.rect(110, 686, 890, 700, shade(c, 0.75))
    p.poly([(890, 640), (980, 760), (890, 760), (890, 700)], STEEL2)
    p.line([(250, 700), (380, 830)], STEEL, 26)
    p.line([(750, 700), (620, 830)], STEEL, 26)
    p.rect(200, 820, 800, 850, INK, r=8)
    p.rect(160, 590, 260, 640, STEEL, r=6)  # teker kilidi
    # motosiklet
    p.wheel(300, 520, 110)
    p.wheel(700, 520, 110)
    p.poly([(300, 520), (440, 380), (600, 390), (700, 520), (590, 520), (520, 450), (420, 450)], INK)
    p.rect(410, 340, 600, 400, RED, r=30)
    p.line([(640, 300), (700, 520)], STEEL2, 20)
    p.line([(610, 300), (680, 290)], INK, 22)


def art_compressor(p: Pen, c=RED):
    p.cyl_h(140, 480, 860, 780, c)
    p.rect(250, 340, 470, 480, INK, r=12)  # motor
    for i in range(6):
        p.rect(262 + i * 34, 352, 282 + i * 34, 468, STEEL, r=4)
    p.rect(520, 300, 720, 480, STEEL2, r=10)  # pompa
    for i in range(5):
        p.rect(530, 312 + i * 30, 710, 330 + i * 30, shade(STEEL2, 0.8), r=4)
    p.rect(740, 380, 800, 480, STEEL, r=6)
    p.gauge(780, 360, 46)
    p.wheel(240, 830, 70)
    p.wheel(760, 830, 70)
    p.rect(120, 600, 160, 660, STEEL, r=6)
    p.line([(150, 520), (90, 440), (90, 330)], INK, 18)


def art_compressor_v(p: Pen, c=BLUE):
    p.rect(320, 220, 680, 860, c, r=170)
    p.rect(360, 300, 420, 780, shade(c, 1.3), r=20)
    p.rect(600, 300, 640, 780, shade(c, 0.8), r=20)
    p.rect(300, 140, 700, 260, INK, r=24)
    p.rect(320, 160, 680, 180, STEEL, r=6)
    p.gauge(560, 360, 50)
    p.gauge(440, 360, 50)
    p.rect(470, 440, 530, 640, WHITE, r=10)
    p.rect(300, 850, 700, 880, INK, r=8)
    p.wheel(360, 880, 40)
    p.wheel(640, 880, 40)


def art_impact(p: Pen, c=YEL):
    p.rect(200, 300, 720, 470, c, r=60)
    p.rect(220, 320, 700, 360, shade(c, 1.25), r=20)
    p.rect(700, 330, 820, 440, INK, r=20)
    p.rect(815, 360, 880, 410, STEEL, r=6)
    p.rect(870, 365, 910, 405, STEEL2, r=4)
    p.poly([(360, 450), (500, 450), (470, 760), (330, 760)], INK)
    p.rect(300, 740, 520, 880, INK2, r=26)
    p.rect(330, 770, 490, 790, c, r=6)
    p.rect(470, 470, 510, 560, RED, r=10)
    p.rect(180, 330, 220, 440, INK, r=12)


def art_tire_changer(p: Pen, c=RED):
    p.rect(200, 560, 760, 900, c, r=18)
    p.rect(220, 580, 740, 620, shade(c, 1.25), r=10)
    p.rect(200, 860, 760, 900, shade(c, 0.7), r=8)
    p.ell(480, 560, 300, 60, STEEL, outline=INK, width=8)
    p.ell(480, 545, 230, 46, STEEL3)
    p.ell(480, 430, 250, 120, TIRE)
    p.ell(480, 420, 150, 66, STEEL2)
    p.ell(480, 416, 50, 22, STEEL)
    p.rect(780, 160, 840, 760, INK, r=10)
    p.rect(560, 160, 840, 210, INK, r=10)
    p.rect(560, 200, 600, 330, STEEL2, r=8)
    p.rect(150, 650, 200, 720, STEEL, r=8)
    p.line([(160, 690), (60, 790)], INK, 20)
    for i, col in enumerate((INK, STEEL, INK)):
        p.rect(300 + i * 120, 900, 360 + i * 120, 930, col, r=6)


def art_balancer(p: Pen, c=BLUE):
    p.rect(230, 480, 700, 880, c, r=14)
    p.rect(250, 500, 680, 540, shade(c, 1.3), r=8)
    p.rect(250, 230, 700, 470, INK, r=16)  # ekran gövdesi
    p.rect(280, 260, 670, 440, INK2, r=8)
    for i, v in enumerate(("35", "10")):
        p.rect(300 + i * 190, 300, 460 + i * 190, 400, "#0c1013", r=6)
        p.text((380 + i * 190, 350), v, _font("bold", 70 * SS), "#ff4b4b", anchor="mm")
    p.rect(700, 600, 800, 640, STEEL, r=6)  # mil
    p.ell(810, 620, 70, 190, TIRE)
    p.ell(810, 620, 40, 120, STEEL3)
    p.rect(640, 400, 900, 450, STEEL2, r=20)  # kapak kolu
    p.rect(700, 360, 900, 420, shade(c, 0.85), r=24)
    p.rect(200, 870, 730, 900, INK, r=6)


def art_floor_jack(p: Pen, c=RED):
    p.poly([(120, 700), (700, 640), (760, 700), (760, 800), (120, 800)], c)
    p.poly([(120, 700), (700, 640), (720, 660), (130, 720)], shade(c, 1.3))
    p.rect(120, 780, 760, 800, shade(c, 0.7))
    p.line([(240, 700), (330, 470)], INK, 46)
    p.rect(270, 430, 400, 470, INK, r=10)  # eyer
    p.rect(470, 610, 640, 690, STEEL2, r=20)
    p.line([(700, 700), (900, 300)], STEEL, 30)
    p.line([(895, 310), (930, 240)], INK, 40)
    p.wheel(190, 820, 50)
    p.wheel(690, 820, 50)
    p.circ(560, 650, 22, INK)


def art_tool_cart(p: Pen, c=RED):
    p.rect(220, 160, 780, 220, INK, r=12)
    p.rect(240, 220, 760, 830, c, r=10)
    p.rect(240, 790, 760, 830, shade(c, 0.7), r=6)
    ys = [240, 330, 410, 490, 570, 650, 720]
    for i, y in enumerate(ys[:-1]):
        y2 = ys[i + 1] - 12
        p.rect(262, y, 738, y2, shade(c, 1.12), r=6)
        p.rect(420, y + (y2 - y) / 2 - 8, 580, y + (y2 - y) / 2 + 8, STEEL3, r=8)
    p.rect(262, 730, 738, 780, shade(c, 1.12), r=6)
    p.line([(780, 260), (840, 260), (840, 480), (780, 480)], STEEL, 18)
    for x in (290, 710):
        p.caster(x, 880, 42)


def art_socket_set(p: Pen, c=RED):
    p.rect(110, 240, 890, 800, INK, r=26)
    p.rect(130, 260, 870, 780, "#262f37", r=18)
    p.rect(110, 210, 890, 260, c, r=20)
    p.rect(420, 180, 580, 230, STEEL, r=12)
    sizes = [26, 28, 30, 32, 34, 36, 38, 40, 42, 44]
    x = 180
    for s in sizes:
        p.rect(x - s, 300 - 6, x + s, 300 + 120, STEEL3, r=8)
        p.rect(x - s * 0.7, 300 + 10, x + s * 0.7, 300 + 30, STEEL, r=4)
        x += s * 2 + 10
    x = 180
    for s in [30, 32, 34, 36, 38, 40, 42]:
        p.rect(x - s, 470, x + s, 640, STEEL3, r=8)
        p.rect(x - s * 0.7, 485, x + s * 0.7, 505, STEEL, r=4)
        x += s * 2 + 14
    p.line([(700, 520), (820, 700)], STEEL2, 30)
    p.circ(700, 510, 46, STEEL3)
    p.circ(700, 510, 20, STEEL)
    p.rect(180, 690, 640, 740, STEEL2, r=20)


def art_wrench_set(p: Pen, c=STEEL2):
    for i in range(7):
        x = 220 + i * 95
        L = 520 + i * 40
        y0 = 500 - L / 2
        p.line([(x, y0 + 50), (x, y0 + L - 50)], c, 34 - i)
        p.circ(x, y0 + 40, 44, c)
        p.circ(x, y0 + 40, 20, (0, 0, 0, 0))
        p.rect(x - 12, y0 - 10, x + 12, y0 + 40, (0, 0, 0, 0))
        p.circ(x, y0 + L - 40, 46, c)
        p.circ(x, y0 + L - 40, 24, WHITE)
        p.line([(x - 6, y0 + 120), (x - 6, y0 + L - 120)], STEEL3, 6)
    p.rect(140, 860, 860, 900, YEL, r=10)


def art_ratchet(p: Pen, c=STEEL3):
    p.line([(200, 800), (640, 360)], c, 64)
    p.line([(230, 790), (600, 420)], WHITE, 10)
    p.line([(160, 840), (330, 670)], INK, 84)
    p.circ(720, 280, 130, c)
    p.circ(720, 280, 80, STEEL2)
    p.circ(720, 280, 36, STEEL)
    p.rect(770, 160, 820, 210, INK, r=10)
    p.circ(300, 370, 60, STEEL3)
    p.circ(300, 370, 28, STEEL)
    p.circ(430, 220, 70, STEEL3)
    p.circ(430, 220, 32, STEEL)


def art_drill(p: Pen, c=YEL):
    p.rect(250, 250, 700, 430, c, r=70)
    p.rect(270, 270, 680, 310, shade(c, 1.25), r=20)
    p.rect(680, 290, 780, 400, INK, r=20)
    p.rect(770, 310, 840, 380, STEEL, r=10)
    p.line([(840, 345), (950, 345)], STEEL2, 14)
    p.poly([(360, 420), (520, 420), (500, 700), (380, 700)], INK)
    p.rect(300, 690, 620, 840, INK2, r=24)
    p.rect(320, 710, 600, 740, c, r=8)
    p.rect(330, 770, 380, 800, "#2ecc71", r=4)
    p.rect(390, 770, 440, 800, "#2ecc71", r=4)
    p.rect(450, 770, 500, 800, "#2ecc71", r=4)
    p.rect(490, 440, 530, 520, RED, r=10)


def art_welder(p: Pen, c=BLUE):
    p.rect(180, 300, 760, 780, c, r=24)
    p.rect(200, 320, 740, 360, shade(c, 1.3), r=12)
    p.rect(230, 400, 520, 560, INK, r=12)
    p.rect(250, 420, 500, 540, "#0c1013", r=6)
    p.text((375, 480), "200A", _font("bold", 64 * SS), "#3cff7a", anchor="mm")
    p.circ(620, 470, 60, INK)
    p.circ(620, 470, 44, STEEL3)
    p.line([(620, 470), (650, 430)], INK, 12)
    p.circ(300, 660, 34, INK)
    p.circ(420, 660, 34, INK)
    p.rect(330, 240, 600, 300, INK, r=20)
    p.rect(180, 780, 760, 810, INK, r=8)
    p.line([(300, 690), (300, 860), (120, 880), (100, 700)], INK, 16)
    p.line([(420, 690), (430, 880), (840, 880), (880, 760)], RED, 16)
    p.rect(860, 680, 900, 780, INK, r=10)


def art_obd(p: Pen, c=YEL):
    p.rect(250, 150, 750, 850, INK, r=50)
    p.rect(250, 150, 750, 850, None, r=50, outline=c, width=24)
    p.rect(300, 220, 700, 560, "#0c1013", r=12)
    p.rect(320, 240, 680, 280, "#1d6fd1", r=4)
    for i, w in enumerate((300, 220, 260, 180)):
        p.rect(330, 310 + i * 55, 330 + w, 335 + i * 55, "#3a8fff" if i % 2 else "#7fdcff", r=4)
    p.rect(560, 420, 670, 540, "#2ecc71", r=8)
    for i in range(3):
        for j in range(2):
            p.rect(320 + i * 125, 620 + j * 90, 430 + i * 125, 690 + j * 90, STEEL, r=14)
    p.rect(470, 850, 530, 930, INK, r=10)
    p.line([(500, 930), (500, 960), (760, 960)], INK, 14)


def art_battery_tester(p: Pen, c=YEL):
    p.rect(340, 200, 660, 720, c, r=50)
    p.rect(370, 240, 630, 420, INK2, r=12)
    p.text((500, 330), "12.6V", _font("bold", 56 * SS), "#3cff7a", anchor="mm")
    for i in range(2):
        for j in range(2):
            p.rect(390 + i * 120, 470 + j * 100, 490 + i * 120, 540 + j * 100, INK, r=14)
    p.line([(420, 720), (400, 840), (260, 860)], RED, 14)
    p.line([(580, 720), (600, 840), (740, 860)], INK, 14)
    p.rect(180, 830, 300, 880, RED, r=14)
    p.rect(700, 830, 820, 880, INK, r=14)


def art_oil_drain(p: Pen, c=RED):
    p.rect(330, 450, 670, 850, c, r=60)
    p.rect(360, 480, 420, 820, shade(c, 1.3), r=20)
    p.ell(500, 460, 170, 40, shade(c, 0.8))
    p.line([(500, 450), (500, 160)], STEEL2, 26)
    p.poly([(330, 130), (670, 130), (560, 210), (440, 210)], c)
    p.ell(500, 130, 170, 30, shade(c, 0.75))
    p.gauge(600, 560, 44)
    p.line([(670, 640), (820, 640), (820, 880)], INK, 14)
    p.rect(300, 850, 700, 880, INK, r=6)
    p.wheel(360, 900, 36)
    p.wheel(640, 900, 36)


def art_bleeder(p: Pen, c=YEL):
    p.rect(330, 300, 670, 820, c, r=150)
    p.rect(370, 380, 420, 740, shade(c, 1.25), r=20)
    p.rect(420, 220, 580, 310, INK, r=16)
    p.gauge(500, 200, 60)
    p.line([(670, 600), (860, 600), (880, 860)], INK, 12)
    p.rect(300, 800, 700, 860, INK, r=10)


def art_trans_jack(p: Pen, c=RED):
    p.rect(440, 300, 560, 800, c, r=14)
    p.rect(455, 320, 485, 780, shade(c, 1.3), r=6)
    p.rect(470, 190, 530, 300, STEEL2, r=8)
    p.rect(330, 150, 670, 200, INK, r=10)
    p.rect(330, 110, 370, 160, STEEL, r=6)
    p.rect(630, 110, 670, 160, STEEL, r=6)
    for a in (210, 270, 330, 30, 90, 150):
        t = math.radians(a)
        x, y = 500 + math.cos(t) * 300, 840 + math.sin(t) * 70
        p.line([(500, 820), (x, y)], INK, 26)
        p.wheel(x, y + 30, 30)
    p.line([(560, 700), (760, 560)], STEEL, 18)


def art_work_light(p: Pen, c=YEL):
    p.rect(300, 150, 700, 520, INK, r=30)
    p.rect(330, 180, 670, 490, "#fff6b0", r=16)
    for i in range(4):
        for j in range(3):
            p.circ(380 + i * 80, 240 + j * 90, 26, "#ffe766")
    p.line([(300, 520), (220, 850)], c, 30)
    p.line([(700, 520), (780, 850)], c, 30)
    p.line([(500, 520), (500, 850)], c, 30)
    p.rect(180, 840, 820, 870, INK, r=10)


def art_workbench(p: Pen, c=BLUE):
    p.rect(120, 380, 880, 430, "#c58b4f", r=8)
    p.rect(120, 420, 880, 440, "#a46f3a")
    p.rect(150, 440, 450, 820, c, r=8)
    for i in range(4):
        p.rect(165, 455 + i * 90, 435, 530 + i * 90, shade(c, 1.12), r=6)
        p.rect(260, 485 + i * 90, 340, 497 + i * 90, STEEL3, r=6)
    p.rect(820, 440, 850, 820, STEEL, r=6)
    p.rect(470, 760, 850, 790, STEEL, r=6)
    p.rect(150, 120, 880, 360, STEEL4, r=8)  # delikli pano
    for i in range(18):
        for j in range(6):
            p.circ(180 + i * 38, 150 + j * 36, 5, STEEL2)
    p.line([(300, 170), (300, 300)], INK, 14)
    p.circ(300, 160, 20, INK)
    p.line([(420, 170), (440, 320)], RED, 16)
    p.line([(560, 160), (560, 300)], STEEL, 18)
    p.rect(640, 200, 780, 330, YEL, r=10)
    p.rect(520, 330, 700, 380, INK, r=8)  # mengene


def art_grinder(p: Pen, c=BLUE):
    p.rect(150, 400, 650, 540, c, r=60)
    p.rect(170, 415, 630, 450, shade(c, 1.3), r=20)
    p.rect(620, 380, 760, 560, INK, r=24)
    p.ell(800, 470, 50, 190, STEEL3)
    p.ell(790, 470, 40, 160, STEEL2)
    p.rect(700, 270, 760, 380, STEEL, r=10)
    p.line([(560, 400), (520, 280), (420, 260)], INK, 30)
    p.rect(100, 430, 160, 510, INK, r=12)


def art_inflator(p: Pen, c=YEL):
    p.gauge(420, 380, 210)
    p.rect(390, 590, 450, 820, INK, r=14)
    p.rect(330, 560, 510, 610, c, r=16)
    p.line([(450, 800), (700, 860), (840, 700)], INK, 16)
    p.rect(820, 640, 880, 700, STEEL, r=8)


def art_engine_crane(p: Pen, c=RED):
    """Katlanır motor indirme vinci (yandan)."""
    p.rect(120, 800, 860, 840, shade(c, 0.8), r=10)          # taban kolu
    p.line([(160, 820), (300, 760)], shade(c, 0.8), 34)       # ayak
    p.rect(300, 330, 360, 820, c, r=10)                       # dikme
    p.line([(330, 340), (850, 210)], c, 58)                   # bom
    p.line([(345, 330), (840, 205)], shade(c, 1.3), 14)
    p.line([(840, 220), (840, 380)], INK, 10)                 # zincir
    p.rect(805, 380, 875, 420, STEEL, r=10)
    p.line([(840, 420), (840, 470), (815, 490)], INK, 12)     # kanca
    p.line([(355, 700), (560, 300)], STEEL, 36)               # hidrolik piston
    p.rect(330, 640, 410, 760, INK, r=12)
    p.line([(370, 650), (230, 520)], STEEL2, 16)              # pompa kolu
    for x in (160, 520, 820):
        p.caster(x, 880, 34)


def art_press(p: Pen, c=BLUE):
    """H tipi atölye presi."""
    p.rect(200, 120, 260, 860, c, r=8)
    p.rect(740, 120, 800, 860, c, r=8)
    p.rect(180, 110, 820, 190, shade(c, 0.85), r=10)          # üst traves
    p.rect(230, 540, 770, 590, shade(c, 1.2), r=8)            # tabla
    p.rect(150, 850, 380, 885, shade(c, 0.7), r=8)
    p.rect(620, 850, 850, 885, shade(c, 0.7), r=8)
    p.rect(450, 190, 550, 330, YEL, r=10)                     # silindir
    p.rect(480, 330, 520, 450, STEEL3, r=6)                   # piston
    p.rect(455, 450, 545, 480, INK, r=6)
    p.gauge(330, 280, 52)
    p.line([(620, 250), (700, 400)], STEEL, 16)               # pompa kolu
    for y in (640, 700, 760):
        p.circ(230, y, 10, INK)
        p.circ(770, y, 10, INK)


def art_torque_wrench(p: Pen, c=STEEL2):
    """Klik tip tork anahtarı (çapraz)."""
    p.line([(170, 830), (700, 300)], c, 70)
    p.line([(185, 800), (680, 305)], shade(c, 1.35), 16)
    p.line([(130, 870), (300, 700)], INK, 96)                 # sap
    p.line([(140, 860), (290, 710)], INK2, 60)
    p.circ(760, 240, 95, STEEL)
    p.circ(760, 240, 62, STEEL3)
    p.rect(730, 210, 790, 270, INK, r=8)
    for i in range(6):                                        # skala
        x, y = 380 + i * 42, 620 - i * 42
        p.line([(x - 18, y - 18), (x + 6, y + 6)], RED if i % 2 else INK, 6)
    p.rect(330, 560, 390, 620, YEL, r=8)


def art_booster(p: Pen, c=RED):
    """Akü takviye / şarj cihazı (tekerlekli)."""
    p.rect(250, 230, 750, 760, c, r=30)
    p.rect(275, 255, 725, 300, shade(c, 1.25), r=14)
    p.rect(320, 330, 680, 470, INK, r=14)                     # ekran paneli
    p.rect(345, 355, 520, 445, "#2ecc71", r=8)
    p.gauge(600, 400, 55)
    for i, x in enumerate((340, 430, 520, 610)):
        p.circ(x, 540, 24, YEL if i == 0 else STEEL3)
    p.line([(400, 760), (330, 880)], INK, 18)                 # kablolar
    p.line([(600, 760), (680, 880)], INK, 18)
    p.rect(300, 870, 360, 920, RED2, r=8)
    p.rect(650, 870, 710, 920, INK2, r=8)
    p.line([(300, 230), (300, 150), (700, 150), (700, 230)], STEEL, 22)
    p.wheel(320, 780, 48)
    p.wheel(680, 780, 48)


def art_smoke_tester(p: Pen, c=YEL):
    """Duman kaçak tespit cihazı."""
    p.rect(230, 360, 770, 800, c, r=40)
    p.rect(255, 385, 745, 440, shade(c, 1.2), r=16)
    p.rect(290, 480, 520, 640, INK, r=16)
    p.rect(310, 500, 500, 560, "#67d4ff", r=8)
    p.gauge(630, 560, 70)
    p.rect(290, 680, 710, 740, shade(c, 0.85), r=12)
    p.line([(770, 500), (860, 470), (900, 360), (860, 260)], INK, 22)   # hortum
    p.rect(830, 210, 890, 270, STEEL, r=10)
    for i, (x, y, r) in enumerate(((880, 160, 40), (820, 110, 30), (930, 100, 26))):  # duman
        p.circ(x, y, r, STEEL4)
    p.line([(400, 360), (400, 280), (600, 280), (600, 360)], INK, 26)  # sap


ARTS = {k[4:]: v for k, v in globals().items() if k.startswith("art_")}


# ============================================================ kompozisyon
def render_art(kind: str, color=None, size=1000):
    p = Pen(size)
    fn = ARTS[kind]
    fn(p, color) if color else fn(p)
    im = p.im.resize((size, size), Image.LANCZOS)
    return im.crop(im.getbbox())


def product_image(kind, color, canvas=(1000, 1000), bg=(255, 255, 255), flip=False, scale=0.78, tint=None):
    art = render_art(kind, color)
    if flip:
        art = art.transpose(Image.FLIP_LEFT_RIGHT)
    W, H = canvas
    k = min(W * scale / art.width, H * scale / art.height)
    art = art.resize((max(1, int(art.width * k)), max(1, int(art.height * k))), Image.LANCZOS)
    base = Image.new("RGB", canvas, bg)
    if tint:  # açık renkli zemin dairesi (ikinci görsel)
        dd = ImageDraw.Draw(base)
        r = min(W, H) * 0.42
        dd.ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=tint)
    x, y = (W - art.width) // 2, (H - art.height) // 2
    # yumuşak zemin gölgesi
    sh = Image.new("L", canvas, 0)
    ImageDraw.Draw(sh).ellipse((x + art.width * 0.08, y + art.height - art.height * 0.035,
                                x + art.width * 0.92, y + art.height + art.height * 0.045), fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(max(6, W // 70)))
    base.paste(Image.new("RGB", canvas, (40, 46, 52)), (0, 0), sh)
    base.paste(art, (x, y), art)
    return base


def detail_image(kind, color, canvas=(1000, 1000)):
    """Yakın plan: çizimin bir bölümünü büyüt (ikinci/üçüncü görsel)."""
    art = render_art(kind, color, 1000)
    w, h = art.size
    crop = art.crop((int(w * 0.18), int(h * 0.05), int(w * 0.92), int(h * 0.7)))
    base = Image.new("RGB", canvas, (246, 247, 249))
    k = min(canvas[0] * 0.9 / crop.width, canvas[1] * 0.9 / crop.height)
    crop = crop.resize((int(crop.width * k), int(crop.height * k)), Image.LANCZOS)
    base.paste(crop, ((canvas[0] - crop.width) // 2, (canvas[1] - crop.height) // 2), crop)
    return base


def save(im, rel, q=82):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=q, method=6)
    return path


def text_lines(d, x, y, parts, max_w=None):
    """parts: [(metin, font, renk)] tek satır parçaları sıralı."""
    for s, f, col in parts:
        d.text((x, y), s, font=f, fill=col)
        x += d.textlength(s, font=f)


def hero(slide):
    """1920x422 (Electro home-v1 hero oranı). Sol %62 boş (metin + dikey menü), ürün sağda."""
    W, H = 1920, 422
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    # yumuşak diyagonal vurgu
    ov = Image.new("L", (W, H), 0)
    od = ImageDraw.Draw(ov)
    od.polygon([(1100, 0), (1920, 0), (1920, 422), (940, 422)], fill=255)
    ov = ov.filter(ImageFilter.GaussianBlur(2))
    im.paste(Image.new("RGB", (W, H), (254, 246, 196)), (0, 0), ov)
    d.ellipse((1120, -140, 1600, 340), fill=(254, 236, 128))
    for i, (kind, col, sc, dx, dy) in enumerate(slide["arts"]):
        art = render_art(kind, col)
        k = H * sc / art.height
        art = art.resize((int(art.width * k), int(art.height * k)), Image.LANCZOS)
        x, y = dx - art.width // 2, H - art.height - dy
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).ellipse((x + art.width * 0.1, y + art.height - 10, x + art.width * 0.9, y + art.height + 14), fill=80)
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        im.paste(Image.new("RGB", (W, H), (60, 60, 60)), (0, 0), sh)
        im.paste(art, (x, y), art)
    return im


def hero_mobile(slide):
    """Mobil hero (≤767px) — 800x860: üst-sol metin alanı, ürün altta."""
    W, H = 800, 860
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    d.ellipse((330, 460, 930, 1060), fill=(254, 236, 128))
    kind, col, *_ = slide["arts"][0]
    art = render_art(kind, col)
    k = min(400 / art.height, 520 / art.width)
    art = art.resize((int(art.width * k), int(art.height * k)), Image.LANCZOS)
    x, y = W - art.width - 50, H - art.height - 40
    im.paste(art, (x, y), art)
    return im


def small_banner(b):
    """Electro 4'lü fırsat kartı görünümü (bg-gray-1, solda ürün, sağda yazı) — 720x400."""
    W, H = 720, 400
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    art = render_art(b["art"], b.get("color"))
    k = min(300 / art.width, 300 / art.height)
    art = art.resize((int(art.width * k), int(art.height * k)), Image.LANCZOS)
    im.paste(art, (40 + (300 - art.width) // 2, (H - art.height) // 2), art)
    size = 40
    while size > 24:  # en uzun satır 310px'e sığana kadar küçült
        fl, fb = _font("light", size), _font("bold", size)
        if max(sum(d.textlength(s, font=fb if bold else fl) for s, bold in line) for line in b["lines"]) <= 310:
            break
        size -= 2
    fs = _font("bold", 30)
    y = 105
    for line in b["lines"]:
        x = 380
        for s, bold in line:
            f = fb if bold else fl
            d.text((x, y), s, font=f, fill=(51, 62, 72))
            x += d.textlength(s, font=f)
        y += int(size * 1.3)
    d.text((380, y + 26), "Hemen İncele", font=fs, fill=(51, 62, 72))
    tx = 380 + d.textlength("Hemen İncele ", font=fs)
    d.ellipse((tx, y + 28, tx + 34, y + 62), fill=(254, 215, 0))
    d.polygon([(tx + 13, y + 37), (tx + 24, y + 45), (tx + 13, y + 53)], fill=(51, 62, 72))
    return im


def wide_banner():
    """Tam genişlik kampanya bandı — 1170x207 (şablon v1.0 home-v1-banner ölçüsü)."""
    W, H = 1170, 207
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    for i, (kind, col) in enumerate((("tool_cart", RED), ("socket_set", RED), ("ratchet", None))):
        art = render_art(kind, col)
        k = 165 / art.height if kind != "socket_set" else 120 / art.height
        art = art.resize((int(art.width * k), int(art.height * k)), Image.LANCZOS)
        im.paste(art, (30 + i * 125, H - art.height - 20), art)
    fl, fb = _font("light", 30), _font("bold", 30)
    x, y = 450, 62
    for s_, f in (("ATÖLYENİZİ ", fl), ("KAZANÇLA", fb), (" DONATIN", fl)):
        d.text((x, y), s_, font=f, fill=(51, 62, 72))
        x += d.textlength(s_, font=f)
    d.text((450, 108), "El aletleri ve takım arabalarında %20'ye varan indirim", font=_font("regular", 18), fill=(51, 62, 72))
    d.rounded_rectangle((930, 55, 1140, 152), radius=12, fill=(254, 215, 0))
    d.text((1035, 84), "FIRSATLAR", font=_font("light", 20), fill=(51, 62, 72), anchor="mm")
    d.text((1035, 119), "%20'ye varan", font=_font("bold", 26), fill=(51, 62, 72), anchor="mm")
    return im


def ad_image(kind, color, size):
    """Reklam bloğu görseli (şablon v1.0 ads-block: 410x281 / 714x486) — açık zemin, metinsiz."""
    W, H = size
    im = Image.new("RGB", (W, H), (245, 245, 245))
    art = render_art(kind, color)
    k = min(W * 0.8 / art.width, H * 0.8 / art.height)
    art = art.resize((int(art.width * k), int(art.height * k)), Image.LANCZOS)
    im.paste(art, ((W - art.width) // 2, (H - art.height) // 2), art)
    return im


def brand_logo(name, style):
    """200x60 marka logosu (demo markalar — gri tonlu kelime işareti)."""
    W, H = 400, 120  # 2x çiz, sonra küçült
    im = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    f = _font("xbold" if style % 2 == 0 else "bold", 54)
    tw = d.textlength(name, font=f)
    x = (W - tw) / 2
    if style % 3 == 0:
        d.rounded_rectangle((x - 22, 22, x + tw + 22, 98), radius=14, outline=(90, 98, 106), width=6)
    d.text((W / 2, H / 2), name, font=f, fill=(90, 98, 106), anchor="mm")
    if style % 3 == 1:
        d.ellipse((x + tw + 6, 70, x + tw + 22, 86), fill=(254, 215, 0))
    return im.resize((200, 60), Image.LANCZOS)


ADS = [("ad-1", "socket_set", RED, (410, 281)), ("ad-2", "compressor", BLUE, (410, 281)), ("ad-3", "tool_cart", RED, (714, 486))]
BRANDS = ["GarajTek Pro", "Liftmax", "Airpro", "Torkmatik", "Balanstek", "Voltix", "Weldon", "Diagnox", "Teknolift", "Atölye Pro"]


# Ürün görsel planı: (anahtar, tür, renk, tuval boyutu) — farklı en-boy oranları gerçek
# yüklemeleri taklit eder (kare, dikey, yatay). Anahtarlar demo_content.P ile birebir.
PRODUCT_ART = {
    "lift2-4t": ("lift2", YEL, (1200, 1200)),
    "lift2-5t": ("lift2", BLUE, (1000, 1300)),
    "scissor-32t": ("scissor", RED, (1600, 1000)),
    "moto-lift": ("moto", BLUE, (1500, 1000)),
    "comp-200": ("compressor", RED, (1400, 1000)),
    "comp-50-silent": ("compressor_v", BLUE, (900, 1300)),
    "impact-12": ("impact", YEL, (1000, 1000)),
    "tire-changer": ("tire_changer", RED, (1000, 1200)),
    "balancer": ("balancer", BLUE, (1200, 1000)),
    "inflator": ("inflator", YEL, (800, 1000)),
    "floor-jack-3t": ("floor_jack", RED, (1500, 1000)),
    "engine-crane": ("engine_crane", RED, (1400, 1100)),
    "press-20t": ("press", BLUE, (1000, 1200)),
    "cart-full-185": ("tool_cart", RED, (900, 1200)),
    "cart-empty-7": ("tool_cart", BLUE, (1000, 1200)),
    "socket-108": ("socket_set", RED, (1400, 1000)),
    "socket-94": ("socket_set", BLUE, (1200, 1000)),
    "torque-wrench": ("torque_wrench", None, (1000, 1000)),
    "wrench-12": ("wrench_set", None, (1200, 1000)),
    "battery-tester": ("battery_tester", YEL, (1000, 1100)),
    "booster": ("booster", RED, (1000, 1100)),
    "oil-drain-80": ("oil_drain", RED, (900, 1300)),
    "smoke-tester": ("smoke_tester", YEL, (1100, 1000)),
    "work-light": ("work_light", YEL, (1000, 1200)),
    "workbench": ("workbench", BLUE, (1400, 1000)),
}

# Ürün Setleri kolaj görselleri (demo_content.SETS ile aynı anahtarlar)
SET_ART = {
    "set-lastikci": [("tire_changer", RED), ("balancer", BLUE), ("compressor", RED), ("impact", YEL)],
    "set-oto-servis": [("lift2", YEL), ("floor_jack", RED), ("engine_crane", RED), ("oil_drain", RED),
                       ("smoke_tester", YEL), ("battery_tester", YEL)],
    "set-el-aletleri": [("tool_cart", BLUE), ("socket_set", BLUE), ("torque_wrench", None), ("wrench_set", None),
                        ("impact", YEL), ("work_light", YEL)],
}


def set_image(arts, canvas=(1200, 1000), variant=0):
    """Set kolajı: bileşen çizimleri ızgarada + sol üstte 'ÜRÜN SETİ' rozeti."""
    W, H = canvas
    im = Image.new("RGB", canvas, (246, 247, 249) if variant == 0 else (255, 255, 255))
    d = ImageDraw.Draw(im)
    n = len(arts)
    cols = 2 if n <= 4 else 3
    rows = math.ceil(n / cols)
    top = 150
    cw, ch = (W - 80) / cols, (H - top - 40) / rows
    order = arts if variant == 0 else list(reversed(arts))
    for i, (kind, col) in enumerate(order):
        art = render_art(kind, col)
        if variant and i % 2:
            art = art.transpose(Image.FLIP_LEFT_RIGHT)
        k = min(cw * 0.82 / art.width, ch * 0.82 / art.height)
        art = art.resize((max(1, int(art.width * k)), max(1, int(art.height * k))), Image.LANCZOS)
        cx = 40 + (i % cols) * cw + cw / 2
        cy = top + (i // cols) * ch + ch / 2
        d.ellipse((cx - cw * 0.42, cy + art.height / 2 - 14, cx + cw * 0.42, cy + art.height / 2 + 10), fill=(228, 231, 235))
        im.paste(art, (int(cx - art.width / 2), int(cy - art.height / 2)), art)
    d.rounded_rectangle((40, 40, 330, 112), radius=36, fill=(254, 215, 0))
    d.text((185, 76), "ÜRÜN SETİ", font=_font("xbold", 34), fill=(51, 62, 72), anchor="mm")
    d.text((360, 76), f"{n} ürün tek sepette", font=_font("semibold", 30), fill=(91, 102, 112), anchor="lm")
    return im


HEROES = [
    {"key": "hero-1", "arts": [("lift2", YEL, 0.96, 1360, 0)]},
    {"key": "hero-2", "arts": [("compressor", RED, 0.78, 1250, 14), ("impact", YEL, 0.42, 1490, 30)]},
    {"key": "hero-3", "arts": [("tire_changer", RED, 0.92, 1220, 0), ("balancer", BLUE, 0.82, 1460, 0)]},
]

SMALL = [
    {"key": "small-1", "art": "socket_set", "color": RED, "lines": [[("LOKMA ", False), ("TAKIMLARINDA", True)], [("BÜYÜK FIRSAT", False)]]},
    {"key": "small-2", "art": "compressor", "color": BLUE, "lines": [[("KOMPRESÖR", True)], [("SEZONU BAŞLADI", False)]]},
    {"key": "small-3", "art": "obd", "color": YEL, "lines": [[("ARIZA TESPİTİ", True)], [("ARTIK ÇOK KOLAY", False)]]},
    {"key": "small-4", "art": "tool_cart", "color": BLUE, "lines": [[("ÜRÜN ", False), ("SETLERİ", True)], [("TEK TIKLA SEPETTE", False)]]},
]


def main():
    only = set(sys.argv[1:])
    for key, (kind, col, canvas) in PRODUCT_ART.items():
        if only and key not in only:
            continue
        save(product_image(kind, col, canvas), f"products/{key}-1.webp")
        save(product_image(kind, col, (1000, 1000), bg=(255, 255, 255), flip=True, scale=0.7, tint=(247, 247, 247)), f"products/{key}-2.webp")
        save(detail_image(kind, col), f"products/{key}-3.webp")
    for key, arts in SET_ART.items():
        if only and key not in only and "sets" not in only:
            continue
        save(set_image(arts), f"products/{key}-1.webp")
        save(set_image(arts, variant=1), f"products/{key}-2.webp")
    if not only or "banners" in only:
        for h in HEROES:
            save(hero(h), f"banners/{h['key']}.webp", q=80)
            save(hero_mobile(h), f"banners/{h['key']}-m.webp", q=80)
        for b in SMALL:
            save(small_banner(b), f"banners/{b['key']}.webp")
        save(wide_banner(), "banners/wide-1.webp")
        for key, kind, col, size in ADS:
            save(ad_image(kind, col, size), f"banners/{key}.webp")
        os.makedirs(os.path.join(OUT, "brands"), exist_ok=True)
        for i, name in enumerate(BRANDS):
            brand_logo(name, i).save(os.path.join(OUT, "brands", f"brand-{i + 1}.png"), optimize=True)
    total = 0
    for root, _d, files in os.walk(OUT):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    print(f"img/: {total / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
