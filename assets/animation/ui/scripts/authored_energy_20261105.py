"""Derive the 2026-11-05 authored energy/domain art into runtime RGBA exports."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'assets/animation/ui/source/energy_20261105'
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

def cold(im, brightness=0.34, tint=(40, 52, 70), tint_mix=0.45):
    gray = ImageOps.grayscale(im.convert('RGB')).point(lambda v: int(v * brightness))
    tinted = Image.blend(gray.convert('RGB'), Image.new('RGB', im.size, tint), tint_mix)
    out = tinted.convert('RGBA')
    out.putalpha(im.getchannel('A'))
    return out

# 1) charged energy crest (HUD emblem), 256
crest = trim_square(load('energy_crest_charged.png'), 256)
crest.save(UI / 'energy_master.png')

# 2) depleted crest, same silhouette
crest_empty = cold(crest, brightness=0.30, tint=(34, 44, 58), tint_mix=0.52)
crest_empty.save(UI / 'big_energy_empty.png')

# 3) card cost frame: flat opaque numeric centre, ornament only on the rim
cost = trim_square(load('cost_badge.png'), 74)
d = ImageDraw.Draw(cost)
centre = cost.getpixel((37, 36))
if centre[3] < 255:
    centre = (18, 33, 48, 255)
    d.ellipse((16, 13, 58, 61), fill=centre)
else:
    d.ellipse((16, 13, 58, 61), fill=(centre[0], centre[1], centre[2], 255))
for x in range(25, 49):
    for y in range(22, 52):
        cost.putpixel((x, y), (centre[0], centre[1], centre[2], 255))
cost.save(UI / 'big_energy.png')

# 4) energy orb art: charged + depleted, darkened centre keeps the number readable
orb = trim_square(load('energy_orb_charged.png'), 256)
orb = shade_center(orb, strength=0.46, radius=0.60)
orb.save(UI / 'energy_orb_charged.png')
orb_empty = cold(orb, brightness=0.30, tint=(28, 38, 52), tint_mix=0.55)
orb_empty.save(UI / 'energy_orb_empty.png')

# 5) suppression seal used by the disabled overlays (no text)
seal = trim_square(load('suppress_rune.png'), 128)
seal = ImageEnhance.Brightness(seal).enhance(0.86)
seal.save(UI / 'domain_suppress_seal.png')

# 6) storm aura texture: keep the wide ground ellipse, modest padding
aura = load('storm_aura.png')
alpha = aura.getchannel('A').point(lambda a: 255 if a > 8 else 0)
aura = aura.crop(alpha.getbbox())
w, h = aura.size
target_w = 1024
aura = aura.resize((target_w, round(h * target_w / w)), Image.LANCZOS)
pad = Image.new('RGBA', (target_w, round(aura.height * 1.12)), (0, 0, 0, 0))
pad.alpha_composite(aura, (0, (pad.height - aura.height) // 2))
pad.save(UI / 'domain_storm_aura.png')

for name in ('energy_master.png', 'big_energy_empty.png', 'big_energy.png',
             'energy_orb_charged.png', 'energy_orb_empty.png',
             'domain_suppress_seal.png', 'domain_storm_aura.png'):
    im = Image.open(UI / name)
    print(name, im.size, im.mode)
