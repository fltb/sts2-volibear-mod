#!/usr/bin/env python3
"""Optional font subset rebuild from the documented official Noto font."""
from pathlib import Path
import argparse,hashlib,json,shutil
from fontTools import subset
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-font',type=Path,required=True);ap.add_argument('--license',type=Path,required=True);a=ap.parse_args()
    expected='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
    assert hashlib.sha256(a.source_font.read_bytes()).hexdigest()==expected,'Different font source; review source version first.'
    paths=['index.html','gallery_data.js','card_bindings_data.js','icons_data.js','README.md','CARD_BINDINGS.md']
    text=''.join(sorted(set(''.join((ROOT/p).read_text() for p in paths))))
    out=ROOT/'fonts';out.mkdir(exist_ok=True);(out/'subset_text.txt').write_text(text+'\n');shutil.copy2(a.license,out/'OFL.txt')
    options=subset.Options();options.flavor='woff';options.hinting=False;options.layout_features=['*'];font=subset.load_font(str(a.source_font),options);sub=subset.Subsetter(options=options);sub.populate(text=text);sub.subset(font);subset.save_font(font,str(out/'vfx_ui.woff'),options)
    cm=TTFont(out/'vfx_ui.woff').getBestCmap();missing=sorted(c for c in text if ord(c)>32 and ord(c) not in cm)
    result={'source_url':'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf','source_sha256':expected,'license':'SIL Open Font License 1.1','license_file':'OFL.txt','subset_file':'vfx_ui.woff','subset_sha256':hashlib.sha256((out/'vfx_ui.woff').read_bytes()).hexdigest(),'missing_text_characters':missing,'subset_method':'fontTools.subset; no hinting; WOFF; unique characters in gallery/mappings/docs'}
    (out/'provenance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');assert not missing,missing
if __name__=='__main__':main()
