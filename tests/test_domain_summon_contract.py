"""Exact source-boundary + real native IL checks; native gameplay acceptance is separate."""
from pathlib import Path
import json
import os
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/Volibear/Core/DomainSummonEffects.cs'
def body(source,name):
    match=re.search(r'(?:private|public|internal) static [^\n]+\b'+re.escape(name)+r'\(',source)
    if not match:raise AssertionError('Missing production method: '+name)
    opening=source.index('{',match.start());depth=1;cursor=opening+1
    while depth:
        if source[cursor]=='{':depth+=1
        if source[cursor]=='}':depth-=1
        cursor+=1
    return source[opening:cursor]
class DomainSummonSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.source=SOURCE.read_text(encoding='utf-8')
    def test_exact_actual_async_body_allowlist(self):
        rows=re.findall(r'Add\(typeof\((\w+)\),\s*(?:"([^"]+)"|nameof\(\w+\.(\w+)\))',self.source)
        self.assertEqual([(a,b or c) for a,b,c in rows],[('Fabricator','SpawnBot'),('Ovicopter','LayEggsMove'),('InfestedPower','AfterDeath'),
            ('CreatureCmd','KillWithoutCheckingWinCondition'),('Fabricator','FabricateMove'),('Fabricator','FabricatingStrikeMove'),
            ('LivingFog','BloatMove'),('TwoTailedRat','CallForBackup'),('Fogmog','IllusionMove'),('TheObscura','IllusionMove')])
        self.assertIn('transpiler: new HarmonyMethod(typeof(DomainSummonEffects), nameof(Rewrite))',self.source)
        self.assertIn('nameof(InfestedPower.ShouldStopCombatFromEnding)',self.source)
        additional=(ROOT/'src/Volibear/Core/DomainSummonEffects.Additional.cs').read_text(encoding='utf-8')
        self.assertIn('RewriteAdditionalBirth(code, frame, kind)',self.source)
        self.assertIn('code[result + 1].opcode == OpCodes.Pop',additional)
        self.assertIn('Additional summon caller no longer discards its child result.',additional)
        self.assertIn('CancelAtGate(frame, "AdditionalBirth.pre-create")',additional)
        self.assertIn('return CreatureCmd.Add<T>(combat, slot);',additional)
    def test_no_global_creator_or_mixed_attack_replacement(self):
        self.assertNotRegex(self.source,r'CreatureCmd\.Add\s*\(')
        for forbidden in ('Task.FromResult','new Creature(', 'typeof(SurprisePower)','typeof(HeistPower)','nameof(MonsterModel.PerformMove)'):
            self.assertNotIn(forbidden,self.source)
        self.assertIn('Original Add', (ROOT/'tests/domain_summon_effects/Program.cs').read_text(encoding='utf-8'))
        self.assertIn('Mixed move actual attack/await/continuation changed',self.source)
    def test_death_domain_read_cannot_recurse_through_ending(self):
        capture=body(self.source,'DomainAtDeathEntry')
        for required in ('manager.IsInProgress','!manager.IsAboutToLose','combat.ContainsCreature(owner)','owner.GetPowerAmount<DomainPower>() > 0'):
            self.assertIn(required,capture)
        for forbidden in ('IsEnding','IsOverOrEnding','DomainPower.IsActive','DomainEnemyEffects.ActiveFor'):
            self.assertNotIn(forbidden,capture)
    def test_veto_only_reads_consumed_event(self):
        veto=body(self.source,'NeutralizeCancelledVeto')
        self.assertIn('Decision.Cancelled == true',veto)
        for forbidden in ('ActiveFor','GetPowerAmount','AtBoundary'):
            self.assertNotIn(forbidden,veto)
        enter=body(self.source,'Enter')
        self.assertIn('if (!prevented && target is not null)',enter)
        self.assertIn('MatchingEvent((InfestedPower)source, target)',enter)
        self.assertIn('!CanAttachDeathBirth(batch.Closed, batch.Decision.Cancelled)',enter)
    def test_same_power_owner_battle_and_epoch_required(self):
        match=body(self.source,'MatchingEvent')
        for expression in ('Attempts.TryGetValue(power','ReferenceEquals(power.Owner, target)','ReferenceEquals(attempt.Owner, target)',
            'target.IsAlive','ReferenceEquals(attempt.Combat, CombatManager.Instance.DebugOnlyGetState())','attempt.Generation != _generation'):
            self.assertIn(expression,match)
        self.assertIn('ConditionalWeakTable<InfestedPower, DeathAttempt>',self.source)
    def test_native_task_binding_close_and_reset(self):
        capture=body(self.source,'CaptureDeath');leave=body(self.source,'Leave')
        for required in ('new DeathAttempt','Attempts.Remove(power)','Attempts.Add(power, attempt)'):self.assertIn(required,capture)
        self.assertIn('Tasks.VerifyReturn(frame.Binding, ref builder, state)', leave)
        self.assertNotIn('Tasks.Begin', leave)
        self.assertIn('Tasks.Close(frame.Binding, static batch => { batch.Closed = true; batch.Decision.Close(); })', self.source)
        registration=(ROOT/'src/Volibear/Core/SummonRegistration.cs').read_text(encoding='utf-8')
        self.assertIn('receipt.BindBeforeSchedule(actual)',registration)
        self.assertIn('binding.Payload=null',registration)
        self.assertNotIn('Tasks = new()',body(self.source,'Reset'))
        self.assertGreaterEqual(len(re.findall(r'OpCodes.Ldflda,\s*builder',self.source)),2)
        self.assertIn('CombatSetUp += _ => Reset()',self.source);self.assertIn('CombatEnded += _ => Reset()',self.source)
        self.assertIn('nameof(CombatManager.Reset)',self.source)
        self.assertIn('Interlocked.Increment(ref _generation)',self.source)
    def test_move_identity_does_not_reserve_a_future_summon(self):
        enter=body(self.source,'Enter');forward=body(self.source,'Forward')
        self.assertIn('new Batch(owner, combat, false)',enter)
        self.assertNotIn('DomainEnemyEffects.ActiveFor',enter)
        self.assertIn('ticket.TryClaim(kind, source, out var parent)',enter)
        self.assertIn('Tasks.Retired(parent.Epoch, source, kind)',enter)
        self.assertIn('ReferenceEquals(frame.Subject, source) ? frame.Binding : null',forward)
        self.assertLess(enter.index('ticket.TryClaim'),enter.index('var owner = ((MonsterModel)source).Creature'))
        self.assertIn('finally { Pending.Value = previous; }',forward)
        self.assertIn('return native(source)',forward)
    def test_all_guards_precede_creation_and_keep_native_completion(self):
        for boundary in ('SpawnBot.entry-pre-selection','LayEggs.entry','LayEggs.pre-create','Infested.confirmed-entry','Infested.post-wait-pre-music','Infested.pre-create'):
            self.assertIn('"'+boundary+'"',self.source)
        self.assertRegex(self.source,r'OpCodes.Leave,\s*complete')
        self.assertIn('Committed child result/Minion continuation changed',self.source)
        self.assertIn('Native Wriggler StartStunned initializer changed',self.source)
        self.assertIn('Native summon loop bound changed',self.source)
        self.assertIn('Native Create/Add gained a precommit await',self.source)
    def test_real_native_decisions_mutation_and_both_adapter_orders(self):
        config_file=ROOT/'.local/config.json'
        if not config_file.exists():self.skipTest('Local native configuration unavailable; NOT RUN')
        config=json.loads(config_file.read_text(encoding='utf-8'));dotnet=Path(config.get('dotnet',''))
        data_name='data_sts2_windows_x86_64' if os.name=='nt' else 'data_sts2_linuxbsd_x86_64'
        data=Path(config.get('game_dir',''))/data_name;mod=ROOT/'src/Volibear/bin/Release/net9.0/Volibear.dll'
        if not dotnet.is_file() or not(data/'sts2.dll').is_file() or not mod.is_file():self.skipTest('Real native dependencies unavailable; no engine substitutes')
        result=subprocess.run([str(dotnet),'run','--project',str(ROOT/'tests/domain_summon_effects/DomainSummonEffects.Tests.csproj'),'-c','Release','-p:Sts2DataDir='+str(data)],
            cwd=ROOT,capture_output=True,text=True,timeout=120,env=dict(os.environ,DOTNET_NOLOGO='1'))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('PASS 142 summon D17 decision/native IL/mutation/combined checks',result.stdout)
        self.assertIn('Summon->Revival',result.stdout);self.assertIn('Revival->Summon',result.stdout)
        self.assertIn('native gameplay NOT RUN',result.stdout)
if __name__=='__main__':unittest.main()
