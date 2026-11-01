#!/usr/bin/env python3
"""Export native relic sizes and hover outlines from the two painted PNG masters.

Only deterministic sizing and alpha-mask export happen here; this never redraws
approved character, card or UI art. The regular PCK build copies these exports.
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / 'src/Volibear/Presentation/icons'


def export():
    for name in ('lightning_heart', 'storm_crown'):
        with Image.open(ICONS / 'masters' / (name + '.png')) as source:
            if source.mode != 'RGBA' or source.width != source.height:
                raise ValueError('Relic master must be square RGBA: ' + name)
            # Premultiplied-alpha resizing keeps the dark contour clean over any UI.
            for folder, size in (('relics', 64), ('relics/big', 256)):
                icon = source.convert('RGBa').resize((size, size), Image.Resampling.LANCZOS).convert('RGBA')
                destination = ICONS / folder / (name + '.png')
                destination.parent.mkdir(parents=True, exist_ok=True)
                icon.save(destination, optimize=True)
                if size == 64:
                    alpha = icon.getchannel('A')
                    edge = ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(5)),
                                               alpha.filter(ImageFilter.MinFilter(3)))
                    outline = Image.new('RGBA', icon.size, (217, 247, 255, 0))
                    outline.putalpha(edge)
                    destination = ICONS / 'relics/outline' / (name + '.png')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    outline.save(destination, optimize=True)
    print('Exported 2 painted relics at 64/256px and 2 matching hover outlines.')


if __name__ == '__main__':
    export()
