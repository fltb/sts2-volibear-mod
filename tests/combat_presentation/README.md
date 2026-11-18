# Combat presentation SDK fixture

`test_combat_presentation.py` compiles the complete production
`CombatPresentationCatalog.cs` and `VolibearPresentationBridge.Combat.cs`.
It also projects the exact `PresentOrdinarySegment`, `OrdinaryAttackPipelineV1`,
`ClearMotions`, `SuspendEnding`, `LightningBatches.Present`, owner lightning method and `Live`
expression from production, without rewriting statements.

The fixture supplies deliberately small native, Godot and Harmony boundary
doubles. They record receivers, styles, segment indices, sprite method calls and
patch metadata. They do not calculate damage, choose targets, advance animation
frames, emulate native history, apply real Harmony patches or simulate networking.
The pipeline tests control the native damage Task and observe the production
receipt order, cancellation, errors and invalidated scope behavior.

Every successful case prints `native-gameplay=NOT_RUN`. Passing these tests is
evidence for orchestration at the stated boundary; it is not a game load test,
an animation review, or an assertion that current StS2 ABI is compatible.

Run with an existing .NET 9 SDK:

```sh
VOLIBEAR_DOTNET=/path/to/dotnet python -m unittest tests.test_combat_presentation -v
```
