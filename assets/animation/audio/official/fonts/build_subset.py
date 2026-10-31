#!/usr/bin/env python3
"""Rebuild this gallery's small, licensed WOFF font from the recorded Noto source.

Requires fonttools; WOFF compression uses the Python standard library. Never modifies the supplied original font/license.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile
import fontTools
from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPECTED_SOURCE_SHA256 = '2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-font', type=Path, required=True)
    parser.add_argument('--source-license', type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.source_font) == EXPECTED_SOURCE_SHA256, 'Use the recorded original Noto CJK source.'
    html = ROOT / 'index.html'; catalog_path = ROOT / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    text = html.read_text(encoding='utf-8') + ''.join(chr(i) for i in range(32,127))
    for row in catalog['entries']:
        text += ''.join(str(row.get(key,'')) for key in ('id','filename','category','language','skin'))
    codepoints = sorted({ord(character) for character in text if ord(character)>=32})
    font = TTFont(args.source_font, recalcTimestamp=False)
    original_copyright = font['name'].getDebugName(0)
    missing = sorted(set(codepoints) - set(font.getBestCmap()))
    assert not missing, 'Original font lacks requested characters: ' + repr(missing)
    options = subset.Options()
    options.flavor = 'woff'; options.recalc_timestamp = False
    options.hinting = False; options.name_IDs = ['*']; options.name_legacy = True
    worker = subset.Subsetter(options=options)
    worker.populate(unicodes=codepoints); worker.subset(font)
    # Give this derived subset its own primary name while preserving copyright/license.
    names = {1:'Volibear Official Audio UI',2:'Regular',3:'VolibearOfficialAudioUI-Regular;subset-v1',4:'Volibear Official Audio UI Regular',6:'VolibearOfficialAudioUI-Regular',16:'Volibear Official Audio UI',17:'Regular',18:'Volibear Official Audio UI Regular'}
    for record in font['name'].names:
        if record.nameID in names: record.string = names[record.nameID].encode(record.getEncoding())
    if 'CFF ' in font:
        cff = font['CFF '].cff; cff.fontNames = ['VolibearOfficialAudioUI-Regular']
        cff.topDictIndex[0].FamilyName = 'Volibear Official Audio UI'
        cff.topDictIndex[0].FullName = 'Volibear Official Audio UI Regular'
    font.flavor = 'woff'
    fd, temporary = tempfile.mkstemp(prefix='.font.', suffix='.woff', dir=HERE)
    os.close(fd)
    target = HERE / 'official_audio_ui.woff'
    try:
        font.save(temporary)
        check = TTFont(temporary)
        assert set(codepoints) <= set(check.getBestCmap()), 'Subset lost requested characters.'
        check.close(); os.replace(temporary, target)
    finally:
        font.close()
        if os.path.exists(temporary): os.unlink(temporary)
    atomic(HERE / 'OFL.txt', args.source_license.read_bytes())
    atomic(HERE / 'characters.txt', (''.join(chr(i) for i in codepoints)+'\n').encode('utf-8'))
    manifest = {
        'schema_version':1,'css_family':'OfficialAudioUI','derived_family':'Volibear Official Audio UI',
        'source':{'filename':args.source_font.name,'sha256':EXPECTED_SOURCE_SHA256,'copyright':original_copyright,'license':'SIL Open Font License 1.1','license_file':'fonts/OFL.txt'},
        'file':'fonts/official_audio_ui.woff','sha256':sha(target),'bytes':target.stat().st_size,
        'license_sha256':sha(HERE/'OFL.txt'),'characters_file':'fonts/characters.txt','characters_sha256':sha(HERE/'characters.txt'),
        'requested_unicode_count':len(codepoints),'missing_codepoints':[],
        'coverage':'All printable characters in index.html, ASCII, and catalog entry id/filename/category/language/skin fields.',
        'input_sha256':{'index.html':sha(html),'catalog.json':sha(catalog_path)},
        'fonttools_version':fontTools.__version__,'builder_sha256':sha(__file__),
        'original_source_unchanged':sha(args.source_font)==EXPECTED_SOURCE_SHA256
    }
    atomic(HERE/'manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__ == '__main__': main()
