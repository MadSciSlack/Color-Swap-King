# Color Swap List — Prototype 0

First concrete parser prototype for Bambu Studio 3MF G-code.

## What it does

- Detects Bambu 3MF G-code by the presence of `Metadata/plate_1.gcode`.
- Reads Bambu filament metadata from `slice_info.config` and `plate_1.json`.
- Normalizes Bambu's zero-based `T0`, `T1`, etc. to user-facing filament numbers `#1`, `#2`, etc.
- Finds ordered `CP TOOLCHANGE START` events in the print G-code.
- Tracks the current `; layer #N` and `; Z_HEIGHT` for each transition.
- Preserves raw G-code line numbers.
- Keeps transition origin as `unknown` rather than incorrectly treating a post-slice/user-added change as a physical manual intervention.
- Resolves physical interactions using a user-supplied manual-infeed set.

## Example

```text
python prototype.py TestCube1-Manual-V1.gcode.3mf --manual 6
```

The resulting checklist should contain a manual load of #6 on layer 6 and a manual unload of #6 on layer 7.

## Current deliberate limitations

- No generic G-code parser yet.
- No GUI yet.
- No printable HTML/PDF yet.
- No attempt to infer whether a transition was manually added after slicing.
- Only the print's primary `plate_1.gcode` is parsed.
- Startup/shutdown `T` commands outside a `CP TOOLCHANGE START` block are ignored.
