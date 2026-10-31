#!/usr/bin/env python3
"""Deterministic CC0 creature recordings + original procedural battle sound design.

No speech synthesis, official Riot recording, or performer imitation is used.
Run from any directory. Requires numpy, scipy, ffmpeg and the bundled source files.
"""
from pathlib import Path
import hashlib, json, math, subprocess, wave, zipfile
import numpy as np
from scipy import signal

ROOT=Path(__file__).resolve().parents[1]
SR=48000
RNG=np.random.default_rng(5172026)
CACHE={}
RECORDS=[]
CUEDATA=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def decode(p):
    p=Path(p)
    if str(p) not in CACHE:
        b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ac','1','-ar',str(SR),'pipe:1'])
        CACHE[str(p)]=np.frombuffer(b,np.float32).astype(np.float64)
    return CACHE[str(p)].copy()
def filt(x,lo=40,hi=6000):
    return signal.sosfilt(signal.butter(3,[lo,hi],btype='bandpass',fs=SR,output='sos'),x)
def fade(x,attack=.006,release=.07):
    x=x.copy();a=min(int(attack*SR),len(x)//3);r=min(int(release*SR),len(x)//3)
    if a:x[:a]*=np.sin(np.linspace(0,np.pi/2,a))**2
    if r:x[-r:]*=np.cos(np.linspace(0,np.pi/2,r))**2
    x[0]=x[-1]=0
    return x
def norm(x):
    return x/max(float(np.max(np.abs(x))),1e-9)
def noise(seconds,lo=60,hi=5500):return norm(filt(RNG.normal(0,1,round(seconds*SR)),lo,hi))
def mix(*tracks):
    # each track=(sample, gain, start_seconds)
    n=max(round(start*SR)+len(x) for x,g,start in tracks);out=np.zeros(n)
    for x,g,start in tracks:
        j=round(start*SR);out[j:j+len(x)]+=x*g
    return out
def tone(seconds,f0=100,f1=45,decay=7):
    t=np.arange(round(seconds*SR))/SR
    return np.sin(2*np.pi*(f0*t+(f1-f0)*t*t/(2*seconds)))*np.exp(-decay*t)
def sweep(seconds=.30,reverse=False):
    t=np.arange(round(seconds*SR))/SR;n=noise(seconds,250,6500)
    env=np.sin(np.pi*np.clip(t/seconds,0,1))**1.4
    out=n*env*(.55+.45*np.cos(2*np.pi*(90*t+900*t*t)))
    return fade(out[::-1] if reverse else out)
def impact(name='impactPunch_heavy_000.ogg'):
    return fade(filt(decode(ROOT/'source/kenney'/name),35,6500),.002,.04)
def spark(seconds=.24):
    t=np.arange(round(seconds*SR))/SR
    return fade(noise(seconds,1100,10000)*np.exp(-22*t)+.22*np.sin(2*np.pi*(1600*t-900*t*t))*np.exp(-35*t),.001,.035)
def thunder(seconds=1.12,weight=1):
    t=np.arange(round(seconds*SR))/SR
    rum=noise(seconds,35,380)*np.exp(-3.8*t)
    return fade(mix((spark(.19),.50,0),(rum,.8*weight,0),(tone(seconds,105,35,6),.36,0)),.002,.13)
def chime(seconds=.55,down=False):
    t=np.arange(round(seconds*SR))/SR;out=np.zeros(len(t))
    for i,hz in enumerate(([720,540,360] if down else [360,540,720])):
        tau=np.maximum(0,t-i*.06);out+=(t>=i*.06)*np.sin(2*np.pi*hz*tau)*np.exp(-9*tau)*(.4/(i+1))
    return fade(out,.003,.10)
def pulse(seconds=.65):
    t=np.arange(round(seconds*SR))/SR
    return fade(noise(seconds,80,1600)*np.sin(np.pi*t/seconds)**2*.45+tone(seconds,220,70,4)*.6,.01,.12)
def periodic_rumble(seconds=4,bright=False):
    # An exactly periodic bandlimited signal. No appended/repeated endpoint frame.
    n=round(seconds*SR);freq=np.fft.rfftfreq(n,1/SR)
    z=RNG.normal(size=len(freq))+1j*RNG.normal(size=len(freq))
    band=np.exp(-((freq-(250 if bright else 110))/(150 if bright else 75))**2)
    z*=band;z[0]=0;z[-1]=0
    x=np.fft.irfft(z,n);t=np.arange(n)/SR
    x=norm(x)*(.7+.3*np.sin(2*np.pi*t/seconds)**2)
    return x
def creature(filename,start,end,pitch=.92):
    x=decode(ROOT/'source'/filename)[round(start*SR):round(end*SR)]
    x=signal.resample_poly(x,100,round(pitch*100))
    x=filt(x,48,4600)
    x=np.tanh(x*.9)
    return fade(x,.018,.12)
def write_wav(p,x):
    with wave.open(str(p),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR)
        w.writeframes(np.round(np.clip(x,-.9999,.9999)*32767).astype('<i2').tobytes())
def loudness(p):
    r=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af','loudnorm=I=-18:TP=-2:LRA=9:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    s=r.stderr;return json.loads(s[s.rfind('{'):s.rfind('}')+1])
def emit(name,x,label,origin,loop=False,target=-19):
    x=x-np.mean(x)
    if not loop:x=fade(x,.004,.055)
    x=norm(x)*.70
    wav=ROOT/'wav'/f'{name}.wav';ogg=ROOT/'ogg'/f'{name}.ogg'
    write_wav(wav,x);lm=loudness(wav);level=float(lm['input_i']);tp=float(lm['input_tp'])
    gain=min(target-level,-2.5-tp) if math.isfinite(level) else -3
    x*=10**(gain/20);write_wav(wav,x)
    subprocess.run(['ffmpeg','-v','error','-i',str(wav),'-c:a','libvorbis','-q:a','5','-metadata','comment=Volibear V5 asset; CC0 recordings and original procedural sound design','-y',str(ogg)],check=True)
    ow=decode(ogg);final=loudness(ogg)
    li=float(final['input_i'])
    rec={'id':name,'label_zh':label,'wav':str(wav.relative_to(ROOT)),'file':str(ogg.relative_to(ROOT)),'sample_rate':SR,'channels':1,'pcm_bits':16,'duration_seconds':round(len(x)/SR,6),'loop':loop,'source':origin,'wav_sha256':sha(wav),'ogg_sha256':sha(ogg),'integrated_lufs':li if math.isfinite(li) else None,'loudness_note':'EBU gated integrated value' if math.isfinite(li) else 'Below the 400 ms integrated-loudness window; peak/RMS checks apply','rms_dbfs':round(20*math.log10(max(float(np.sqrt(np.mean(ow*ow))),1e-12)),3),'true_peak_dbtp':float(final['input_tp']),'peak_sample':round(float(np.max(np.abs(ow))),7),'dc_offset':round(float(np.mean(ow)),9),'nonzero_samples':int(np.sum(np.abs(ow)>1e-6))}
    if loop:
        slope=np.abs(np.diff(ow));rec['loop_boundary_step']=float(abs(ow[-1]-ow[0]));rec['loop_step_p999']=float(np.quantile(slope,.999));rec['loop_samples']=len(x)
    RECORDS.append(rec);print(name,rec['duration_seconds'],rec['integrated_lufs'],rec['true_peak_dbtp'],flush=True)
    return rec
def main():
    for p in ['wav','ogg','reports','previews']: (ROOT/p).mkdir(exist_ok=True)
    # Derive only the selected files, preserving the original licence and archive.
    raw=ROOT/'source/kenney';raw.mkdir(exist_ok=True)
    used=['impactPunch_heavy_000.ogg','impactPunch_medium_001.ogg','impactMetal_heavy_000.ogg','impactWood_heavy_000.ogg','impactGeneric_light_000.ogg','impactGlass_light_001.ogg','footstep_snow_000.ogg']
    with zipfile.ZipFile(ROOT/'source/kenney_impact-sounds.zip') as z:
        for n in used:(raw/n).write_bytes(z.read('Audio/'+n))
        (raw/'License.txt').write_bytes(z.read('License.txt'))
    punch=impact();metal=impact('impactMetal_heavy_000.ogg');wood=impact('impactWood_heavy_000.ogg')
    light=impact('impactGeneric_light_000.ogg');glass=impact('impactGlass_light_001.ogg')
    definitions=[
      ('claw_slash',mix((sweep(.29),.70,0),(punch,.38,.14)),'爪击：挥动与接触','Kenney CC0 impactPunch_heavy_000 + procedural filtered sweep'),
      ('heavy_impact',mix((wood,.7,0),(punch,.6,.018),(tone(.8,80,28,5),.6,0)),'重击：低频冲击','Kenney CC0 wood/punch + original sub impact'),
      ('bite_hit',mix((punch,.65,0),(glass,.20,.02),(tone(.35,150,65,14),.20,0)),'咬击：短促咬合','Kenney CC0 punch/glass + original transient'),
      ('guard_gain',mix((sweep(.3,True),.5,0),(chime(.55),.3,.08)),'格挡建立','original procedural sound design'),
      ('guard_hit',mix((metal,.55,0),(tone(.42,130,60,12),.45,0)),'格挡接触','Kenney CC0 impactMetal_heavy_000 + original low body'),
      ('guard_break',mix((metal,.45,0),(glass,.6,.08),(sweep(.30),.3,.04)),'护盾破裂','Kenney CC0 metal/glass + original air'),
      ('counter_release',mix((sweep(.22),.65,0),(thunder(.75),.6,.10)),'反击释放','original procedural sound design'),
      ('absorb',mix((sweep(.45,True),.6,0),(pulse(.65),.55,.05)),'吸收收束','original procedural sound design'),
      ('lightning_strike',thunder(1.1),'单次雷击','original procedural filtered-noise / sub / transient design'),
      ('lightning_chain',mix((spark(.28),.7,0),(spark(.25),.6,.13),(spark(.22),.5,.27),(thunder(.6,.5),.30,.30)),'链雷','original procedural sound design'),
      ('lightning_all',mix((thunder(1.45,1.2),.8,0),(spark(.35),.25,.09)),'群体雷落','original procedural sound design'),
      ('lightning_growth',mix((chime(.42),.30,0),(spark(.18),.16,.03)),'雷电成长','original procedural sound design'),
      ('domain_enter',mix((sweep(.65,True),.6,0),(thunder(1.4,1.2),.65,.42),(chime(.8),.20,.45)),'领域展开','original procedural sound design'),
      ('domain_exit',mix((pulse(.8)[::-1],.45,0),(chime(.65,True),.35,.16)),'领域消散','original procedural sound design'),
      ('domain_suppress',mix((pulse(.50),.55,0),(spark(.12),.12,.04)),'领域压制','original procedural sound design'),
      ('card_purify',mix((sweep(.4),.4,0),(chime(.65),.6,.05)),'卡牌净化','original procedural sound design'),
      ('feral_transfer',mix((sweep(.52),.6,0),(spark(.18),.25,.30),(pulse(.35),.3,.35)),'兽化侵染：流向目标再附着','original procedural directional sweep and contact'),
      ('feral_claw',mix((sweep(.22),.60,0),(punch,.42,.10),(spark(.13),.18,.12)),'爪形转换/触发','Kenney CC0 punch + original sweep'),
      ('feral_body',mix((pulse(.7),.6,0),(metal,.25,.26)),'躯形转换/触发','Kenney CC0 metal + original body pulse'),
      ('mark_bite',mix((light,.35,0),(tone(.28,210,70,12),.30,0)),'咬痕印记','Kenney CC0 generic impact + original stamp'),
      ('charge',mix((sweep(.7,True),.45,0),(chime(.8),.30,.2)),'蓄势/充能','original procedural sound design'),
      ('card_draw',sweep(.23),'抽牌','original procedural paper-like filtered air'),
      ('card_retrieve',mix((sweep(.28,True),.50,0),(chime(.35),.22,.08)),'检索/回收','original procedural sound design'),
      ('card_discard',sweep(.3),'弃牌','original procedural paper-like filtered air'),
      ('card_exhaust',mix((noise(.55,300,6000)*np.exp(-np.arange(round(.55*SR))/SR*7),.50,0),(chime(.40,True),.20,0)),'消耗','original procedural sound design'),
      ('energy_gain',chime(.58),'能量获得','original procedural harmonic chime'),
      ('card_replay',mix((sweep(.27,True),.4,0),(chime(.45),.25,.10),(spark(.12),.13,.21)),'重演','original procedural sound design'),
      ('lifesteal',mix((sweep(.65,True),.40,0),(chime(.45),.3,.33)),'汲取回流','original procedural sound design'),
      ('heal',chime(.8),'恢复','original procedural harmonic chime'),
      ('roar_wave',mix((pulse(.9),.5,0),(sweep(.40),.35,.12)),'吼声冲击波底层','original procedural sound design'),
      ('cast_charge',mix((sweep(.8,True),.42,0),(spark(.28),.2,.38),(chime(.60),.24,.19)),'施法前摇','original procedural sound design'),
      ('footstep',impact('footstep_snow_000.ogg'),'落地/脚步','Kenney CC0 footstep_snow_000'),
    ]
    for name,x,label,origin in definitions:emit(name,x,label,origin,target=-23 if name.startswith('card_') or name in ['lightning_growth','energy_gain','mark_bite','heal'] else -19)
    emit('domain_loop',periodic_rumble(4),'领域持续低鸣','original periodic spectral synthesis',True,-29)
    emit('feral_aura',periodic_rumble(4,True),'兽化持续气息','original periodic spectral synthesis',True,-32)
    voice_defs=[
      ('select','monster-snarls.ogg',.16,1.40,.94,'选择/进入战斗低吼'),
      ('attack_01','monster-snarl-attack.ogg',.10,.63,.92,'攻击短吼 A'),
      ('attack_02','monster-snarl-attack.ogg',1.68,2.40,.94,'攻击短吼 B'),
      ('heavy','monster-snarl-5.ogg',.30,1.40,.90,'重击发力'),
      ('bite','monster-snarl-attack.ogg',3.38,3.92,.90,'撕咬发力'),
      ('cast','monster-snarls-2.ogg',2.74,3.45,.94,'施法低吟'),
      ('hurt_01','monsters-snarls-3.ogg',.60,1.23,1.02,'受击短声 A'),
      ('hurt_02','monster-snarl-5.ogg',8.92,9.55,1.03,'受击短声 B'),
      ('low_health','monster-snarls-2.ogg',4.94,5.65,.86,'低血喘息：进入状态一次'),
      ('roar','monster_roar.wav',.16,2.05,1.0,'战斗咆哮'),
      ('feral','monster-snarl-5.ogg',4.04,5.65,.90,'兽化咆哮'),
      ('death','monster-snarls.ogg',.18,2.25,.84,'倒下低吼'),
      ('victory','monster_roar.wav',.18,1.35,.96,'胜利短吼'),
    ]
    for name,f,a,b,pitch,label in voice_defs:
        emit('voice_'+name,creature(f,a,b,pitch),label,{'recording':f,'source_interval_seconds':[a,b],'rate_ratio':pitch,'processing':'mono 48k, bandpass 48-4600 Hz, soft saturation, endpoint fades, loudness/peak controlled'},target=-22 if name=='low_health' else -19)
    effect_ids='claw_slash heavy_impact bite_hit guard_gain guard_hit guard_break counter_release absorb lightning_strike lightning_chain lightning_all lightning_growth domain_enter domain_loop domain_exit domain_suppress card_purify feral_transfer feral_claw feral_body feral_aura mark_bite wound weakness charge strength armor_retain armor_iron card_draw card_retrieve card_discard card_exhaust energy_gain cost_reduce card_replay lifesteal heal roar_wave thunder_armor cast_charge'.split()
    aliases={'wound':'mark_bite','weakness':'domain_suppress','strength':'charge','armor_retain':'guard_gain','armor_iron':'guard_hit','cost_reduce':'energy_gain','thunder_armor':'lightning_growth'}
    byid={r['id']:r for r in RECORDS}
    for eid in effect_ids:
        rec=byid[aliases.get(eid,eid)]
        CUEDATA.append({'id':'sfx.'+eid,'asset_id':rec['id'],'file':rec['file'],'wav':rec['wav'],'duration_seconds':rec['duration_seconds'],'loop':rec['loop'],'bus':'Ambience' if rec['loop'] else 'Sfx','gain_db':0,'cooldown_ms':250 if eid in ['lightning_growth','domain_suppress','card_draw'] else 60,'max_voices':1 if rec['loop'] else 4,'trigger_policy':'start_once_on_state_enter_stop_on_exit_death_room_cleanup' if rec['loop'] else 'once_per_successful_semantic_event; never per_render_frame','default_enabled':eid!='feral_aura'})
    for name,*_ in voice_defs:
        rec=byid['voice_'+name]
        CUEDATA.append({'id':'voice.'+name,'asset_id':rec['id'],'file':rec['file'],'wav':rec['wav'],'duration_seconds':rec['duration_seconds'],'loop':False,'bus':'Voice','gain_db':0,'cooldown_ms':1800 if name=='low_health' else 200,'max_voices':1,'trigger_policy':'semantic_action_start; deterministic cosmetic selection, not gameplay RNG','default_enabled':True})
    CUEDATA.append({'id':'sfx.footstep','asset_id':'footstep',**{k:byid['footstep'][k] for k in ['file','wav','duration_seconds','loop']},'bus':'Sfx','gain_db':-3,'cooldown_ms':90,'max_voices':2,'default_enabled':True})
    manifest={'schema_version':1,'sample_rate':SR,'channels':1,'runtime_format':'Ogg Vorbis q5; editable PCM16 WAV masters','official_character_voice':False,'spoken_dialogue':False,'cue_count':len(CUEDATA),'unique_asset_count':len(RECORDS),'cues':CUEDATA,'assets':RECORDS,'mix_rules':{'voice_bus':-3,'sfx_bus':-3,'ambience_bus':-6,'headroom_db':6,'master_soft_limit_dbtp':-1,'mute_voice_available':True,'loop_fade_out_ms':140,'scope':'combat/room owner; stop all owned handles on death and scene release','randomness':'separate cosmetic deterministic counter; never consume game RNG'}}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'manifest.js').write_text('window.VOLIBEAR_AUDIO='+json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+';\n')
    make_action_cues()
    overview=np.concatenate([np.concatenate([decode(ROOT/r['file']),np.zeros(round(.18*SR))]) for r in RECORDS])
    write_wav(ROOT/'previews/audio_overview.wav',overview)
    subprocess.run(['ffmpeg','-v','error','-i',str(ROOT/'previews/audio_overview.wav'),'-c:a','libvorbis','-q:a','4','-y',str(ROOT/'previews/audio_overview.ogg')],check=True)
    segments=[];pos=0
    for r in RECORDS:
        segments.append({'asset':r['id'],'start_seconds':round(pos,4),'end_seconds':round(pos+r['duration_seconds'],4)});pos+=r['duration_seconds']+.18
    (ROOT/'previews/audio_overview.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2)+'\n')
    print('BUILT',len(RECORDS),'assets',len(CUEDATA),'cues',flush=True)

def make_action_cues():
    motions=json.loads((ROOT.parent/'animations/rig/motions.json').read_text());items=[]
    cdefs=motions['clips']+[dict(next(c for c in motions['clips'] if c['name']==v['base_clip']),**v) for v in motions['variants']]
    for clip in cdefs:
        name=clip['name'];base=name.removeprefix('domain_');entries=[]
        def add(t,cue,reason):entries.append({'time_seconds':round(t,6),'cue':cue,'reason':reason})
        voice={'attack':'attack_01','attack_heavy':'heavy','bite':'bite','cast':'cast','hurt':'hurt_01','roar':'roar','feral_enter':'feral','die':'death','storm_leap':'heavy'}.get(base) or {'domain_enter':'roar'}.get(name)
        if voice:add(.08 if base!='roar' else .36,'voice.'+voice,'action-start cosmetic cue')
        for e in clip['events']:
            typ=e['event'];mapping={'hurt_recoil':'heavy_impact','guard_on':'guard_gain','blocked_impact':'guard_hit','absorbed_impact':'absorb','counter_impact':'counter_release','cast_release':'lightning_strike','domain_on':'domain_enter','domain_off':'domain_exit','feral_on':'feral_transfer','body_ground_impact':'heavy_impact','takeoff':'cast_charge','landing_impact':'heavy_impact','aftershock':'lightning_all','roar_release':'roar_wave'}
            if typ=='impact':eid='bite_hit' if base=='bite' else 'heavy_impact' if base=='attack_heavy' else 'claw_slash'
            else:eid=mapping.get(typ)
            if eid:add(e['time'],'sfx.'+eid,typ)
        state={'domain_idle':['sfx.domain_loop'],'feral_idle':[],'weak_loop':['voice.low_health'],'domain_weak_loop':['voice.low_health','sfx.domain_loop']}.get(name,[])
        items.append({'clip':name,'events':sorted(entries,key=lambda e:e['time_seconds']),'state_entry_only':state,'replay_loop_behavior':'Never replay entry-only voice or start another loop on cycle wrap.','cancel_policy':'Cancel future scheduled cues on interrupted animation; stop state loops on state exit/death/room cleanup.'})
    (ROOT/'action_cues.json').write_text(json.dumps({'schema_version':1,'animation_motion_sha256':sha(ROOT.parent/'animations/rig/motions.json'),'purpose':'offline timing preview and adapter example; actual damage/VFX use resolved game events','clips':items},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
