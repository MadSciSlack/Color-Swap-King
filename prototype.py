from __future__ import annotations
import argparse
import json
from bambu_parser import parse, to_dict


def main():
    ap = argparse.ArgumentParser(
        description="Color Swap List — Prototype 0 Bambu parser"
    )
    ap.add_argument("file")
    ap.add_argument(
        "--manual",
        nargs="*",
        type=int,
        default=[],
        help="User-facing filament numbers assigned to manual infeed",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Display all color swaps, including fully automatic ones",
    )
    ap.add_argument(
        "--json", action="store_true", help="Print normalized JSON"
    )
    args = ap.parse_args()

    job = parse(args.file)
    events = job.color_swap_list(set(args.manual), show_all=args.all)

    if args.json:
        out = to_dict(job)
        out["resolved_interactions"] = [to_dict_event(e) for e in events]
        print(json.dumps(out, indent=2))
        return

    print(f"Format: {job.format}")
    print(f"Layers: {job.total_layers}")
    print("Filaments:")
    for f in job.filaments:
        print(
            f"  #{f.number}: {f.color or '?'} {f.filament_type or ''}".rstrip()
        )

    print(f"\nTransitions: {len(job.transitions)}")
    for e in job.transitions:
        src = f"#{e.source}" if e.source is not None else "?"
        print(
            f"  [{e.sequence}] Layer {e.layer}: {src} -> #{e.destination} (T{e.raw_tool}, line {e.line_number}, origin={e.origin})"
        )

    print("\nColor Swap List:")
    for event in events:
        details = ", ".join(event.interactions)
        src = f"#{event.source}" if event.source is not None else "?"
        print(
            f"  [ ] Layer {event.layer}: Filament {src} -> Filament #{event.destination} ({details})"
        )

    if not events:
        print("  No manual-infeed interactions detected.")

    if job.warnings:
        print("\nWarnings:")
        for w in job.warnings:
            print(f"  - {w}")


def to_dict_event(e):
    return {
        "sequence": e.sequence,
        "layer": e.layer,
        "z_height": e.z_height,
        "source": e.source,
        "destination": e.destination,
        "raw_tool": e.raw_tool,
        "line_number": e.line_number,
        "origin": e.origin,
        "interactions": e.interactions,
    }


if __name__ == "__main__":
    main()
