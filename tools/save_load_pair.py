#!/usr/bin/env python3
"""Standalone native lifecycle runner. Never builds/deploys or edits a native save.
Only an explicit --execute-native launches games; source/unit-test imports are inert.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/headless.py').is_file())
sys.path.insert(0,str(ROOT/'tools'))
import headless as h
from save_load_evidence import parse_log, validate_pair, eq, native_reload_expected
from save_load_profile import create_owned_profile, shader_directory_budget


def phase_command(game,directory,display,frames):
    command=[str(h.game_executable(game)),'--headless','--audio-driver','Dummy',
             '--force-steam=off','--quit-after',str(frames),'--log-file',str(directory/'game.log')]
    return h.display_command(command,display) # Deliberately no --bootstrap.


def launch_phase(game,pair_dir,base_env,case,mode,phase,seed,stock,stock_evidence,timeout,frames,display):
    directory=pair_dir/('phase-'+phase);directory.mkdir(exist_ok=False)
    token=pair_dir.name+'-'+phase+'-'+uuid.uuid4().hex[:12]
    env=base_env.copy();env.update(VOLIBEAR_TEST_TOKEN=token,VOLIBEAR_TEST_ARTIFACT_DIR=str(directory),
        VOLIBEAR_TEST_SCENARIO='save-load-contract',VOLIBEAR_SAVE_PAIR=pair_dir.name,
        VOLIBEAR_SAVE_PHASE=phase,VOLIBEAR_SAVE_MODE=mode,VOLIBEAR_SAVE_CASE=case,VOLIBEAR_SAVE_SEED=seed)
    root=Path(env['VOLIBEAR_TEST_DATA_ROOT'])
    checkpoint=root/'default/1/modded/profile1/saves/current_run.save'
    command=phase_command(game,directory,display,frames)
    with (directory/'stdout.log').open('w',encoding='utf-8') as output:
        process,job=h.spawn_owned(command,game,env,output,window=h.IS_WINDOWS and display=='window')
        pid=process.pid
        try:code,timed_out=h.wait_owned_process(process,timeout,job)
        finally:h.close_owned(job)
    log=h.combined_log(directory)
    checks=h.evaluate(code,timed_out,log,stock)
    checks['stock_control_success']=bool(stock_evidence.get('successful') is True and
        stock_evidence.get('exit_code')==0 and stock_evidence.get('timed_out') is False)
    expected=dict(token=token,pair=pair_dir.name,phase=phase,mode=mode,caseId=case,seed=seed,pid=pid,
                  userRoot=str(root),checkpointPath=str(checkpoint))
    lifecycle_errors=[]
    raw,checks['save_lifecycle']=parse_log(log,expected,lifecycle_errors)
    try:
        actual=json.loads(checkpoint.read_text(encoding='utf-8'))
        checks['disk_checkpoint_matches_raw']=raw is not None and eq(actual,raw['afterMenu' if phase=='prepare' else 'afterLoad'])
    except (OSError,ValueError,KeyError,TypeError):checks['disk_checkpoint_matches_raw']=False
    defaulted_map_points=[]
    if checks['save_lifecycle'] and phase!='prepare':
        _,defaulted_map_points=native_reload_expected(raw['checkpoint'])
    report=dict(phase=phase,token=token,pid=pid,command=command,exit_code=code,timed_out=timed_out,
                checks=checks,passed=all(v is True for v in checks.values()),expected=expected,raw=raw,lifecycle_errors=lifecycle_errors,
                native_reload_defaulted_map_points=defaulted_map_points)
    (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def gate_then_resume(a,checkpoint,resume):
    """No B until ALL shared/runtime/oracle/disk gates from this actual invocation pass."""
    required={'exited_zero','steam_disabled','no_cloud_backend','no_runtime_errors','mod_initialized',
              'runtime_isolation','teardown_matches_stock','stock_control_success','save_lifecycle','disk_checkpoint_matches_raw'}
    if set(a.get('checks',{}))!=required or any(v is not True for v in a['checks'].values()):return None
    # A.report.passed alone is not an authority. Re-run the raw oracle with runner bindings.
    from save_load_evidence import validate_phase
    if not validate_phase(a.get('raw',{}),a.get('expected',{})) or a['expected']['phase']!='prepare':return None
    try:
        if not eq(json.loads(checkpoint.read_text(encoding='utf-8')),a['raw']['afterMenu']):return None
    except (OSError,ValueError,TypeError,KeyError):return None
    return resume()


def run_pair(game,case,mode,timeout=180,frames=30000,display='headless'):
    if case not in ('S1','S2') or mode not in ('same-process','restart'):raise ValueError('Unsupported case/mode')
    h.display_command([],display)
    if display not in ('headless','window'):raise ValueError('PID binding requires direct executable, not xvfb wrapper')
    h.validate_game(game)
    pair_dir=ROOT/'artifacts/save-load'/h.new_run_id();pair_dir.mkdir(parents=True,exist_ok=False)
    profile=create_owned_profile() # Unique short owned root, shared unchanged by A and B; never delete its cache.
    env=h.isolated_env(profile)
    for key in list(env):
        if key.startswith(('VOLIBEAR_TEST_','VOLIBEAR_SAVE_')):del env[key]
    root=h.user_data_root(profile);env['VOLIBEAR_TEST_DATA_ROOT']=str(root)
    (pair_dir/'profile.json').write_text(json.dumps(dict(pair=pair_dir.name,profile=str(profile),userRoot=str(root),
        checkpointPath=str(root/'default/1/modded/profile1/saves/current_run.save'),
        shaderDirectoryBudget=shader_directory_budget(root) if h.IS_WINDOWS else None),indent=2)+'\n',encoding='utf-8')
    settings=root/'default/1/settings.save';settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(dict(schema_version=5,mod_settings={'mods_enabled':True},seen_ea_disclaimer=True,
        skip_intro_logo=True,fullscreen=False,language='zhs',limit_fps_in_background=False))+'\n',encoding='utf-8')
    # Fresh stock control per invocation; no trusted external passed/report shortcut.
    stock,stock_evidence=h.stock_teardown(game,timeout,frames,display)
    if not stock_evidence.get('successful'):
        return dict(pair=pair_dir.name,passed=False,reason='stock-control-failed',stock=stock_evidence,phases=[])
    seed='VOLIBEAR-SAVE-'+case
    first='same' if mode=='same-process' else 'prepare'
    a=launch_phase(game,pair_dir,env,case,mode,first,seed,stock,stock_evidence,timeout,frames,display)
    phases=[a]
    if mode=='restart':
        b=gate_then_resume(a,Path(a['expected']['checkpointPath']),lambda:launch_phase(
            game,pair_dir,env,case,mode,'resume',seed,stock,stock_evidence,timeout,frames,display))
        if b is not None:phases.append(b)
        passed=b is not None and validate_pair(a['raw'],b['raw'],a['expected'],b['expected'],a['passed'],b['passed'])
    else:passed=a['passed']
    report=dict(pair=pair_dir.name,case=case,mode=mode,profile=str(profile),userRoot=str(root),acceptance='save-lifecycle-only-not-G6',passed=passed,
                stock=stock_evidence,phases=phases)
    (pair_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native',action='store_true',help='Explicitly authorize bounded native game launches; never deploys')
    parser.add_argument('--case',choices=['S1','S2'],default='S1')
    parser.add_argument('--mode',choices=['same-process','restart'],default='restart')
    parser.add_argument('--display',choices=['headless','window'],default='window' if h.IS_WINDOWS else 'headless')
    parser.add_argument('--timeout',type=int,default=180);parser.add_argument('--frames',type=int,default=30000)
    args=parser.parse_args()
    if not args.execute_native:parser.error('--execute-native is required; no game was launched')
    if not 30<=args.timeout<=300 or not 1000<=args.frames<=60000:parser.error('timeout30..300 frames1000..60000')
    game=Path(h.config()['game_dir']).expanduser().resolve()
    result=run_pair(game,args.case,args.mode,args.timeout,args.frames,args.display)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
