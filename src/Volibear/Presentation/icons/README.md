# Relic and power art

The two production relics use the painted PNGs in `relics/`:

| Resource | Normal | Inspection | Hover outline |
| --- | --- | --- | --- |
| Lightning heart (starter) | `relics/lightning_heart.png`, 64px | `relics/big/lightning_heart.png`, 256px | `relics/outline/lightning_heart.png`, 64px |
| Storm crown (upgraded) | `relics/storm_crown.png`, 64px | `relics/big/storm_crown.png`, 256px | `relics/outline/storm_crown.png`, 64px |

These original project illustrations were generated with OpenAI imagegen for the
user's requested relic redesign on 2026-11-01. The stormstone, bronze bindings,
ivory fangs and pale fur match the approved character palette. The separate
masters in `masters/` retain their transparent source pixels. The project asset
license applies; these are not extracted Riot or Mega Crit item images.

Run `python -B tools/export_relic_icons.py` from the repository root to reproduce
the six checked-in game exports. This only resizes with premultiplied alpha and
derives the hover outline from the same silhouette. The PCK builder copies the
exports unchanged; it never regenerates artwork during an ordinary build.

The old four relic SVGs are retained as editable historical sources but are no
longer referenced by production. `thunder_force.svg` and `domain.svg` remain the
two original power runes. `VolibearIcons.cs` is the authoritative runtime path
table, and the PCK verifier loads all ten normal/big/outline resources in Godot.
