#!/usr/bin/env python3
"""Verify every delivered file against SHA256SUMS using only Python stdlib."""
from pathlib import Path
import argparse, hashlib, json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args()
    root=args.root.resolve();manifest=root/'SHA256SUMS';errors=[];count=0;seen=set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest,rel=line.split('  ',1);file=(root/rel).resolve()
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid hash record')
        if not file.is_relative_to(root) or rel in seen:raise ValueError('Unsafe or duplicate checksum path: '+rel)
        seen.add(rel);count+=1
        if not file.is_file():errors.append({'path':rel,'error':'missing'});continue
        h=hashlib.sha256()
        with file.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=digest:errors.append({'path':rel,'error':'SHA256 differs'})
    print(json.dumps({'passed':not errors,'checked_files':count,'errors':errors},ensure_ascii=False))
    raise SystemExit(1 if errors else 0)
if __name__=='__main__':main()
