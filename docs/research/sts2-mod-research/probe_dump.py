import sys, json, struct
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_mdread import load
DLL='/home/float/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/Slay the Spire 2/data_sts2_linuxbsd_x86_64/sts2.dll'
md,sig=load(DLL)

# index typedefs
tdefs={}
for i in range(1, md.rows[0x02]+1):
    ns,nm=md.typedef_name(i)
    tdefs[(ns,nm)]=i
byname={}
for (ns,nm),i in tdefs.items():
    byname.setdefault(nm,[]).append(i)

FMASK={0:'priv',1:'famandassem',2:'internal',3:'protected',4:'protectedinternal',5:'public',6:'public'}
def field_vis(f):
    a=f&7
    return {0:'compilercontrolled',1:'private',2:'famandassem',3:'internal',4:'protected',5:'protectedinternal',6:'public'}.get(a,'?'+str(a))
def method_vis(f):
    a=f&7
    return {0:'compilercontrolled',1:'private',2:'famandassem',3:'internal',4:'protected',5:'protectedinternal',6:'public'}.get(a,'?'+str(a))

# base type resolution
def type_name(coded):
    tbl,idx=md.decode_coded('TypeDefOrRef', coded)
    if idx==0: return None
    return md.type_name_of(tbl,idx)

# fields
def fields_of(ti):
    r=md.row(0x02,ti); start=r[4]
    nxt=md.row(0x02,ti+1)[4] if ti<md.rows[0x02] else md.rows[0x04]+1
    out=[]
    for fi in range(start,nxt):
        fr=md.row(0x04,fi)
        t,fl=sig.fieldsig(md.blob(fr[2]))
        out.append(dict(name=md.string(fr[1]), type=t, vis=field_vis(fr[0]), static=bool(fr[0]&0x10), literal=bool(fr[0]&0x40), initonly=bool(fr[0]&0x20), row=fi))
    return out
# methods
def methods_of(ti):
    r=md.row(0x02,ti); start=r[5]
    nxt=md.row(0x02,ti+1)[5] if ti<md.rows[0x02] else md.rows[0x06]+1
    out=[]
    for mi in range(start,nxt):
        mr=md.row(0x06,mi)
        try:
            ret,params,_=sig.methodsig(md.blob(mr[4]))
        except Exception as e:
            ret,params='ERR',''
        out.append(dict(name=md.string(mr[3]), ret=ret, params=params, vis=method_vis(mr[2]),
                        static=bool(mr[2]&0x10), virtual=bool(mr[2]&0x40), abstract=bool(mr[2]&0x400), row=mi))
    return out
# properties
def props_of(ti):
    pm=md.row(0x15,ti) if ti<=md.rows.get(0x15,0) else None
    # propertymap rows: find row with parent==ti
    start=None
    for pi in range(1, md.rows.get(0x15,0)+1):
        if md.row(0x15,pi)[0]==ti: start=pi; break
    if not start: return []
    pstart=md.row(0x15,start)[1]
    pnext=md.row(0x15,start+1)[1] if start<md.rows[0x15] else md.rows[0x17]+1
    out=[]
    for pi in range(pstart,pnext):
        pr=md.row(0x17,pi)
        try:
            t,params,_=sig.propsig(md.blob(pr[2]))
        except Exception:
            t,params='ERR',[]
        out.append(dict(name=md.string(pr[1]), type=t, params=params, row=pi))
    return out
# custom attributes on props/fields/types
def ca_map():
    prop_ca={}; field_ca={}; type_ca={}
    n=md.rows.get(0x0C,0)
    for ci in range(1,n+1):
        cr=md.row(0x0C,ci)
        tbl,idx=md.decode_coded('HasCustomAttribute', cr[0])
        try: an=md.resolve_customattr_type(ci)
        except Exception: continue
        if tbl==0x17: prop_ca.setdefault(idx,[]).append((an,cr[2]))
        elif tbl==0x04: field_ca.setdefault(idx,[]).append((an,cr[2]))
        elif tbl==0x02: type_ca.setdefault(idx,[]).append((an,cr[2]))
        elif tbl==0x06: pass
    return prop_ca, field_ca, type_ca
prop_ca, field_ca, type_ca = ca_map()
def ca_string(blobidx):
    b=md.blob(blobidx)
    if len(b)<3: return None
    # prolog 01 00 then serstring
    i=2; b0=b[i]
    if b0&0x80==0: ln=b0; i+=1
    elif b0&0xC0==0x80: ln=((b0&0x3f)<<8)|b[i+1]; i+=2
    else: ln=((b0&0x1f)<<24)|(b[i+1]<<16)|(b[i+2]<<8)|b[i+3]; i+=4
    return b[i:i+ln].decode('utf-8','replace')
def json_keys(prop_row, attrs):
    for an,blob in attrs:
        if an and 'JsonPropertyName' in an:
            try: return ca_string(blob)
            except Exception: return '<err>'
    return None
# enum values
CONSTT={0x02:'bool',0x03:'char',0x04:'int8',0x05:'uint8',0x06:'int16',0x07:'uint16',0x08:'int32',0x09:'uint32',0x0a:'int64',0x0b:'uint64',0x0c:'float32',0x0d:'float64',0x0e:'string'}
const_by_field={}
for ci in range(1, md.rows.get(0x0B,0)+1):
    cr=md.row(0x0B,ci)
    tbl,idx=md.decode_coded('HasConstant', cr[1])
    if tbl==0x04: const_by_field[idx]=(cr[0], md.blob(cr[2]))
def enum_values(ti):
    vals=[]
    for f in fields_of(ti):
        if f['row'] in const_by_field:
            ct,b=const_by_field[f['row']]
            t=CONSTT.get(ct,'?')
            try:
                v=struct.unpack('<i',b)[0] if t=='int32' else struct.unpack('<I',b)[0]
            except Exception: v=b.hex()
            vals.append((f['name'],v))
    return vals

def typeinfo(ns,name):
    ti=tdefs.get((ns,name))
    if not ti:
        cands=byname.get(name)
        if not cands: return None
        ti=cands[0]
    r=md.row(0x02,ti)
    base=type_name(r[3])
    return dict(full=md.string(r[2])+'.' + md.string(r[1]) if False else (md.string(r[2]), md.string(r[1])), base=base,
                fields=fields_of(ti), props=props_of(ti), methods=methods_of(ti), row=ti,
                attrs=[(a, str(md.blob(b)[:60])) for a,b in type_ca.get(ti,[])])
def show(ns,name, out=sys.stdout, meth_filter=None):
    ti=tdefs.get((ns,name))
    if not ti:
        cands=byname.get(name); ti=cands[0] if cands else None
    if not ti:
        print('NOT FOUND', ns,name); return
    r=md.row(0x02,ti)
    print(f'### {md.string(r[2])}.{md.string(r[1])}  (row {ti})  base={type_name(r[3])}')
    for a,b in type_ca.get(ti,[]): print('  [attr]',a,b)
    for f in fields_of(ti): print('  field',f['vis'],'static' if f['static'] else '','literal' if f['literal'] else '',f['type'],f['name'])
    for p in props_of(ti):
        keys=json_keys(p['row'], prop_ca.get(p['row'],[]))
        if keys: print(f"  prop {p['type']} {p['name']}  [JsonPropertyName(\"{keys}\")]")
        else: print(f"  prop {p['type']} {p['name']}")
    for m in methods_of(ti):
        if m['name'].startswith('get_') or m['name'].startswith('set_') or m['name'].startswith('add_') or m['name'].startswith('remove_'): continue
        print(f"  {m['vis']}{' static' if m['static'] else ''}{' virtual' if m['virtual'] else ''}{' abstract' if m['abstract'] else ''} {m['ret']} {m['name']}({', '.join(m['params'])})")
