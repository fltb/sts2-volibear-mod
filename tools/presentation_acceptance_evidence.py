"""Bounded G5 capture gate, NOT a human visual/listening or complete G5 verdict.
Standalone logs remain strict; a runner may pass its independently stock-validated view.
"""
from __future__ import annotations
import array
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import wave
import os
EXPECTED_GAME_VERSION = os.environ.get('VOLIBEAR_GAME_VERSION', 'v0.107.1')
EXPECTED_GAME_COMMIT = os.environ.get('VOLIBEAR_GAME_COMMIT', '59260271')

MARKER = "[Volibear] PRESENTATION_ACCEPTANCE_RESULT "
ACCEPTANCE = "native-viewport-paid-actions-game-bus-pcm-not-sensory-or-full-G5"
# Fixed approved 89-definition denominator, independent of producer enumeration.
CODES = set("B01 B02 B03 C01 C02 C03 C08 C09 C12 C13 C20 C22 C24 C26 U05 U06 U07 U13 U15 U20 U23 U24 U27 U31 U36 U38 U40 R05 R07 R12 R17 R21 R23 R24 T01 T02 C05 C14 C17 C18 C21 C25 U02 U03 U04 U10 U11 U12 U14 U19 U21 U25 U26 U29 U32 U34 U37 R01 R02 R06 R13 R14 R16 R18 B04 C04 C06 C10 C11 U08 U28 U35 R31 C07 C15 C19 U39 U41 U42 U43 R10 R25 R27 R28 R29 R30 U17 R08 R09".split())
ACTION_CODES = ("B01", "B02", "B03", "B04", "C03", "C05")
ACTION_PHASES = [f"{w}-{code}" for w in (1280, 1920) for code in ACTION_CODES] + ["beast-convert", "converted-claw", "converted-body"]
PORTRAITS = "res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/"
EFFECTS = set("absorb armor_iron armor_retain bite_hit card_discard card_draw card_exhaust card_purify card_replay card_retrieve cast_charge charge claw_slash cost_reduce counter_release domain_enter domain_exit domain_loop domain_suppress energy_gain feral_aura feral_body feral_claw feral_transfer guard_break guard_gain guard_hit heal heavy_impact lifesteal lightning_all lightning_chain lightning_growth lightning_strike mark_bite roar_wave strength thunder_armor weakness wound".split())


def number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _effective_audio_files(authored, runtime):
    """Resolve only a verified packaged profile, never a producer-selected path.

    The authored manifest is the open inventory even in private builds. The PCK
    runtime overlay must match the locally verified pinned profile preparation.
    No media decoding or playback is inferred from this identity check.
    """
    try:
        from . import audio_profiles
    except ImportError:
        import audio_profiles
    # stage_assets.py removes only authoring WAV paths from runtime cue rows.
    approved = [{k: v for k, v in row.items() if k != 'wav'}
                for row in audio_profiles.read_json(audio_profiles.AUDIO / 'manifest.json')['cues']]
    if authored['cues'] != approved:
        raise ValueError('authored audio cue inventory differs from approved manifest')
    files = {cue['id']: cue['file'] for cue in approved}
    if runtime == {'schema_version': 1, 'profile': 'open', 'overrides': []}:
        return files
    if not isinstance(runtime, dict) or runtime.get('profile') != 'riot_en':
        raise ValueError('unknown/malformed runtime audio profile')
    expected = audio_profiles.verify_prepared(full_decode=False)
    if runtime != expected:
        raise ValueError('runtime audio profile differs from verified pinned preparation')
    for row in expected['overrides']:
        files[row['cue']] = row['file']
    return files


def _source_audio_errors(voices, files):
    errors = []
    for voice in voices:
        if (voice['cue'] not in files or voice['file'] != files.get(voice['cue'])
                or voice['playing'] is not True or not number(voice['volume']) or voice['volume'] <= 0):
            errors.append('actual source cue identity/playback/gain')
    return errors


def _structure(p, token, mode):
    errors=[]
    def need(ok, why):
        if not ok: errors.append(why)
    try:
        need(mode in ("all","cards","actions") and p["mode"]==mode, "exact requested mode")
        need(p["schema"]==1 and type(p["schema"]) is int and p["token"]==token and bool(token), "schema/run token")
        need(p["version"]==EXPECTED_GAME_VERSION and p["commit"]==EXPECTED_GAME_COMMIT, "pinned native version")
        need(p["acceptance"]==ACCEPTANCE, "bounded evidence scope")
        need(p["osInput"] is False and p["syntheticScreenshots"] is False and p["directCosmeticPlayback"] is False, "no OS input/synthetic rendering/direct playback")
        need(type(p["display"]) is str and p["display"] not in ("", "headless"), "real display")
        need(len(p["matrix"])==10 and {r["id"] for r in p["matrix"]}=={f"V{i:02}" for i in range(1,11)}, "V matrix denominator")
        need(all(r["status"] in ("NOTRUN","inventory-only","captured-awaiting-manual-review","partial-evidence-manual-review-required") for r in p["matrix"]), "no self-awarded full G5 pass")
        need(next(r for r in p["matrix"] if r["id"]=="V09")["status"]=="NOTRUN" and len(p["manualReviewRequired"])>=6, "unexecuted normal progression and sensory boundary")
        effects=p["authoredEffects"]["effects"]
        need(len(effects)==40 and {r["id"] for r in effects}==EFFECTS, "fixed 40 effect inventory")
        cues=p["authoredAudio"]["cues"]
        cue_ids={r["id"] for r in cues}
        need(len(cues)==len(cue_ids)==54, "54 distinct authored cues, not 54 heard claims")
        effective_files = _effective_audio_files(p['authoredAudio'], p['audioProfile'])
        if mode in ("cards","all"):
            rows=p["views"]
            need(len(rows)==356 and {(r["code"],r["upgraded"],r["kind"]) for r in rows}=={(c,u,k) for c in CODES for u in (False,True) for k in ("small","large")}, "89 x base/upgrade x hand/Inspect")
            for r in rows:
                need(type(r["upgraded"]) is bool and type(r["level"]) is int and r["level"]==int(r["upgraded"]) and r["viewLevel"]==r["level"], "actual native upgrade level")
                need(r["viewModel"]==r["model"] and (r["sameModel"] is True if r["kind"]=="small" else r["sameModel"] is False), "hand original vs native Inspect clone identity")
                path=PORTRAITS+("big/" if r["kind"]=="large" else "")+r["code"].lower()+".png"
                expected=(1000,760) if r["kind"]=="large" else (250,190)
                portraits=[t for t in r["textures"] if t["resource"]==path and t["visible"] is True]
                need(len(portraits)==1 and (portraits[0]["width"],portraits[0]["height"])==expected, "actual normal-view approved small/big texture and dimensions")
                need(r["bigResource"]["path"]==PORTRAITS+"big/"+r["code"].lower()+".png" and (r["bigResource"]["width"],r["bigResource"]["height"])==(1000,760) and r["bigResource"]["usedByNativeView"] is (r["kind"]=="large"), "big resource must actually be used only by Inspect")
                need(any(x["visible"] is True and type(x["text"]) is str and bool(x["text"].strip()) for x in r["labels"]), "native text captured for human readability review")
        else: need(p["views"]==[], "actions-only has no catalog claims")
        if mode in ("actions","all"):
            rows=p["actions"]
            need([r["phase"] for r in rows]==ACTION_PHASES, "finite paid action order")
            for r in rows:
                need(r["type"]=="PlayCardAction" and r["sameCard"] is True and r["events"]==["before-executed","after-finished"], "original paid action completed without AutoPlay/cancel")
                need(all(number(r[k]) for k in ("before","after","cost","start","end")) and r["cost"]>=0 and r["before"]-r["after"]==r["cost"] and 0<=r["start"]<=r["end"], "native energy/payment and time")
            need(all(rows[i]["end"]<=rows[i+1]["start"] for i in range(len(rows)-1)), "serialized paid action chronology")
            frames=p["frames"]
            need(bool(frames) and all(number(f["at"]) and f["at"]>=0 for f in frames) and all(frames[i]["at"]<=frames[i+1]["at"] for i in range(len(frames)-1)), "monotonic actual frame samples")
            observed={v["effect"] for f in frames for v in f["visual"]}
            need(observed<=EFFECTS and {"guard_gain","lightning_all","domain_enter","domain_loop","feral_claw","feral_body"}<=observed, "required finite business VFX routes")
            need(any(s["visible"] is True and s["playing"] is True for f in frames for s in f["sprites"]), "actual animated sprites observed")
            for f in frames:
                for v in f["visual"]:
                    need(v["anchors"] and all(a["node"] is not None and type(a["node"]["id"]) is int and a["node"]["id"]>0 for a in v["anchors"]), "real live anchor identities")
                    if v["effect"] in ("feral_claw","feral_body"):
                        need(any(a["node"]["cardModel"] is not None for a in v["anchors"] if a["node"]), "beast transition anchored to actual card, not just actor")
            for w,h in ((1280,720),(1920,1080)):
                shots=[x["screenshot"] for x in p["screens"] if x["phase"]==f"resolution-{w}x{h}"]
                need(any((s["width"],s["height"])==(w,h) for s in shots), "both real viewport resolutions")
            audio=p["audio"]
            need(type(audio["driver"]) is str and bool(audio["driver"]) and "dummy" not in audio["driver"].lower(), "actual non-Dummy audio driver")
            need(audio["origin"]=="this-process-Godot-AudioServer" and audio["bus"]=="Master" and audio["systemCapture"] is False and audio["forcedUnmute"] is False and audio["heard"] is False, "game-only PCM, no forced unmute or hearing claim")
            need(audio["channels"]==2 and type(audio["sampleRate"]) is int and 8000<=audio["sampleRate"]<=192000 and type(audio["frames"]) is int and audio["frames"]>0 and audio["discardedFrames"]==0, "unbroken finite stereo PCM")
            need(number(audio["rms"]) and number(audio["peak"]) and 0<audio["rms"]<=audio["peak"]<=1, "nonzero finite bus mix, not per-cue audibility")
            voices=audio["voices"]
            need(bool(voices) and len({v["node"] for v in voices})==len(voices), "actual unique source audio nodes")
            errors.extend(_source_audio_errors(voices, effective_files))
            for v in voices:
                need(all(number(v[k]) for k in ("first","last","ended")) and 0<=v["first"]<=v["last"]<=v["ended"], "voice start/overlap/end timeline")
            cleanup=p["cleanup"]
            need(cleanup["cause"]=="native-last-enemy-death" and cleanup["afterVisuals"]==cleanup["afterVoices"]==0 and cleanup["oldRootAlive"] is False and cleanup["roomAttached"] is False, "native combat-end owned node cleanup")
        else: need(p["actions"]==[] and p["audio"] is None and p["cleanup"] is None, "cards-only not audio/cleanup evidence")
    except (OSError,KeyError,TypeError,ValueError,IndexError,StopIteration,AttributeError) as exc:
        errors.append("malformed capture: "+str(exc))
    return errors


def _artifact(root, relative):
    if type(relative) is not str or not relative or Path(relative).name!=relative or ":" in relative or "\\" in relative:
        raise ValueError("artifact must be one relative filename")
    path=(root/relative).resolve()
    if path.parent!=root or not path.is_file(): raise ValueError("missing/outside artifact: "+relative)
    return path


def _decode_screenshot(root, job):
    shot, preflight_error = job
    if preflight_error is not None:
        return None, preflight_error
    try:
        path=_artifact(root,shot["path"]);data=path.read_bytes()
        if data[:8]!=b"\x89PNG\r\n\x1a\n" or len(data)<64:raise ValueError("not a complete PNG")
        if struct.unpack(">II",data[16:24])!=(shot["width"],shot["height"]):raise ValueError("PNG dimension mismatch")
        from PIL import Image
        with Image.open(path) as image:
            image.load()
            with image.convert("RGB") as rgb:
                if all(lo==hi for lo,hi in rgb.getextrema()):raise ValueError("flat/blank viewport")
        return hashlib.sha256(data).hexdigest(), None
    except (OSError,ValueError,TypeError,KeyError,struct.error,SyntaxError,AttributeError,EOFError,OverflowError) as exc:
        return None, "artifact evidence: "+str(exc)


def validate(p, token, mode, artifact_dir):
    errors=_structure(p,token,mode)
    try:
        root=Path(artifact_dir).resolve(strict=True)
        shots=[r["screenshot"] for r in p["views"]]+[r["screenshot"] for r in p["screens"]]
        names=set();catalog_hashes=set();jobs=[]
        for shot in shots:
            preflight_error=None
            try:
                if shot["origin"]!="native-viewport" or shot["path"] in names: raise ValueError("duplicate/non-native screenshot")
                names.add(shot["path"])
            except (ValueError,TypeError,KeyError) as exc:
                preflight_error="artifact evidence: "+str(exc)
            jobs.append((shot,preflight_error))
        # Independent fresh decodes, fixed cap; reduce in original screenshot order.
        image_errors=[]
        with ThreadPoolExecutor(max_workers=4) as workers:
            for index,(digest,error) in enumerate(workers.map(lambda job: _decode_screenshot(root,job),jobs)):
                if error is not None:image_errors.append(error)
                elif index<len(p["views"]):catalog_hashes.add(digest)
        errors.extend(image_errors)
        if p["views"] and not image_errors and len(catalog_hashes)!=356:
            errors.append("artifact evidence: catalog screenshots reused/not distinct")
        if p["audio"] is not None:
            a=p["audio"]
            with wave.open(str(_artifact(root,a["wav"])),"rb") as wav:
                if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())!=(2,2,a["sampleRate"],a["frames"]):raise ValueError("actual WAV header mismatch")
                samples=array.array("h",wav.readframes(wav.getnframes()))
            if sys.byteorder!="little":samples.byteswap()
            if not samples or not any(samples):raise ValueError("actual WAV is silent")
            peak=max(abs(x) for x in samples)/32767
            rms=math.sqrt(sum((x/32767)**2 for x in samples)/len(samples))
            if abs(peak-a["peak"])>2/32767 or abs(rms-a["rms"])>2/32767:raise ValueError("actual PCM statistics differ")
    except (OSError,ValueError,TypeError,KeyError,struct.error,wave.Error) as exc:
        errors.append("artifact evidence: "+str(exc))
    return errors


SHUTDOWN_RACE = ('ERROR: Invalid Task ID',)


def _engine_shutdown_race(line):
    return line.strip() in SHUTDOWN_RACE or 'Unreferenced static string' in line


def check_log(text,token,mode,artifact_dir):
    cleaned='\n'.join(line for line in text.splitlines() if not _engine_shutdown_race(line))
    if re.search(r"PRESENTATION_ACCEPTANCE_ERROR|\bERROR\s*:|Unhandled\s+exception|FATAL|\[Volibear presentation:",cleaned,re.I):return ["runtime/presentation error in full supplied log"]
    lines=[line.split(MARKER,1)[1] for line in text.splitlines() if MARKER in line]
    if len(lines)!=1:return ["expected exactly one matching presentation result"]
    try:
        def unique(pairs):
            result={}
            for k,v in pairs:
                if k in result:raise ValueError("duplicate JSON key")
                result[k]=v
            return result
        return validate(json.loads(lines[0],object_pairs_hook=unique),token,mode,artifact_dir)
    except (ValueError,TypeError) as exc:return ["malformed presentation JSON: "+str(exc)]
