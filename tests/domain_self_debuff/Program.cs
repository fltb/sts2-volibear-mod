using HarmonyLib;
using MegaCrit.Sts2.Core.Models.Powers;
using Volibear.Core;

Semantics.Run();
var harmony = new Harmony("Volibear.Tests.SelfDebuff");
DomainSelfDebuffEffects.Install(harmony);
DomainSandpitEffects.Install(harmony);
var patched = harmony.GetPatchedMethods().ToArray();
foreach (var method in patched) Console.WriteLine("BOUND " + method.DeclaringType!.FullName + "." + method.Name);
if (patched.Length < 20) throw new Exception("Missing native self-debuff contribution bindings");
var sandpit = AccessTools.DeclaredMethod(typeof(SandpitPower), "UpdateCreaturePositions");
if (!patched.Contains(sandpit)) throw new Exception("Sandpit attraction must be bound");
Console.WriteLine("SELF_DEBUFF_NATIVE_BINDINGS_PASS count=" + patched.Length);
SandpitChecks.Run();
WeakDurationChecks.Run();
BaseLibWeakDurationChecks.Run();
harmony.UnpatchAll(harmony.Id);
