#!/usr/bin/env python3
"""Decode every runtime file and verify cue, timing, peak and loop contracts."""
from pathlib import Path
import json,hashlib,subprocess,wave,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    data=json.loads((ROOT/'manifest.json').read_text(),parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    errors=[];checks=[]
    for a in data['assets']:
        wav=ROOT/a['wav'];ogg=ROOT/a['file']
        assert sha(wav)==a['wav_sha256'];assert sha(ogg)==a['ogg_sha256']
        with wave.open(str(wav),'rb') as w:
            spec=(w.getframerate(),w.getnchannels(),w.getsampwidth());n=w.getnframes();pcm=np.frombuffer(w.readframes(n),'<i2')/32768.
        assert spec==(48000,1,2),(a['id'],spec)
        assert abs(n/48000-a['duration_seconds'])<2/48000
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ogg),'-f','f32le','-ac','1','-ar','48000','pipe:1'])
        x=np.frombuffer(raw,np.float32).astype(float)
        assert np.isfinite(x).all() and len(x)>4000
        meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(ogg)]))
        assert abs(float(meta['format']['duration'])-n/48000)<2/48000
        # Vorbis decoders may expose up to one final codec block of padding.
        # The Ogg granule duration, validated above, is the playback duration.
        assert -256<=len(x)-n<=2048,(a['id'],len(x),n)
        assert np.sqrt(np.mean(x*x))>1e-5 and np.max(np.abs(x))<.89,(a['id'],'silent/clipped')
        assert abs(np.mean(x))<.01,(a['id'],'DC offset')
        assert a['true_peak_dbtp']<=-1.5,(a['id'],'true peak')
        if a['loop']:
            step=abs(x[-1]-x[0]);limit=max(.003,float(np.quantile(np.abs(np.diff(x)),.999))*1.2)
            assert step<=limit,(a['id'],'loop discontinuity',step,limit)
        else:
            assert abs(pcm[0])<1/32768 and abs(pcm[-1])<1/32768
        checks.append({'asset':a['id'],'ogg_decode_pass':True,'samples':len(x),'sample_peak':float(np.max(np.abs(x))),'wav_sha256':a['wav_sha256'],'ogg_sha256':a['ogg_sha256']})
    assets={x['id']:x for x in data['assets']};cues={x['id']:x for x in data['cues']}
    assert len(cues)==len(data['cues'])==54
    for c in cues.values():
        a=assets[c['asset_id']];assert c['file']==a['file'] and c['loop']==a['loop'];assert (ROOT/c['file']).is_file()
    actions=json.loads((ROOT/'action_cues.json').read_text());motions=json.loads((ROOT.parent/'animations/rig/motions.json').read_text());clips={c['name']:c for c in motions['clips']+motions['variants']}
    assert set(x['clip'] for x in actions['clips'])==set(clips)
    for a in actions['clips']:
        for e in a['events']:
            assert e['cue'] in cues
            assert 0<=e['time_seconds']<=clips[a['clip']]['duration']
        for e in a['state_entry_only']:assert e in cues
    source=json.loads((ROOT/'sources.json').read_text())
    for s in source['recordings']:assert sha(ROOT/s['file'])==s['sha256']
    report={'status':'pass','scope':'file decoding, format, silence, waveform endpoints, measured true peak, periodic-loop seam, hashes, cue references and action time ranges; not a human listening review or in-game mix test','unique_audio_assets':len(assets),'cue_count':len(cues),'animation_sequences_mapped':len(actions['clips']),'source_files_checked':len(source['recordings']),'manifest_sha256':sha(ROOT/'manifest.json'),'action_cues_sha256':sha(ROOT/'action_cues.json'),'build_script_sha256':sha(ROOT/'scripts/build_audio.py'),'validator_sha256':sha(__file__),'assets':checks}
    (ROOT/'reports/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='assets'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
