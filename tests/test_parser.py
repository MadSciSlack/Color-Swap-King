from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from bambu_parser import parse

ROOT = Path('/mnt/data')


def test_test0_multiple_swaps_same_layer():
    job = parse(ROOT / 'TestCube0-SingleStripe-V1.gcode.3mf')
    assert [t.destination for t in job.transitions] == [2, 1]
    assert [t.layer for t in job.transitions] == [6, 6]
    assert job.filaments[0].number == 1
    assert job.filaments[1].number == 2


def test_test1_noncontiguous_filament_numbering():
    job = parse(ROOT / 'TestCube1-Manual-V1.gcode.3mf')
    assert [t.destination for t in job.transitions] == [6, 1]
    assert [t.layer for t in job.transitions] == [6, 7]
    assert [f.number for f in job.filaments] == [1, 6]


def test_manual_infeed_resolution():
    job = parse(ROOT / 'TestCube1-Manual-V1.gcode.3mf')
    events = job.color_swap_list({6})
    assert len(events) == 2
    assert events[0].interactions == ['Manual Load #6']
    assert events[1].interactions == ['Manual Unload #6']
