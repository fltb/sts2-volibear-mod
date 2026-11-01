# Native Volibear visuals (BaseLib 3.4.7)

This is an independently authored adapter using BaseLib's public node factory and native Godot
`AnimatedSprite2D`. It does not copy third-party implementation code or use an Ironclad scene.

## Integration owned by the character/build maintainer

The character must derive from `BaseLib.Abstracts.CustomCharacterModel` and override:

```csharp
public override string CustomVisualPath => VolibearPresentation.CombatScenePath;
public override NCreatureVisuals CreateCustomVisuals() => VolibearPresentation.CreateCombatVisuals();
public override string CustomCharacterSelectBg => VolibearPresentation.SelectionScenePath;
public override float DeathAnimTime => VolibearPresentation.DeathAnimationSeconds;
public override string CustomIconPath => VolibearPresentation.IconScenePath;
public override string CustomEnergyCounterPath => VolibearPresentation.EnergyScenePath;
public override string CustomRestSiteAnimPath => VolibearPresentation.RestScenePath;
public override string CustomMerchantAnimPath => VolibearPresentation.MerchantScenePath;
public override string CustomTrailPath => VolibearPresentation.TrailScenePath;
public override string CustomCharacterSelectTransitionPath => VolibearPresentation.TransitionMaterialPath;
```

Call `VolibearPresentation.RegisterSceneConversions()` once during mod initialization, after
BaseLib initialization and before card trail creation. This installs the small, independently
authored `NodeFactory<NCardTrailVfx>` adapter and registers only this mod's trail scene. The
character's other scene paths use BaseLib's inherited `RegisterSceneConversions()`; call that
from the character constructor after its configuration is initialized, because custom bootstrap
paths can bypass BaseLib's `ModelDb.Preload` registration postfix. The trail root cannot
remain a plain Node2D at runtime: game `NCardTrailVfx.Create(Control, string)` instantiates the
scene as `NCardTrailVfx`, then owns card following, particle reduction, fade and node cleanup.
The factory supplies that game root type; it does not reimplement those behaviors.

Use namespace `Volibear.Presentation`. Reference the selected BaseLib 3.4.7 release DLL in the
main project; ordinary SDK C# globbing includes this adapter. No C# scene script is exported.
Do not call the old AssetBridge visual replacement prefix or override these paths with its
Ironclad substitutions. BaseLib must initialize its factories before creating the character.
`CustomVisualPath` also lets BaseLib register/preload the scene for native-root conversion.

BaseLib's custom animation patch discovers `Visuals/AnimatedSprite2D`; no Spine animator or
`SetupCustomAnimationStates` is needed. Aliases support idle, attack, cast, hurt/hit and die/dead.
Actions return to the configured loop; death holds frame 39. The 26 original clip names remain
available through `VolibearPresentation.Play(visuals, clip)`.
`SetIdle(visuals, loop)` changes the next return pose, without interrupting an action.
Domain/feral/low-HP gameplay events are NOT wired here. No custom animation wait is introduced.

## Native UI contracts

- Icon: native `TextureRect`/`Control`, using the approved 128px portrait; no game script.
- Energy: 128px `Control` with `Label` (BaseLib converts it to `MegaLabel`), unique `Layers`,
  `RotationLayers`, `EnergyVfxBack`, `EnergyVfxFront`, `StarAnchor`. The game owns label updates,
  zero-energy darkening and rotation. Particle containers are intentionally empty; this slice
  does not claim new energy VFX. The approved energy emblem stays upright.
- Rest: `Node2D` plus `ControlRoot`, unique `Hitbox` and left/right thought anchors. The factory
  creates the universal game selection reticle. Visuals are under `ControlRoot` so native flip
  also flips the actor. Approved `relaxed_loop` is reused; no seated animation is claimed.
- Merchant: `Node2D` with native `AnimatedSprite2D`; BaseLib's merchant patch replaces the Spine
  entry points. Separate social SpriteFrames map its preferred `idle` alias to `relaxed_loop`.
- Trail: native `Sprites` child with `CPUParticles2D`, matching the game's fade/particle contract;
  motes reuse the approved small energy emblem. No gameplay-triggered VFX or audio is added.
- Selection transition: **ShaderMaterial**, not PackedScene. Game `NTransition.FadeOut` drives
  `shader_parameter/threshold` from 0 (transparent) to 1 (black). The intermediate image reuses
  the approved transition cutout. Both shader and material are independently authored.

## Production event bridge

The mod entrypoint calls `VolibearPresentationBridge.Install()` once, after core/character
initialization. The bridge changes no gameplay model values and never replaces an original
command Task, waits for VFX, chooses targets, or consumes gameplay RNG. It is restricted to
owners whose actual native Character is `VolibearCharacter`; other characters are untouched.

- Native `CombatManager.History.Changed` supplies committed typed entries: card play start,
  ordinary `CreatureAttackedEntry`, positive block, incoming damage, draw/discard/exhaust.
  `PrimitiveRoutes` is the intentional semantic table. Ordinary damage is never labeled lightning
  by inspecting Unpowered flags. Each native damage result retains its source card's authored
  contact style, so nested effects cannot substitute another card's last animation.
- Explicit-owner `LightningCmd.Deal` ensures the per-owner receipt subscription exists before
  the first batch. Only actual `LightningBatches` completion receipts produce lightning. Batch
  IDs and actual result receivers provide group deduplication; sound plays once across the group.
  Closed core-reset subscriptions are repaired without replacing active/reentrant subscribers.
- Actual Creature power events drive Domain entry/exit and StormCharge growth. Setup observers
  attach during `IsStarting`; domain loops renew every 200ms with a two-second lease only while
  the authoritative domain is positive and the owner alive. Snapshot/silent recovery does not
  pretend a fresh entry occurred. Revival alone cannot restore a domain presentation.
- `EngageCmd.Perform` gets an isolated AsyncLocal observation scope. A block telegraph pose is
  shown only if that invocation actually reaches its enemy's native `PerformIntent` after native
  eligibility/reservation. Incoming damage/block history supplies the real impacts. A successful
  performed/completed result with positive absorbed damage adds the absorb cue. Original task
  identity, faults, cancellation and exception objects remain unchanged; no guard is copied.
- `BeastForms.Converted` supplies the actual preserved card identity for claw/body card effects.
  Native replay entries show a replay stamp without repeating the primary paid-play pose.
- Anchors use actual `NCreature.Visuals` (feet), CenterPos, IntentPos and TalkPosition, real target
  visuals including still-visible dying nodes, and `NCard.FindOnTable` plus native pile buttons.
  Player.NetId, Creature.CombatId and NetCombatCardDb IDs are used unchanged. The combat interface
  exposes no global combat ID, so a presentation-only epoch is bound to the exact ICombatState
  reference and actual room instance, never presented as a network/gameplay identifier.
- Death stops owned loops/audio before its bounded death cue; actual combat end, Reset(bool) and
  room TreeExiting dispose subscriptions and players. A transient native IsEnding suspends
  cosmetics, rather than permanently breaking a battle that subsequently resumes. The only
  Harmony boundaries are room Ready, manager Reset, owner Lightning Deal, Engage Perform and
  native PerformIntent; no private card/MoveNext/settlement hooks are patched.

This first primitive bridge covers B01/B02/B03/B04, domain state, actual force growth, committed
ordinary attacks/block/draw, incoming reactions, replay/card movement and beast conversion.
The low-level renderer supports all 54 cues, but **not all are activated by this bridge**. In
particular selection/victory/low-health/footstep, dedicated hand-cast charge, native heal/energy,
status-specific enemy effects, purification-versus-generic-exhaust, full transfer choreography
and all later card/passive semantic bindings need their own precise event integrations. No
normal-window visual/audio acceptance follows from merely installing or compiling this bridge.

## Semantic VFX/audio API

Keep one `VolibearEffects.Attach(sceneOwner, battleId, ownerId)` instance per player/room, not
one per card. The owner must already be in the Godot tree. All calls are main-thread only.
The C# facade loads the shipped `volibear_effects.tscn` / `effects.gd` native controller; it does
not need a registered game-root conversion. The controller uses all 40 approved effect atlases,
47 Ogg streams / 54 manifest cues, and no gameplay RNG, calculations, mutation or awaited effect.

```csharp
// On a confirmed physical hit; ownerVisuals/targetVisuals are existing CanvasItems.
effects.Emit(resolvedEventId, "claw_slash",
    new EffectAnchors(ownerVisuals, Target: targetVisuals), targetEntityId);
// On actual domain state entry (persistent key is per owner and state).
effects.Emit(stateEventId, "domain_loop", new EffectAnchors(ownerVisuals),
    persistentKey: domainKey, leaseSeconds: 10f);
// Renew periodically ONLY while authoritative state is still active; never restart on loop wrap.
effects.RenewLoop(domainKey, 10f);
effects.StopLoop(domainKey); // state exit: immediate visual stop, 140ms audio fade
// Independent successful semantic sound, including voice.* cues:
effects.PlaySound(resolvedEventId, "sfx.guard_hit");
// Death: stop owned domain/audio. Battle/room release: dispose the whole owner.
effects.StopAll();
effects.Dispose();
```

- Event IDs must identify actual committed events, not render frames or animation markers.
  Deduplication is per owner/battle, event + effect + stable target ID, within a bounded 4096-key
  rolling window. A new room/battle gets a new service. Supply `targetId` for target/card events;
  do not use a speculative target. Group damage calls once per resolved target with the same
  event ID; sound deduplicates by event + cue so groups do not start one sound per enemy.
- `EffectAnchors` supplies Owner, Target, Source, Card, Energy, OwnerHand, OwnerMouth and CardCost.
  Ordinary contact/status nodes use recursive `CenterPos`/`IntentPos` markers if available;
  ground uses the node origin. Controls use their transformed center/top/bottom. Explicit
  Marker2D endpoints are accepted. Canvas transforms are converted into this service's canvas.
  Card, cost, energy, hand and mouth effects require the corresponding explicit node; missing or
  freed anchors reject/cancel presentation instead of inventing a gameplay target.
- The manifest selects owner/target/ground/status positioning. Counter/chain/lifesteal map the
  actual authored segment endpoints, including reverse lifesteal direction; only their length
  axis stretches. Feral transfer preserves aspect ratio and pins its authored arrival point to
  the selected card. Card/pile transition atlases remain local arrival effects, not invented
  full-screen card movement. `lightning_all` can be emitted per actual resolved enemy.
- Maximum 64 simultaneous visuals, 24 sound players, manifest per-cue voice counts/cooldowns and
  one Voice-category player. Disabled `sfx.feral_aura` stays off unless explicitly requested with
  `PlaySound(..., allowDisabled: true)`. Native streams are duplicated before setting loop mode;
  imported resources are never mutated. `sound: false` permits cosmetic audio omission.
- Every one-shot has natural completion and a bounded safety timeout. Persistent keys require
  explicit renewal; leases are capped at 60 seconds. Stop by key on authoritative status exit,
  stop all on owner death, dispose on battle/room exit. Freed anchors cancel bound loops. Same-key
  updates rebind endpoints and renew the existing animation/sound without restarting it.
- Default gain reads the game's squared Master/Sfx/Ambience slider settings plus background mute;
  Voice follows Sfx unless an optional `Func<string,float>` gain provider is supplied. Live gains
  refresh during playback. Manifest mix attenuation/headroom and conservative simultaneous-voice
  normalization are applied. No global bus or output device is changed, and normal windows never
  force Dummy audio. Headless decode/lifecycle verification is not a listening approval.

## Original relic and power runes

The six SVG masters under `icons/` are newly authored geometry, not modifications of approved
art or borrowed game assets. The builder exports ten textures: packed/outline 64px, big 256px.
`VolibearIcons` supplies exact runtime path constants:

- LightningHeart, LightningHeartOutline, LightningHeartBig: `icons/relics/lightning_heart.svg`,
  `icons/relics/outline/lightning_heart.svg`, `icons/relics/big/lightning_heart.svg`.
- StormCrown, StormCrownOutline, StormCrownBig: matching `storm_crown.svg` paths.
- ThunderForce, ThunderForceBig: `icons/powers/thunder_force.svg` and
  `icons/powers/big/thunder_force.svg`.
- Domain, DomainBig: matching `domain.svg` power paths.

All these paths have prefix `res://VolibearArt/`. Native relic overrides are **not** named
CustomIconPath:

```csharp
public override string PackedIconPath => VolibearIcons.LightningHeart;
protected override string PackedIconOutlinePath => VolibearIcons.LightningHeartOutline;
protected override string BigIconPath => VolibearIcons.LightningHeartBig;
// On a BaseLib CustomPowerModel instead:
public override string CustomPackedIconPath => VolibearIcons.ThunderForce;
public override string CustomBigIconPath => VolibearIcons.ThunderForceBig;
public override string CustomBigBetaIconPath => VolibearIcons.ThunderForceBig;
```

## Resource-only production command

From the repository root, using Python 3 (with pip on Windows) and the installed Godot
**4.5.1 stable mono** executable. The Mono editor also needs the .NET SDK configured by
`.local/config.json`'s `dotnet` path, or available on PATH. Windows builds supply pip's bundled
CA certificates explicitly to the isolated editor, avoiding dependence on its access to the
host certificate store; these certificates are not exported into the PCK.

```powershell
$env:PYTHONUTF8='1'
$py = "$env:USERPROFILE\venvs\sts2-volibear\Scripts\python.exe"
$godot = "$env:LOCALAPPDATA\Programs\godot-4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe"
& $py tools/build_assets.py --godot $godot
& $py -m unittest discover -s tests -p test_assets.py
```

The build creates a fresh `.local/asset-build/<id>/` project, stages current runtime animation,
VFX/audio/UI using the existing stage selector, and adds all **89 small + 89 big portraits**.
It validates approved atlas/portrait SHA-256s, generates native resources/scenes, imports and
exports with Godot, mounts the candidate in a separate empty project, checks all clips and
portrait decodes, and exercises idle/action-return/death/selection playback. A second empty-project
verifier decodes all 40 VFX atlases, 47 Ogg streams to nonzero PCM and all ten SVG textures, then
runs the production effects controller through dedup, native playback, tether mapping, cooldown,
loop reuse/fade/expiry, capacity, target-free and scene-exit checks. Shutdown includes a bounded
250ms native mixer retirement interval; warnings/errors are not suppressed. Only after these
checks pass does it atomically publish `.local/packs/Volibear.pck`. No approved art is regenerated.
Use `--output .local/packs/Volibear-effects-candidate.pck` to build and verify a separate candidate
without replacing the current pack while integration tests are running. Output outside
`.local/` is rejected. UI, VFX atlas and Ogg source/staged bytes are checked against their approved
manifests as well. Runtime SVG icon exports are separate original resources.
Build logs remain in the ignored staging directory. The developer build entrypoint should run
this command and deploy this output, never the old `VolibearArt_v5.pck` candidate.

Runtime paths:

- `res://VolibearArt/scenes/volibear_combat.tscn`
- `res://VolibearArt/scenes/volibear_selection.tscn`
- `res://VolibearArt/scenes/volibear_frames.tres`
- `res://VolibearArt/scenes/volibear_icon.tscn`
- `res://VolibearArt/scenes/volibear_energy.tscn`
- `res://VolibearArt/scenes/volibear_rest.tscn`
- `res://VolibearArt/scenes/volibear_merchant.tscn`
- `res://VolibearArt/scenes/volibear_trail.tscn`
- `res://VolibearArt/scenes/volibear_transition.tres`
- `res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/b01.png`
- `res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/big/b01.png`

Card IDs in filenames are lowercase; substitute each approved ID. Load textures with Godot
`ResourceLoader` from these paths rather than external filesystem/junction loading.

## Explicit limits

Resource verification is not a BaseLib runtime integration or game acceptance test. Character
root conversion, normal selection-screen layout, action triggers in combat, UI icons/energy,
all gameplay event bindings, VFX, sound and lifecycle/window quality still require their
separate game tests. Selection currently supplies an animated native actor, not a complete
final character-select background composition. The scene's ground pivot is the approved
(250,442); combat bounds and marker positions are initial integration values requiring window
validation. No real-game deployment or whole-project build is performed by this command.
