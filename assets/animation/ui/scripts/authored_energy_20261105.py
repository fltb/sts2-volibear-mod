"""Derive the 2026-11-05 authored energy/domain art into runtime RGBA exports."""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageEnhance
ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parents[1] / 'source/energy_20261105'
UI = ROOT / 'assets/animation/ui/images'

def load(name): return Image.open(SRC / name).convert('RGBA')

def trim_square(im, size):
    alpha = im.getchannel('A').point(lambda a: 255 if a > 8 else 0)
    box = alpha.getbbox()
    im = im.crop(box)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((side - w) // 2, (side - h) // 2))
    return canvas.resize((size, size), Image.LANCZOS)

def shade_center(im, strength=0.40, radius=0.62, blur=0.07, tint=(6, 16, 28)):
    w, h = im.size
    mask = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(mask)
    r = w * radius / 2
    d.ellipse((w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r), fill=int(255 * strength))
    mask = mask.filter(ImageFilter.GaussianBlur(w * blur))
    dark = Image.new('RGBA', (w, h), (*tint, 0))
    dark.putalpha(mask)
    return Image.alpha_composite(im, dark)

def cold(im, brightness=0.34, tint=(40, 52, 70), tint_mix=0.45, rim=None):
    gray = ImageOps.grayscale(im.convert('RGB')).point(lambda v: int(v * brightness))
    tinted = Image.blend(gray.convert('RGB'), Image.new('RGB', im.size, tint), tint_mix)
    out = tinted.convert('RGBA')
    alpha = im.getchannel('A')
    out.putalpha(alpha)
    if rim is not None:
        edge = ImageChops.subtract(alpha.filter(ImageFilter.GaussianBlur(6)), alpha.filter(ImageFilter.GaussianBlur(1)))
        glow = Image.new('RGBA', im.size, (*rim, 0)); glow.putalpha(edge.point(lambda v: int(v * 0.5)))
        out = Image.alpha_composite(out, glow)
    return out

# 1) charged energy crest (HUD emblem), 256
crest = trim_square(load('energy_crest_charged.png'), 256)
crest.save(UI / 'energy_master.png')

# 2) depleted crest, same silhouette
crest_empty = cold(crest, brightness=0.42, tint=(40, 52, 70), tint_mix=0.42, rim=(60, 110, 150))
crest_empty.save(UI / 'big_energy_empty.png')

# 3) card cost frame: simple gold ring, flat opaque numeric centre
cost = trim_square(load('cost_badge.png'), 74)
d = ImageDraw.Draw(cost)
d.ellipse((14, 14, 60, 60), fill=(13, 24, 46, 255))
for x in range(25, 49):
    for y in range(22, 52):
        cost.putpixel((x, y), (13, 24, 46, 255))
cost.save(UI / 'big_energy.png')

# 4) charged orb: slightly smaller inside the 128 control, softer outer bloom
orb = trim_square(load('energy_orb_charged.png'), 256)
orb = shade_center(orb, strength=0.46, radius=0.60)
inner = orb.resize((225, 225), Image.LANCZOS)
framed = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
framed.alpha_composite(inner, (15, 15))
# keep the painted detail, mute only the halo that used to blow out the screen edge
px = framed.load()
for x in range(256):
    for y in range(256):
        dx, dy = (x - 128) / 128.0, (y - 128) / 128.0
        r = (dx * dx + dy * dy) ** 0.5
        if r > 0.44:
            f = max(0.55, 1.0 - (r - 0.44) * 0.9)
            rr, gg, bb, aa = px[x, y]
            px[x, y] = (rr, gg, bb, int(aa * f))
framed.save(UI / 'energy_orb_charged.png')

# 5) depleted orb: cold cracked glass with visible structure, never a flat grey disc
source = Image.open(UI / 'energy_orb_charged.png').convert('RGBA')
luma = ImageOps.grayscale(source.convert('RGB'))
detail = luma.point(lambda v: int(min(255, 26 + v * 0.62)))
steel = ImageOps.colorize(detail, (10, 17, 28), (126, 164, 190))
steel = steel.convert('RGBA'); steel.putalpha(source.getchannel('A'))
# faint dormant charge in the old lightning paths
mask = luma.point(lambda v: int(max(0, (v - 120)) * 1.4))
glow = Image.new('RGBA', source.size, (96, 168, 205, 0)); glow.putalpha(mask.point(lambda v: int(v * 0.30)))
empty_orb = Image.alpha_composite(steel, glow)
empty_orb.save(UI / 'energy_orb_empty.png')

# 6) suppression seal used by the disabled overlays (no text), calmer so intents stay readable
seal = trim_square(load('suppress_rune.png'), 128)
seal = ImageEnhance.Brightness(seal).enhance(0.76)
seal.save(UI / 'domain_suppress_seal.png')

# 7) storm aura texture: wide ground ellipse with compressed highlights (no blown white)
aura = load('storm_aura.png')
alpha = aura.getchannel('A').point(lambda a: 255 if a > 8 else 0)
aura = aura.crop(alpha.getbbox())
w, h = aura.size
target_w = 1024
aura = aura.resize((target_w, round(h * target_w / w)), Image.LANCZOS)
keep_alpha = aura.getchannel('A')
rgb = aura.convert('RGB').point(lambda v: int(min(232, v * 0.93)))
aura = rgb.convert('RGBA'); aura.putalpha(keep_alpha)
pad = Image.new('RGBA', (target_w, round(aura.height * 1.12)), (0, 0, 0, 0))
pad.alpha_composite(aura, (0, (pad.height - aura.height) // 2))
pad.save(UI / 'domain_storm_aura.png')

for name in ('energy_master.png', 'big_energy_empty.png', 'big_energy.png',
             'energy_orb_charged.png', 'energy_orb_empty.png',
             'domain_suppress_seal.png', 'domain_storm_aura.png'):
    im = Image.open(UI / name)
    print(name, im.size, im.mode)
