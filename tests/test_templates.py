"""Static checks on the homing templates' step machines. Standard library only.

TwinCAT cannot build here, so these read the ST as text. They hold the shape the
templates' comments promise: every step is handled, and a commanded MC_ block never
sees its Execute stay TRUE from one of its steps into the next (that would be no
rising edge, so the second command would never be issued).
"""
import os
import pathlib
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = pathlib.Path(HERE, '..')
TEMPLATES = ROOT / 'templates'

# (FB, its step enum, its params struct)
MACHINES = [('FB_HomePlc', 'E_HomePlcState', 'ST_HomePlcParams'),
            ('FB_HomeNc', 'E_HomeNcState', 'ST_HomeNcParams')]


def read(name):
    return (TEMPLATES / name).read_text(encoding='utf-8-sig')


def body(fb):
    # The FB's own implementation, without its methods.
    text = read(fb + '.TcPOU')
    return re.search(r'<Implementation>\s*<ST><!\[CDATA\[(.*?)\]\]>', text, re.S).group(1)


def enum_members(enum):
    decl = re.search(r'\((.*?)\)\s*DINT', read(enum + '.TcDUT'), re.S).group(1)
    return re.findall(r'^\s*(\w+)\s*:=', decl, re.M)


def struct_fields(struct):
    decl = re.search(r'STRUCT(.*?)END_STRUCT', read(struct + '.TcDUT'), re.S).group(1)
    return set(re.findall(r'^\s*(\w+)\s*:', decl, re.M))


def branches(fb, enum):
    # {step: text of its CASE branch}
    case = re.search(r'CASE eState OF(.*?)\nELSE', body(fb), re.S).group(1)
    parts = re.split(r'^\s{4}%s\.(\w+):\s*$' % enum, case, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def transitions(fb, enum):
    # {step: steps it can go to}. M_Fail and M_StepResult fail to Error, or to Stopping
    # when the branch passes bStop := TRUE (the step may be moving the axis).
    out = {}
    for step, text in branches(fb, enum).items():
        targets = set(re.findall(r'eState\s*:=\s*%s\.(\w+)' % enum, text))
        if 'M_Fail(' in text or 'M_StepResult(' in text:
            targets.add('Error')
            if re.search(r'bStop\s*:=\s*TRUE', text):
                targets.add('Stopping')
        out[step] = targets
    return out


def execute_steps(fb, enum):
    # {instance: steps in which its Execute is TRUE}
    out = {}
    for inst, expr in re.findall(r'^(fb\w+)\(Axis := Axis,\s*Execute := (.*?),\s*\n\s*\w+ :=',
                                 body(fb), re.M | re.S):
        out[inst] = set(re.findall(r'eState = %s\.(\w+)' % enum, expr))
    return out


class StepMachines(unittest.TestCase):
    def test_every_step_has_a_branch(self):
        for fb, enum, _ in MACHINES:
            self.assertEqual(sorted(branches(fb, enum)), sorted(enum_members(enum)), fb)

    def test_every_target_is_a_step(self):
        for fb, enum, _ in MACHINES:
            steps = set(enum_members(enum))
            for step, targets in transitions(fb, enum).items():
                self.assertLessEqual(targets, steps, (fb, step))

    def test_execute_is_a_fresh_edge_on_every_entry(self):
        # No step in which a block's Execute is TRUE leads straight to another such step.
        for fb, enum, _ in MACHINES:
            moves = transitions(fb, enum)
            found = execute_steps(fb, enum)
            self.assertTrue(found, fb)
            for inst, steps in found.items():
                for step in steps:
                    self.assertFalse(moves[step] & steps,
                                     '%s.%s: %s -> %s' % (fb, inst, step, moves[step] & steps))

    def test_params_named_in_code_exist(self):
        # Every stRun./stParams. field in the FB, and every stHomePlc. field written in the
        # example or the field test, is declared in the params struct.
        for fb, _, struct in MACHINES:
            fields = struct_fields(struct)
            used = set(re.findall(r'\bst(?:Run|Params)\.(\w+)', read(fb + '.TcPOU')))
            self.assertLessEqual(used, fields, fb)
        fields = struct_fields('ST_HomePlcParams')
        for path in [TEMPLATES / 'PRG_AxisExample.TcPOU',
                     *sorted((ROOT / 'evals' / 'field-test').glob('*.st'))]:
            text = path.read_text(encoding='utf-8-sig')
            self.assertLessEqual(set(re.findall(r'\bstHomePlc\.(\w+)', text)), fields, path.name)

    def test_home_plc_options_default_off(self):
        # The two-speed search and the unhoming are opt-in: a struct that never names them
        # gets the plain run. tRunTimeout must default to a value, or M_ParamsOk refuses.
        decl = read('ST_HomePlcParams.TcDUT')
        self.assertRegex(decl, r'\n\s*fSlowVelocity\s*:\s*LREAL;')
        self.assertRegex(decl, r'\n\s*bUnhomeOnAxisError\s*:\s*BOOL;')
        self.assertRegex(decl, r'\n\s*tRunTimeout\s*:\s*TIME\s*:=\s*T#\d')
        self.assertRegex(read('FB_HomePlc.TcPOU'), r'bSearchLimitOk\s*:\s*BOOL\s*:=\s*TRUE;')


if __name__ == '__main__':
    unittest.main()
