#!/usr/bin/env python3
"""Fetch the exact publicly distributed CC0 source recordings used by this pack."""
from pathlib import Path
import datetime, hashlib, json, urllib.request, zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'source'
SOURCES = [
    ('monster_roar.wav', 'https://opengameart.org/sites/default/files/monster_roar.wav', 'trazzz123', 'https://opengameart.org/content/cc0-deep-monster-roar'),
    ('monster-snarls.ogg', 'https://opengameart.org/sites/default/files/monster-snarls_0.ogg', 'Darsycho', 'https://opengameart.org/content/monster-snarls'),
    ('monster-snarls-2.ogg', 'https://opengameart.org/sites/default/files/monster-snarls-2_0.ogg', 'Darsycho', 'https://opengameart.org/content/monster-snarls'),
    ('monsters-snarls-3.ogg', 'https://opengameart.org/sites/default/files/monsters-snarls-3_0.ogg', 'Darsycho', 'https://opengameart.org/content/monster-snarls'),
    ('monster-snarl-attack.ogg', 'https://opengameart.org/sites/default/files/monster-snarl-attack.ogg', 'Darsycho', 'https://opengameart.org/content/monster-snarls'),
    ('monster-snarl-5.ogg', 'https://opengameart.org/sites/default/files/monster-snarl-5.ogg', 'Darsycho', 'https://opengameart.org/content/monster-snarls'),
    ('kenney_impact-sounds.zip', 'https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip', 'Kenney', 'https://kenney.nl/assets/impact-sounds'),
]

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    records=[]
    for name, url, author, page in SOURCES:
        p=RAW/name
        if not p.exists():
            req=urllib.request.Request(url, headers={'User-Agent':'VolibearAssetBuild/5.0'})
            with urllib.request.urlopen(req, timeout=40) as r:
                data=r.read()
            p.write_bytes(data)
        records.append({'file':str(p.relative_to(ROOT)), 'author':author, 'source_page':page, 'download_url':url, 'license':'CC0-1.0', 'license_url':'https://creativecommons.org/publicdomain/zero/1.0/', 'size_bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        print(name,p.stat().st_size,flush=True)
    (ROOT/'sources.json').write_text(json.dumps({'schema_version':1,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recordings':records,'scope':'Recordings and derived audio only. No official Riot voice or performance is included.'},ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(RAW/'kenney_impact-sounds.zip') as z:
        print('KENNEY ARCHIVE:', '\n'.join(z.namelist()),flush=True)

if __name__=='__main__':
    main()
