#!/usr/bin/env python3
"""Subset a locally supplied licensed CJK font for the current offline gallery."""
from pathlib import Path
import argparse
from fontTools import subset
from fontTools.ttLib import TTFont
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--font',type=Path,required=True);a=p.parse_args()
text=''.join((R/x).read_text() for x in ['cards/index.html','START_HERE.html','cards/gallery_data.js'])
f=TTFont(a.font);options=subset.Options();options.flavor='woff';options.recalc_timestamp=False;options.notdef_glyph=True;options.notdef_outline=True
ss=subset.Subsetter(options=options);ss.populate(text=text);ss.subset(f);f.flavor='woff';f.save(R/'cards/fonts/gallery_ui.woff')
print('Saved current offline gallery font')
