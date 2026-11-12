"""Tests for scripts/axis_xti.py. Standard library only.

Real axes come from public sample projects (tests/fixtures/xti, see README.md there).
Rules no public axis triggers are tested on small axes written here.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'scripts', 'axis_xti.py')
FIX = os.path.join(HERE, 'fixtures', 'xti')
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import axis_xti  # noqa: E402

HOMING = os.path.join(FIX, 'spt_AxisHoming_Axis1.xti')
EXTSEQ = os.path.join(FIX, 'spt_ExternalSequence_Axis1.xti')
LCLS = os.path.join(FIX, 'lcls_Axis_AxisParameter_Test.xti')
SEAL = os.path.join(FIX, 'packml_VFFS_Seal.xti')

AXIS = '''<?xml version="1.0"?>
<TcSmItem TcVersion="3.1.4024.60" ClassName="{cls}" SubType="1">
  <DataTypes><DataType><Name>NOISE</Name></DataType></DataTypes>
  <Axis Id="1" AxisType="1">
    <Name>__FILENAME__</Name>
    <AxisPara>{axispara}</AxisPara>
    <Encoder Name="Enc" EncType="{enc}"><EncPara {encpara}>{encchild}</EncPara>
      <Vars VarGrpType="1"><Name>Inputs</Name></Vars></Encoder>
    <Drive Name="Drive" DrvType="{drv}"><DrvPara>{drvpara}</DrvPara></Drive>
    <Controller Name="Ctrl" CtrType="1"><CtrPara>{ctrpara}</CtrPara></Controller>
  </Axis>
</TcSmItem>
'''


def axis(**kw):
    """Write a small axis file and load it. Keyword args fill the template."""
    values = dict(cls='CNcAxisDef', axispara='', enc='19', encpara='', encchild='',
                  drv='16', drvpara='', ctrpara='')
    values.update(kw)
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'Axis_X.xti')
    with open(path, 'w') as f:
        f.write(AXIS.format(**values))
    try:
        return axis_xti.load(path)
    finally:
        shutil.rmtree(d)


def rules(ax):
    return sorted(f['rule'] for f in axis_xti.lint(ax))


def run(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)


class Load(unittest.TestCase):
    def test_datatypes_and_vars_are_skipped(self):
        p = axis_xti.load(HOMING)['params']
        self.assertFalse([k for k in p if 'DataType' in k or 'Vars' in k or 'SubVar' in k])
        self.assertEqual(p['Drive@DrvType'], '5')
        self.assertEqual(p['Controller/CtrPara/Observer@BandWidth'], '20')

    def test_placeholder_name_falls_back_to_file_name(self):
        self.assertEqual(axis_xti.load(SEAL)['name'], 'packml_VFFS_Seal')

    def test_version_read(self):
        self.assertEqual(axis_xti.load(LCLS)['version'], '3.1.4026.17')

    def test_lcls_explicit_values(self):
        p = axis_xti.load(LCLS)['params']
        self.assertEqual(p['Encoder/EncPara/SoftEndMinControl@Range'], '4')
        self.assertEqual(p['Controller/CtrPara/PosDiffControl@Time'], '7')
        self.assertEqual(p['AxisPara/Velo@Maximum'], '4000')

    def test_mc3_axis_refused_by_name(self):
        with self.assertRaisesRegex(axis_xti.XtiError, 'MC3'):
            axis(cls='CTComMcAxisDef')

    def test_not_an_axis(self):
        with self.assertRaisesRegex(axis_xti.XtiError, 'not an NC axis'):
            axis(cls='CNcSafTaskDef')

    def test_repeated_siblings_get_an_index(self):
        p = axis(drvpara='<Analog A="1"/><Analog A="2"/>')['params']
        self.assertEqual(p['Drive/DrvPara/Analog[1]@A'], '1')
        self.assertEqual(p['Drive/DrvPara/Analog[2]@A'], '2')


    def test_parameter_changed_is_bookkeeping(self):
        ax = axis(axispara='<ParameterChanged>9</ParameterChanged><Velo FastManual="124"/>'
                           '<ParameterChanged>33</ParameterChanged>')
        self.assertFalse([k for k in ax['params'] if 'ParameterChanged' in k])
        self.assertEqual(ax['bookkeeping'], {'AxisPara/ParameterChanged': ['9', '33']})


class LintRealAxes(unittest.TestCase):
    def test_public_axes_only_get_the_simulation_note(self):
        for path in (HOMING, EXTSEQ, LCLS, SEAL):
            self.assertEqual(rules(axis_xti.load(path)), ['S1'], path)

    def test_real_axis_types_no_simulation_note(self):
        self.assertEqual(rules(axis()), [])


class LintRules(unittest.TestCase):
    def test_v1_maximum_velocity_not_positive(self):
        self.assertIn('V1', rules(axis(axispara='<Velo Maximum="0"/>')))

    def test_v2_speed_above_maximum(self):
        ax = axis(axispara='<Velo Maximum="100" Fast="100" FastManual="120"/>')
        found = [f for f in axis_xti.lint(ax) if f['rule'] == 'V2']
        self.assertEqual(len(found), 1)
        self.assertIn('AxisPara/Velo@FastManual', found[0]['paths'])

    def test_v2_needs_both_values(self):
        # Maximum absent = default, unknown here: no comparison.
        self.assertEqual(rules(axis(axispara='<Velo Fast="99999"/>')), [])

    def test_v3_dynamics(self):
        self.assertEqual(rules(axis(axispara='<Dynamic Acceleration="0" Jerk="-1"/>')),
                         ['V3', 'V3'])
        self.assertEqual(rules(axis(axispara='<Dynamic Jerk="0"/>')), [])

    def test_d2_maximum_above_reference_velocity(self):
        ax = axis(axispara='<Velo Maximum="1000"/>', drvpara='<Analog VeloReferenz="900"/>')
        self.assertEqual(rules(ax), ['D2'])
        ax = axis(axispara='<Velo Maximum="809"/>', drvpara='<Analog VeloReferenz="890"/>')
        self.assertEqual(rules(ax), [])

    def test_d1_reference_velocity_not_positive(self):
        self.assertEqual(rules(axis(drvpara='<Analog VeloReferenz="0"/>')), ['D1'])

    def test_e1_scaling(self):
        self.assertEqual(rules(axis(encpara='ScaleFactorNumerator="0"')), ['E1'])
        self.assertEqual(rules(axis(encpara='ScaleFactorDenominator="0"')), ['E1'])
        self.assertEqual(rules(axis(encpara='ScaleFactorNumerator="-1"')), [])

    def test_e2_soft_limits_crossed(self):
        child = ('<SoftEndMinControl Enable="true" Range="50"/>'
                 '<SoftEndMaxControl Enable="true" Range="50"/>')
        self.assertEqual(rules(axis(encchild=child)), ['E2'])

    def test_e2_only_when_both_enabled(self):
        child = ('<SoftEndMinControl Enable="false" Range="50"/>'
                 '<SoftEndMaxControl Enable="true" Range="10"/>')
        self.assertEqual(rules(axis(encchild=child)), [])

    def test_c1_lag_monitoring_off(self):
        self.assertEqual(rules(axis(ctrpara='<PosDiffControl Enable="false"/>')), ['C1'])
        self.assertEqual(rules(axis(ctrpara='<PosDiffControl Enable="TRUE"/>')), [])

    def test_c2_lag_window(self):
        self.assertEqual(rules(axis(ctrpara='<PosDiffControl Range="0" Time="-0.1"/>')),
                         ['C2', 'C2'])

    def test_non_numeric_values_do_not_crash(self):
        self.assertEqual(rules(axis(axispara='<Velo Maximum="fast" Fast="x"/>')), [])


class Diff(unittest.TestCase):
    def test_known_public_difference(self):
        rows = axis_xti.diff(axis_xti.load(HOMING), axis_xti.load(EXTSEQ))
        self.assertEqual([(r['path'], r['change'], r['new']) for r in rows], [
            ('Encoder/EncPara/SoftEndMaxControl@Enable', 'set', 'true'),
            ('Encoder/EncPara/SoftEndMaxControl@Range', 'set', '100'),
            ('Encoder/EncPara@ScaleFactorNumerator', 'set', '1'),
        ])

    def test_reverse_is_back_to_default(self):
        rows = axis_xti.diff(axis_xti.load(EXTSEQ), axis_xti.load(HOMING))
        self.assertEqual({r['change'] for r in rows}, {'back to default'})

    def test_identical(self):
        self.assertEqual(axis_xti.diff(axis_xti.load(LCLS), axis_xti.load(LCLS)), [])

    def test_changed_value_and_number_formatting(self):
        a = axis(axispara='<Velo Maximum="809.1666666666670"/>')
        b = axis(axispara='<Velo Maximum="809.166666666667"/>')
        self.assertEqual(axis_xti.diff(a, b), [])
        c = axis(axispara='<Velo Maximum="900"/>')
        self.assertEqual(axis_xti.diff(a, c)[0]['change'], 'changed')

    def test_datatypes_noise_ignored(self):
        with open(HOMING, encoding='utf-8') as f:
            text = f.read()
        noisy = text.replace('<BitSize>32</BitSize>', '<BitSize>64</BitSize>', 1)
        self.assertNotEqual(text, noisy)
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'a.xti')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(noisy)
            self.assertEqual(axis_xti.diff(axis_xti.load(HOMING), axis_xti.load(path)), [])
        finally:
            shutil.rmtree(d)


    def test_parameter_changed_never_a_parameter_change(self):
        # Field test A4.2/A4.4: one entry becoming two, or an insertion in the middle,
        # used to show up as removed, re-added and shifted index rows.
        one = axis(axispara='<ParameterChanged>260</ParameterChanged>')
        two = axis(axispara='<ParameterChanged>260</ParameterChanged>'
                            '<ParameterChanged>33</ParameterChanged>'
                            '<OtherSettings AllowMotionCmdToExtSetGenAxis="true"/>')
        self.assertEqual([(r['path'], r['change']) for r in axis_xti.diff(one, two)], [
            ('AxisPara/OtherSettings@AllowMotionCmdToExtSetGenAxis', 'set')])
        self.assertEqual(axis_xti.bookkeeping_diff(one, two), [
            {'path': 'AxisPara/ParameterChanged', 'old': ['260'], 'new': ['260', '33']}])
        a = axis(axispara='<ParameterChanged>260</ParameterChanged>'
                          '<ParameterChanged>33</ParameterChanged>'
                          '<ParameterChanged>32</ParameterChanged>')
        b = axis(axispara='<ParameterChanged>260</ParameterChanged>'
                          '<ParameterChanged>16</ParameterChanged>'
                          '<ParameterChanged>33</ParameterChanged>'
                          '<ParameterChanged>32</ParameterChanged>')
        self.assertEqual(axis_xti.diff(a, b), [])
        self.assertEqual(len(axis_xti.bookkeeping_diff(a, b)), 1)
        self.assertEqual(axis_xti.bookkeeping_diff(b, b), [])

    def test_friendly_name_external_setpoint(self):
        self.assertIn('external setpoint',
                      axis_xti.label('AxisPara/OtherSettings@AllowMotionCmdToExtSetGenAxis'))


class CommandLine(unittest.TestCase):
    def test_lint_folder_clean_exit_and_defaults_note(self):
        r = run('lint', FIX)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('lcls_Axis_AxisParameter_Test', r.stdout)
        self.assertIn('TwinCAT default', r.stdout)

    def test_lint_json(self):
        data = json.loads(run('lint', LCLS, '--json').stdout)
        self.assertIn('default', data['note'])
        self.assertEqual(data['axes'][0]['findings'][0]['rule'], 'S1')

    def test_diff_exit_codes(self):
        self.assertEqual(run('diff', LCLS, LCLS).returncode, 0)
        r = run('diff', HOMING, EXTSEQ)
        self.assertEqual(r.returncode, 1)
        self.assertIn('(default) -> 100', r.stdout)

    def test_show_output_is_ascii(self):
        r = subprocess.run([sys.executable, SCRIPT, 'show', SEAL], stdout=subprocess.PIPE)
        self.assertEqual(r.returncode, 0)
        r.stdout.decode('ascii')  # the degree sign in UnitName must be escaped
        self.assertIn(b'maximum velocity', r.stdout)

    def test_unreadable_file(self):
        self.assertEqual(run('lint', os.path.join(FIX, 'LICENSE-SPT_V4_Samples')).returncode, 2)
        self.assertEqual(run('diff', HOMING, os.path.join(FIX, 'missing.xti')).returncode, 2)


if __name__ == '__main__':
    unittest.main()
