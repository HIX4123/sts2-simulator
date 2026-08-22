# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project scope

This is a Python 3.11+ headless Slay the Spire 2 simulator. Runtime code uses only the standard library. The implementation is a fidelity port of the C# game data and behavior in `sts2.dll`, `sts2.xml`, and the locally decompiled sources under `decompiled/`; use those sources to resolve unclear card, power, monster, and encounter semantics. Port the non-Ascension/default values unless the task explicitly adds Ascension handling.

The README contains historical architecture and commands that no longer match the active code. In particular, the live combat/run path uses `random.Random`, duck-typed power hooks, a fixed floor plan, and root-level `test_sts2_*.py` scripts—not `SeededRng`, `HookBus`, a full map/event run, or `test_full_run.py`. Prefer current code and regression tests when documentation disagrees.

## Product goal and roadmap

The final goal is an AI mod capable of clearing Slay the Spire 2. Work toward it in this order:

1. Complete a faithful, reproducible headless simulation of the game systems needed for full runs.
2. Build and evaluate an AI that can use that simulator to clear the game.
3. Adapt the proven AI into a mod that can be integrated into the live game.

The repository is currently in the simulation stage. Prioritize simulation fidelity, coverage, and deterministic regression checks over speculative AI or mod infrastructure. Keep policy code separable from game mechanics, but do not add future-facing interfaces or integration layers until the current stage needs them.

New work uses the hierarchical Stage/Milestone/Batch IDs defined in `ROADMAP.md` (for example, `S1.M3.B18`); do not create new alphabetic Phase suffixes. Preserve existing `test_sts2_phase*.py` names as historical IDs. For new regression files, replace dots with underscores (for example, `test_sts2_s1_m3_b18.py`), while runtime monster modules continue their domain sequence (for example, `monsters_batch18.py`).

## Commands

Run commands from the repository root. Test scripts print emoji, so force UTF-8 on Windows to avoid a cp949 `UnicodeEncodeError` unrelated to test behavior.

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

Run one regression suite:

```powershell
python test_sts2_phase6l.py
```

Run every root regression suite and stop at the first failure:

```powershell
Get-ChildItem test_sts2_*.py | ForEach-Object {
    python $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Failed: $($_.Name)" }
}
```

Run one assert-based test function without pytest:

```powershell
python -c "from test_sts2_phase6l import test_registry_and_encounters; test_registry_and_encounters()"
```

If the optional dev dependencies are installed, the equivalent pytest selection is:

```powershell
python -m pytest test_sts2_phase6l.py::test_registry_and_encounters
```

Do not rely on bare `pytest`: `pyproject.toml` currently points `testpaths` at `sts2_sim`, while the active regression suites live at the repository root. There is no configured lint command. No verified package-build command is currently part of the development workflow; use the regression scripts as the authoritative check.

Run multi-seed simulations:

```powershell
python -m sts2_sim.core.stats ironclad 50 --policy greedy
python -m sts2_sim.core.stats ironclad 5 --policy greedy --verbose
```

`--verbose` emits full combat logs only for the first five runs.

## Architecture

### Registration and construction

`import sts2_sim` imports all character card modules through `sts2_sim.cards`, and those modules mutate `CARD_REGISTRY` at import time. Cards, powers, relics, orbs, characters, and monsters are concrete model classes constructed through registries and `create_*` helpers. Monster batch modules likewise extend `MONSTER_REGISTRY`; `core.encounters` imports the implemented batches and maps encounter IDs to seeded monster factories. When a registry lookup unexpectedly fails, first verify that the module performing import-time registration was imported.

### Combat model

`core.combat.CombatState` is the orchestration boundary for a single fight. It owns seeded RNG, draw/hand/discard/exhaust piles, card play, turn phases, monster actions, death reaping, and combat-scoped counters. `entities.player.Player` and `entities.sts2_monster.MonsterModel` share HP, block, powers, and damage behavior through `entities.creature.Creature`. Card effects live in concrete `STS2Card.use()` implementations and receive the `CombatState` when they need pile, orb, generation, or combat context.

Power events are intentionally duck-typed: combat, creature, card, and monster paths call optional methods such as `on_turn_start`, `on_turn_end`, `on_take_damage_powered`, `modify_hp_lost`, `on_any_death`, and `flush_landed_attacks` via `getattr`. Do not introduce or route new live behavior through the legacy `hooks/hook_bus.py` abstraction. Trace every emitter of a hook before deciding that a power method is unused.

Damage behavior distinguishes powered from unpowered effects and card-sourced from non-card-sourced effects. Preserve the existing ordering of outgoing additive/multiplicative modifiers, damage caps, block, and final HP-loss modifiers. Add a new hook only at the stage matching the decompiled command semantics; moving a cap or trigger between stages changes multi-hit and on-hit behavior.

### Monster moves and encounters

A monster builds a `MonsterMoveStateMachine` from `MoveState`, `RandomBranchState`, and `ConditionalBranchState` nodes. The state machine owns current intent, history, branch resolution, forced transitions, and temporary stun insertion. Encounters can assign constructor flags or `slot_name` before `CombatState.start()` so initial conditional branches resolve correctly.

C# `AddBranch` overloads are a recurring source of porting bugs. An integer argument is not automatically a weight: depending on the overload it can be `cooldown` or `max_repeats` while the base weight remains 1. Check the original overload declaration and call site before encoding a branch. Preserve history-dependent `cannot_repeat`, cooldown, fallback, and follow-up behavior rather than replacing the graph with ad hoc randomness.

### Run and policy layers

`core.run.RunState` is deliberately smaller than the game: it maintains a deck across a fixed `DEFAULT_FLOOR_PLAN`, selects encounters from room-specific pools, resolves rest sites, and chooses one of three weighted-rarity card rewards with a heuristic. It does not implement the real map graph, events, shops, or a complete encounter progression. `core.policy.GreedyPolicy` is an intent-aware heuristic; `core.combat.SimplePolicy` is the basic fallback. `core.stats` repeatedly creates seeded `RunState` instances and aggregates their results.

## Porting and verification

Keep concrete card/power/monster classes when they mirror concrete C# models; apparent repetition is often required for fidelity. Before porting a behavior, compare the model class, command implementation, state graph, relevant power hooks, and overloaded method declarations in the decompiled source. Add the smallest root-level assert-based regression to the relevant phase script, including a seeded smoke run when state-machine behavior is involved. The scripts are executable directly through their `main()` functions and are also pytest-discoverable.
