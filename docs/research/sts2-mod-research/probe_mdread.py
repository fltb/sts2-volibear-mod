import struct, sys, json
from collections import defaultdict

class PE:
    def __init__(self, path):
        self.d = open(path,'rb').read()
        d=self.d
        e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
        assert d[e_lfanew:e_lfanew+4]==b'PE\0\0'
        coff = e_lfanew+4
        self.nsec = struct.unpack_from('<H', d, coff+2)[0]
        optsz = struct.unpack_from('<H', d, coff+16)[0]
        opt = coff+20
        magic = struct.unpack_from('<H', d, opt)[0]
        self.pe32plus = (magic==0x20b)
        # data directories
        if self.pe32plus:
            dd = opt+112
        else:
            dd = opt+96
        self.dd = [struct.unpack_from('<II', d, dd+8*i) for i in range(16)]
        sec = opt+optsz
        self.sections=[]
        for i in range(self.nsec):
            o=sec+40*i
            name=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsize,vaddr,rawsize,rawptr = struct.unpack_from('<IIII', d, o+8)
            self.sections.append((name,vaddr,vsize,rawptr,rawsize))
    def off(self, rva):
        for name,va,vs,rp,rs in self.sections:
            if va<=rva<va+max(vs,rs):
                return rp+(rva-va)
        raise ValueError('rva %x not found'%rva)

class MD:
    def __init__(self, path):
        self.pe=PE(path); d=self.pe.d
        # COM descriptor
        cor_rva, cor_sz = self.pe.dd[14]
        cor = self.pe.off(cor_rva)
        md_rva, md_sz = struct.unpack_from('<II', d, cor+8)
        md = self.pe.off(md_rva)
        assert d[md:md+4]==b'BSJB', d[md:md+4]
        ver_len = struct.unpack_from('<I', d, md+12)[0]
        p = md+16+ver_len
        p += 2  # flags
        nstreams = struct.unpack_from('<H', d, p)[0]; p+=2
        self.streams={}
        for i in range(nstreams):
            off,size = struct.unpack_from('<II', d, p); p+=8
            name=b''
            while d[p]!=0:
                name+=bytes([d[p]]); p+=1
            p+=1
            p = (p+3)&~3
            self.streams[name.decode()]=(md+off, size)
        assert '#~' in self.streams
        t, _tsize = self.streams['#~']
        self.tables_off = t
        heap_sizes = d[t+6]
        self.str_idx = 4 if heap_sizes&1 else 2
        self.guid_idx = 4 if heap_sizes&2 else 2
        self.blob_idx = 4 if heap_sizes&4 else 2
        valid = struct.unpack_from('<Q', d, t+8)[0]
        self.valid=[i for i in range(64) if valid>>i &1]
        # row counts
        p2 = t+24
        self.rows={}
        for i in self.valid:
            self.rows[i]=struct.unpack_from('<I', d, p2)[0]; p2+=4
        self.tables_start = p2
        self.tab={}
        self.rowstart={}
        off=p2
        for i in self.valid:
            self.rowstart[i]=off
            off += self.rows[i]*self.rowsize(i)
        self.tables_size_end = off
        # heaps
        self.strs = self.streams.get('#Strings',(0,0))[0]
        self.blobs = self.streams.get('#Blob',(0,0))[0]
        self.us = self.streams.get('#US',(0,0))[0]
        self.guid = self.streams.get('#GUID',(0,0))[0]
        self.blobsize = self.streams.get('#Blob',(0,0))[1]
        self.strsize = self.streams.get('#Strings',(0,0))[1]
    # --- primitives
    def u8(self,o): return self.pe.d[o]
    def u16(self,o): return struct.unpack_from('<H', self.pe.d, o)[0]
    def u32(self,o): return struct.unpack_from('<I', self.pe.d, o)[0]
    def string(self, idx):
        if idx==0: return ''
        o=self.strs+idx; d=self.pe.d
        e=d.index(b'\0', o)
        return d[o:e].decode('utf-8','replace')
    def blob(self, idx):
        d=self.pe.d; o=self.blobs+idx
        b0=d[o]
        if b0&0x80==0: ln=b0; o+=1
        elif b0&0xC0==0x80: ln=((b0&0x3f)<<8)|d[o+1]; o+=2
        else: ln=((b0&0x1f)<<24)|(d[o+1]<<16)|(d[o+2]<<8)|d[o+3]; o+=4
        return d[o:o+ln]
    # --- coded index widths
    def _cw(self, tables):
        mx=0
        for t in tables:
            r=self.rows.get(t,0)
            if r>mx: mx=r
        bits = {1:0,2:1,3:2,4:3,5:4}.get(len(tables))
        # compute needed bits
        n=len(tables)-1
        bits=0
        while (1<<bits) < max(n,1): bits+=1
        # bits = ceil(log2(len(tables)))
        bits=0
        while (1<<bits) < len(tables): bits+=1
        return 4 if mx >= (1<<(16-bits)) else 2
    def idxw(self, table): return 4 if self.rows.get(table,0)>=65536 else 2
    def codedw(self, tag, tables):
        mx=max(self.rows.get(t,0) for t in tables)
        bits=0
        while (1<<bits) < len(tables): bits+=1
        return 4 if mx >= (1<<(16-bits)) else 2
    # table schemas: list of ('u1'|'u2'|'u4'|'str'|'guid'|'blob'|('tbl',n)|('coded',name))
    CODED = {
      'TypeDefOrRef': [0x02,0x01,0x1B],
      'HasConstant': [0x04,0x08,0x17],
      'HasCustomAttribute': [0x06,0x04,0x01,0x02,0x08,0x09,0x0A,0x00,0x0E,0x17,0x14,0x11,0x1A,0x1B,0x20,0x23,0x26,0x27,0x28,0x2A,0x2B,0x2C],
      'HasFieldMarshal': [0x04,0x08],
      'HasDeclSecurity': [0x02,0x06,0x20],
      'MemberRefParent': [0x02,0x01,0x1A,0x06,0x1B],
      'HasSemantics': [0x14,0x17],
      'MethodDefOrRef': [0x06,0x0A],
      'MemberForwarded': [0x04,0x06],
      'Implementation': [0x26,0x23,0x27],
      'CustomAttributeType': [0x06,0x0A],
      'ResolutionScope': [0x00,0x1A,0x23,0x01],
      'TypeOrMethodDef': [0x02,0x06],
    }
    SCHEMA = {
      0x00:[('u2',),('str',),('guid',),('guid',),('guid',)],
      0x01:[('coded','ResolutionScope'),('str',),('str',)],
      0x02:[('u4',),('str',),('str',),('coded','TypeDefOrRef'),('tbl',0x04),('tbl',0x06)],
      0x03:[('tbl',0x04)],
      0x04:[('u2',),('str',),('blob',)],
      0x05:[('tbl',0x06)],
      0x06:[('u4',),('u2',),('u2',),('str',),('blob',),('tbl',0x08)],
      0x07:[('tbl',0x08)],
      0x08:[('u2',),('u2',),('str',)],
      0x09:[('tbl',0x02),('coded','TypeDefOrRef')],
      0x0A:[('coded','MemberRefParent'),('str',),('blob',)],
      0x0B:[('u2',),('coded','HasConstant'),('blob',)],
      0x0C:[('coded','HasCustomAttribute'),('coded','CustomAttributeType'),('blob',)],
      0x0D:[('coded','HasFieldMarshal'),('blob',)],
      0x0E:[('u2',),('coded','HasDeclSecurity'),('blob',)],
      0x0F:[('u2',),('u4',),('tbl',0x02)],
      0x10:[('u4',),('tbl',0x04)],
      0x11:[('blob',)],
      0x12:[('tbl',0x02),('tbl',0x14)],
      0x13:[('tbl',0x14)],
      0x14:[('u2',),('str',),('coded','TypeDefOrRef')],
      0x15:[('tbl',0x02),('tbl',0x17)],
      0x16:[('tbl',0x17)],
      0x17:[('u2',),('str',),('blob',)],
      0x18:[('u2',),('tbl',0x06),('coded','HasSemantics')],
      0x19:[('tbl',0x02),('coded','MethodDefOrRef'),('coded','MethodDefOrRef')],
      0x1A:[('str',)],
      0x1B:[('blob',)],
      0x1C:[('u2',),('coded','MemberForwarded'),('str',),('tbl',0x1A)],
      0x1D:[('u4',),('tbl',0x04)],
      0x1E:[('u4',),('u4',)],
      0x1F:[('u4',),('u4',)],
      0x20:[('u4',),('u2',),('u2',),('u2',),('u2',),('u4',),('blob',),('str',),('str',)],
      0x21:[('u4',),('u4',)],
      0x22:[('u4',),('u4',),('u4',)],
      0x23:[('u2',),('u2',),('u2',),('u2',),('u4',),('blob',),('str',),('str',),('blob',)],
      0x24:[('u4',),('tbl',0x23)],
      0x25:[('u4',),('u4',),('u4',),('tbl',0x23)],
      0x26:[('u4',),('str',),('blob',)],
      0x27:[('u4',),('u4',),('str',),('str',),('coded','Implementation')],
      0x28:[('u4',),('u4',),('str',),('coded','Implementation')],
      0x29:[('tbl',0x02),('tbl',0x02)],
      0x2A:[('u2',),('u2',),('coded','TypeOrMethodDef'),('str',)],
      0x2B:[('coded','MethodDefOrRef'),('blob',)],
      0x2C:[('tbl',0x02),('tbl',0x2A)],
    }
    def colw(self, c):
        if c[0]=='u1': return 1
        if c[0]=='u2': return 2
        if c[0]=='u4': return 4
        if c[0]=='str': return self.str_idx
        if c[0]=='guid': return self.guid_idx
        if c[0]=='blob': return self.blob_idx
        if c[0]=='tbl': return self.idxw(c[1])
        if c[0]=='coded': return self.codedw(c[1], self.CODED[c[1]])
        raise ValueError(c)
    def rowsize(self, t):
        return sum(self.colw(c) for c in self.SCHEMA[t])
    def row(self, t, i):
        """1-based row i -> tuple of raw values"""
        if t not in self.rows: raise KeyError(t)
        off=self.rowstart[t]+(i-1)*self.rowsize(t)
        vals=[]
        for c in self.SCHEMA[t]:
            w=self.colw(c)
            if w==1: v=self.u8(off)
            elif w==2: v=self.u16(off)
            else: v=self.u32(off)
            vals.append(v); off+=w
        return vals
    def decode_coded(self, name, v):
        tables=self.CODED[name]
        bits=0
        while (1<<bits)<len(tables): bits+=1
        tag = v & ((1<<bits)-1)
        return (tables[tag], v>>bits)
    # --- high level
    def typedef_name(self, i):
        r=self.row(0x02,i) if True else None
        return (self.string(r[2]), self.string(r[1]))
    def typeref_name(self, i):
        r=self.row(0x01,i)
        return (self.string(r[2]), self.string(r[1]))
    def type_name_of(self, coded_table, idx):
        if coded_table==0x02: return self.typedef_name(idx)
        if coded_table==0x01: return self.typeref_name(idx)
        if coded_table==0x1B: return ('<typespec>','')
        return ('?','?')
    def resolve_memberref(self, i):
        r=self.row(0x0A,i)
        tbl,idx=self.decode_coded('MemberRefParent', r[0])
        return self.type_name_of(tbl,idx)+(self.string(r[1]),)
    def resolve_customattr_type(self, i):
        r=self.row(0x0C,i)
        tbl,idx=self.decode_coded('CustomAttributeType', r[1])
        if tbl==0x0A:
            t=self.resolve_memberref(idx)
            return t[1]  # type name
        elif tbl==0x06:
            # methoddef: find owning type
            owner=self.owner_of_method(idx)
            return owner[1] if owner else '?'
        return '?'
    def owner_of_method(self, i):
        # build map lazily
        if not hasattr(self,'_mowner'):
            self._mowner={}
            for ti in range(1, self.rows.get(0x02,0)+1):
                r=self.row(0x02,ti)
                start=r[5]; nxt=self.row(0x02,ti+1)[5] if ti<self.rows[0x02] else self.rows.get(0x06,0)+1
                for m in range(start, nxt): self._mowner[m]=self.typedef_name(ti)
        return self._mowner.get(i)
    def owner_of_field(self, i):
        if not hasattr(self,'_fowner'):
            self._fowner={}
            for ti in range(1, self.rows.get(0x02,0)+1):
                r=self.row(0x02,ti)
                start=r[4]; nxt=self.row(0x02,ti+1)[4] if ti<self.rows[0x02] else self.rows.get(0x04,0)+1
                for f in range(start,nxt): self._fowner[f]=self.typedef_name(ti)
        return self._fowner.get(i)

# Element type decoder
ET = {0x01:'void',0x02:'bool',0x03:'char',0x04:'int8',0x05:'uint8',0x06:'int16',0x07:'uint16',0x08:'int32',0x09:'uint32',0x0a:'int64',0x0b:'uint64',0x0c:'float32',0x0d:'float64',0x0e:'string',0x18:'IntPtr',0x19:'UIntPtr',0x1c:'object'}
class Sig:
    def __init__(self, md): self.md=md
    def type_of(self, b, i):
        et=b[i]; i+=1
        if et in ET: return ET[et], i
        if et==0x0f:  # ptr
            t,i=self.type_of(b,i); return t+'*', i
        if et==0x10:  # byref
            t,i=self.type_of(b,i); return 'ref '+t, i
        if et==0x11 or et==0x12: # valuetype / class
            cv,i=self.comp2(b,i)
            tbl,idx=self.md.decode_coded('TypeDefOrRef', cv)
            ns,nm=self.md.type_name_of(tbl,idx)
            return (f'{ns}.{nm}' if ns else nm), i
        if et==0x13: # var
            return '!'+str(b[i]), i+1
        if et==0x1e:
            return '!'+str(b[i]), i+1
        if et==0x1d: # szarray
            t,i=self.type_of(b,i); return t+'[]', i
        if et==0x14: # array
            t,i=self.type_of(b,i)
            rank=b[i]; i+=1
            n=b[i]; i+=1
            for _ in range(n):
                i+=2
            n=b[i]; i+=1
            for _ in range(n):
                i+=2
            return f'{t}[{rank}]', i
        if et==0x15: # genericinst
            kind=b[i]; i+=1
            cv,i=self.comp2(b,i)
            tbl,idx=self.md.decode_coded('TypeDefOrRef', cv)
            ns,nm=self.md.type_name_of(tbl,idx)
            n,i=self.comp2(b,i)
            args=[]
            for _ in range(n):
                t,i=self.type_of(b,i); args.append(t)
            return (f'{ns}.{nm}' if ns else nm)+'<'+','.join(args)+'>', i
        if et==0x1b: # fnptr
            i=self.methodsig(b,i)[2]; return 'fnptr', i
        if et==0x45: # pinned
            return self.type_of(b,i)
        return f'?et{et}', i
    def comp(self, blob):
        # compressed unsigned
        b0=blob[0]
        if b0&0x80==0: return b0
        if b0&0xC0==0x80: return ((b0&0x3f)<<8)|blob[1]
        return ((b0&0x1f)<<24)|(blob[1]<<16)|(blob[2]<<8)|blob[3]
    def comp2(self, b, i):
        v=self.comp(b[i:i+5])
        b0=b[i]
        n = 1 if b0&0x80==0 else (2 if b0&0xC0==0x80 else 4)
        return v, i+n
    def methodsig(self, b, i=0):
        flags=b[i]; i+=1
        genc=0
        if flags&0x10:
            genc,i=self.comp2(b,i)
        n=b[i]; i+=1
        ret,i=self.type_of(b,i)
        params=[]
        for _ in range(n):
            t,i=self.type_of(b,i); params.append(t)
        return ret, params, i
    def fieldsig(self, b):
        flags=b[0]
        t,i=self.type_of(b,1)
        return t, flags
    def propsig(self, b):
        flags=b[0]
        n=b[1]
        t,i=self.type_of(b,2)
        params=[]
        for _ in range(n):
            p,i=self.type_of(b,i); params.append(p)
        return t, params, flags

def load(path):
    md=MD(path)
    return md, Sig(md)
