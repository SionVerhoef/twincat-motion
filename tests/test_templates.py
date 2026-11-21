"""Text checks on templates/ that hold without TwinCAT. Standard library only.

TwinCAT cannot build here, so these read the ST and XML as text; CI's twincat-st step
and a field test do the rest. The step-machine checks hold the shape the homing
templates' comments promise: every step is handled, and a commanded MC_ block never
sees its Execute stay TRUE from one of its steps into the next (that would be no
rising edge, so the second command would never be issued).
"""

import os
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET

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


class Files(unittest.TestCase):
    def test_well_formed_with_unique_ids(self):
        # A copied GUID makes XAE treat two objects as one (templates/README.md).
        seen = {}
        for path in sorted(TEMPLATES.glob('*.Tc*')):
            root = ET.fromstring(path.read_text(encoding='utf-8-sig'))
            for el in root.iter():
                gid = el.get('Id')
                if gid:
                    self.assertNotIn(gid, seen, f'{path.name} reuses an Id of {seen.get(gid)}')
                    seen[gid] = path.name


class AxisWrapper(unittest.TestCase):
    def setUp(self):
        self.fb = read('FB_Axis.TcPOU')

    def test_every_command_has_a_result_path(self):
        # A command the body never compares eCmd against would leave bBusy,
        # bDone and bCommandAborted silent for it: the gap a replaced, never
        # issued move used to fall into.
        enum = read('E_AxisCmd.TcDUT')
        members = re.findall(r'^\s*(\w+)\s*:=\s*\d+', enum, re.M)
        self.assertIn('Jog', members)
        for name in members:
            if name != 'None':
                self.assertRegex(self.fb, rf'eCmd = E_AxisCmd\.{name}\b', name)

    def test_public_interface_documented(self):
        # templates/README.md lists every method and property a caller can use.
        readme = (TEMPLATES / 'README.md').read_text(encoding='utf-8')
        public = re.findall(r'<(?:Method|Property) Name="(\w+)"', self.fb)
        public = [n for n in public if not n.startswith('M_')]
        self.assertIn('ReleaseStop', public)
        self.assertIn('fActPosition', public)
        for name in public:
            self.assertIn(f'`{name}`', readme, name)

    def test_private_helpers_are_private(self):
        for name, head in re.findall(r'<Method Name="(M_\w+)"[^>]*>\s*<Declaration>'
                                     r'<!\[CDATA\[(METHOD[^\r\n]*)', self.fb):
            self.assertIn('PRIVATE', head, name)


if __name__ == '__main__':
    unittest.main()
