import sys, struct
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_dump import md
def method_il(mi):
    r=md.row(6,mi)
    rva=r[0]
    if rva==0: return b''
    off=md.pe.off(rva)
    d=md.pe.d
    b=d[off]
    if b&3==2:  # tiny
        size=b>>2; start=off+1
    else:
        # fat: flags(2) maxstack(2) codesize(4) localvarsig(4)
        size=struct.unpack_from('<I',d,off+4)[0]
        start=off+12
    return d[start:start+size]
def us(tok):
    idx=tok&0xffffff
    o=md.us+idx
    d=md.pe.d
    b0=d[o]
    if b0&0x80==0: ln=b0; o+=1
    elif b0&0xC0==0x80: ln=((b0&0x3f)<<8)|d[o+1]; o+=2
    else: ln=((b0&0x1f)<<24)|(d[o+1]<<16)|(d[o+2]<<8)|d[o+3]; o+=4
    # UTF-16
    raw=d[o:o+ln]
    return raw.decode('utf-16-le','replace')
def strings_of(mi):
    il=method_il(mi); out=[]
    for i in range(len(il)-4):
        if il[i]==0x72:
            tok=struct.unpack_from('<I',il,i+1)[0]
            if tok>>24==0x70:
                try: s=us(tok)
                except Exception: continue
                s=s.split('\ufffd')[0].rstrip('\x00')
                if s and len(s)>1:
                    out.append(s)
    return out
def find_method(type_ns, type_name, meth):
    from dump import tdefs
    ti=tdefs.get((type_ns,type_name))
    if not ti: return None
    r=md.row(2,ti); start=r[5]
    nxt=md.row(2,ti+1)[5] if ti<md.rows[2] else md.rows[6]+1
    for mi in range(start,nxt):
        if md.string(md.row(6,mi)[3])==meth: return mi
    return None
def show(ns,name,meth):
    mi=find_method(ns,name,meth)
    if not mi: print('MISS',name,meth); return
    print('###',name+'.'+meth)
    for s in strings_of(mi): print('  str:',repr(s))
if __name__=='__main__':
    for m in ['GetModdedLocTables','ReadModManifest','ReadModsInDirRecursive','TryLoadMod','Initialize']:
        show('MegaCrit.Sts2.Core.Modding','ModManager',m)
