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
TWO_ENC = os.path.join(HERE, 'fixtures', 'handwritten', 'Axis_X_two_encoders.xti')

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


class MultiEncoder(unittest.TestCase):
    """An axis with two encoders (hand-written fixture): Enc is sound, Enc_2 is not."""

    def test_encoders_keyed_by_name(self):
        p = axis_xti.load(TWO_ENC)['params']
        self.assertEqual(p['Encoder[Enc]/EncPara@ScaleFactorDenominator'], '1')
        self.assertEqual(p['Encoder[Enc_2]/EncPara@ScaleFactorDenominator'], '0')

    def test_encoder_rules_run_on_every_encoder(self):
        found = [f for f in axis_xti.lint(axis_xti.load(TWO_ENC)) if f['rule'] in ('E1', 'E2')]
        self.assertEqual(sorted(f['rule'] for f in found), ['E1', 'E2'])
        for f in found:
            self.assertTrue(all(p.startswith('Encoder[Enc_2]/') for p in f['paths']), f)
            self.assertIn('Enc_2', f['message'])

    def test_single_encoder_message_unchanged(self):
        f = axis_xti.lint(axis(encpara='ScaleFactorNumerator="0"'))[0]
        self.assertEqual(f['paths'], ['Encoder/EncPara@ScaleFactorNumerator'])
        self.assertTrue(f['message'].startswith('Encoder scaling numerator is 0'))

    def test_diff_pairs_encoders_by_name_not_position(self):
        with open(TWO_ENC, encoding='utf-8') as f:
            text = f.read()
        start, end = text.index('\t\t<Encoder Name="Enc"'), text.index('\t\t<Encoder Name="Enc_2"')
        stop = text.index('</Encoder>', end) + len('</Encoder>\n')
        swapped = text[:start] + text[end:stop] + text[start:end] + text[stop:]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'Axis_X.xti')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(swapped)
            self.assertEqual(axis_xti.diff(axis_xti.load(TWO_ENC), axis_xti.load(path)), [])
        finally:
            shutil.rmtree(d)

    def test_labels_apply_to_named_encoders(self):
        self.assertIn('soft limit minimum',
                      axis_xti.label('Encoder[Enc_2]/EncPara/SoftEndMinControl@Range'))


# Shaped like ProduceXml output as described in references/config-changes.md (root
# TreeItem, values as element text, groups renamed to ...Param, defaults listed). Written
# here, not captured from XAE.
PRODUCED = '''<?xml version="1.0"?>
<TreeItem>
  <ItemName>Axis_X</ItemName>
  <NcAxisDef>
    <AxisParam>
      <Velo><Maximum>2000</Maximum><Fast>1000</Fast><FastManual>600</FastManual></Velo>
      <Dynamic><Acceleration>1500</Acceleration></Dynamic>
    </AxisParam>
    <Encoder>
      <EncParam>
        <ScaleFactorNumerator>0.0001</ScaleFactorNumerator>
        <SoftEndMaxControl><Enable>false</Enable><Range>0</Range></SoftEndMaxControl>
      </EncParam>
    </Encoder>
    <Controller><CtrParam><PosDiffControl><Range>5</Range></PosDiffControl></CtrParam>
    </Controller>
  </NcAxisDef>
</TreeItem>
'''


def produced(text=PRODUCED):
    return axis_xti.ET.fromstring(text)


class AiChanges(unittest.TestCase):
    def test_paths_map_to_produced_layout(self):
        self.assertEqual(axis_xti.produced_path('AxisPara/Velo@FastManual'),
                         '/TreeItem/NcAxisDef/AxisParam/Velo/FastManual')
        self.assertEqual(axis_xti.produced_path('Controller/CtrPara/PosDiffControl@Enable'),
                         '/TreeItem/NcAxisDef/Controller/CtrParam/PosDiffControl/Enable')
        self.assertEqual(axis_xti.produced_path('Encoder/EncPara/TimeComp@EncDelayCycles'),
                         '/TreeItem/NcAxisDef/Encoder/EncParam/TimeComp/EncDelayCycles')

    def test_old_value_comes_from_produced_xml_defaults_included(self):
        # HOMING -> EXTSEQ sets three parameters that were at their default in the .xti;
        # the produced XML holds their current value, so the CSV can state it.
        rows = axis_xti.diff(axis_xti.load(HOMING), axis_xti.load(EXTSEQ))
        out, problems, notes = axis_xti.ai_changes(rows, produced())
        self.assertEqual(problems, [])
        self.assertEqual(notes, [])
        self.assertEqual(out, [
            ('/TreeItem/NcAxisDef/Encoder/EncParam/SoftEndMaxControl/Enable', 'false',
             'true'),
            ('/TreeItem/NcAxisDef/Encoder/EncParam/SoftEndMaxControl/Range', '0', '100'),
            ('/TreeItem/NcAxisDef/Encoder/EncParam/ScaleFactorNumerator', '0.0001', '1'),
        ])

    def test_target_differs_from_old_xti_is_noted(self):
        a = axis(axispara='<Velo FastManual="500"/>')
        b = axis(axispara='<Velo FastManual="700"/>')
        out, problems, notes = axis_xti.ai_changes(axis_xti.diff(a, b), produced())
        self.assertEqual(out, [('/TreeItem/NcAxisDef/AxisParam/Velo/FastManual', '600',
                                '700')])
        self.assertEqual(problems, [])
        self.assertEqual(len(notes), 1)
        self.assertIn('500', notes[0])

    def test_unresolvable_rows_are_problems(self):
        a = axis(axispara='<Velo RefSearch="10"/><Dynamic Acceleration="900"/>',
                 drvpara='<Analog A="1"/><Analog A="2"/>')
        b = axis(axispara='<Velo RefSearch="20"/>', drvpara='<Analog A="1"/><Analog A="3"/>')
        out, problems, notes = axis_xti.ai_changes(axis_xti.diff(a, b), produced())
        text = '\n'.join(problems)
        self.assertEqual(len(problems), 3, text)
        self.assertIn('RefSearch', text)          # not in the produced XML
        self.assertIn('Acceleration', text)       # back to default: value unknown
        self.assertIn('Analog[2]', text)          # repeated element: position unreliable

    def test_group_is_not_a_value(self):
        rows = [{'path': 'AxisPara@Velo', 'change': 'set', 'old': None, 'new': '1'}]
        self.assertIn('group', axis_xti.ai_changes(rows, produced())[1][0])

    def test_not_produced_xml(self):
        with self.assertRaises(axis_xti.XtiError):
            axis_xti.ai_changes([], produced('<TcSmItem/>'))


PROJ = os.path.join(HERE, 'fixtures', 'tsproj')


def tsproj_in(folder):
    return os.path.join(folder, [f for f in os.listdir(folder) if f.endswith('.tsproj')][0])


def project(folder):
    """Load a project folder. Returns (result, sorted (rule, axis) pairs)."""
    pr = axis_xti.load_project(tsproj_in(folder))
    return pr, sorted((f['rule'], f['axis'] or '') for f in pr['findings'])


def edit(path, old, new):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if old not in text:
        raise AssertionError('%r not in %s' % (old, path))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text.replace(old, new))


class ProjectRealProjects(unittest.TestCase):
    """Public projects (tests/fixtures/tsproj, see README.md there)."""

    def test_clean_inline_project(self):
        pr, found = project(os.path.join(PROJ, 'geardemo'))
        self.assertEqual(found, [])
        self.assertEqual([a['name'] for a in pr['axes']], ['Axis 1', 'Axis 2'])
        self.assertTrue(pr['axes'][0]['axis']['path'].endswith(', inline'))

    def test_separate_files_drive_links_in_axis_files(self):
        pr, found = project(os.path.join(PROJ, 'amr_demo'))
        self.assertEqual(found, [('L5', 'Lift'), ('L7', 'WheelLeft'), ('L7', 'WheelRight')])
        self.assertEqual([a['name'] for a in pr['axes']], ['WheelLeft', 'WheelRight'])
        l5 = [f for f in pr['findings'] if f['rule'] == 'L5'][0]
        self.assertEqual(l5['level'], 'info')  # axis no longer exists: leftover, not a fault

    def test_unlinked_torque_and_speed_limits(self):
        pr, found = project(os.path.join(PROJ, 'i950_dual_axis'))
        self.assertEqual(found, [('L6', 'Axis_M'), ('L6', 'Axis_S'),
                                 ('L7', 'Axis_M'), ('L7', 'Axis_S')])
        l6 = [f for f in pr['findings'] if f['rule'] == 'L6'][0]
        self.assertEqual(l6['level'], 'warning')
        for entry in ('Torque Limits^Positive torque limit', 'Torque Limits^Negative torque '
                      'limit', 'Speed Limits^Speed limitation: Upper speed limit'):
            self.assertIn(entry, l6['message'])
        self.assertNotIn('Offset speed', l6['message'])  # not a limit: L7

    def test_channel_prefixed_link_names_count_as_linked(self):
        pr, found = project(os.path.join(PROJ, 'triamec_ethercat'))
        self.assertEqual(found, [('L7', 'Axis 1')])
        msg = pr['findings'][0]['message']
        self.assertIn('MainOutputs^Auxiliary Byte', msg)
        self.assertNotIn('Control Word', msg)
        self.assertIn('Axis 1, Axis 2', msg)  # one two-channel drive, reported once

    def test_drive_and_encoder_linked_to_plc(self):
        self.assertEqual(project(os.path.join(PROJ, 'triamec_trialink'))[1], [])

    def test_xts_mover_linked_to_tcom_object(self):
        found = project(os.path.join(PROJ, 'xts_open'))[1]
        self.assertNotIn(('L1', 'Mover Axis 1'), found)
        self.assertNotIn(('L2', 'Mover Axis 1'), found)
        self.assertEqual(found, [('L3', 'Axis 1'), ('L3', 'Axis 2')])


class ProjectRules(unittest.TestCase):
    """Rules no public project triggers, on edited copies of a public project."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def copy(self, name):
        dst = os.path.join(self.tmp, name)
        shutil.copytree(os.path.join(PROJ, name), dst)
        return dst

    def amr(self, path=''):
        return os.path.join(self.tmp, 'amr_demo', path)

    def test_p1_axis_file_missing(self):
        self.copy('amr_demo')
        os.remove(self.amr('_Config/NC/Axes/WheelLeft.xti'))
        pr, found = project(self.amr())
        self.assertIn(('P1', ''), found)
        self.assertIn('WheelLeft.xti', pr['findings'][0]['message'])

    def test_p1_nc_file_missing(self):
        self.copy('amr_demo')
        os.remove(self.amr('_Config/NC/NC.xti'))
        self.assertEqual(project(self.amr())[1], [('P1', '')])

    def test_file_names_resolve_ignoring_case(self):
        self.copy('amr_demo')
        edit(self.amr('_Config/NC/NC.xti'), 'File="WheelLeft.xti"', 'File="wheelleft.XTI"')
        self.assertNotIn('P1', [r for r, _ in project(self.amr())[1]])

    def test_p2_axis_file_not_listed(self):
        self.copy('amr_demo')
        shutil.copy(self.amr('_Config/NC/Axes/WheelLeft.xti'),
                    self.amr('_Config/NC/Axes/Spare.xti'))
        pr, found = project(self.amr())
        self.assertIn(('P2', ''), found)
        self.assertTrue(any('Spare.xti' in f['message'] for f in pr['findings']))

    def test_p3_duplicate_axis_id(self):
        self.copy('amr_demo')
        edit(self.amr('_Config/NC/NC.xti'), 'Id="3"', 'Id="2"')
        self.assertIn(('P3', ''), project(self.amr())[1])

    def test_l1_l2_drive_and_encoder_not_linked(self):
        self.copy('amr_demo')
        path = self.amr('_Config/NC/Axes/WheelLeft.xti')
        root = axis_xti.ET.parse(path)
        root.getroot().remove(root.getroot().find('Mappings'))
        root.write(path)
        found = project(self.amr())[1]
        self.assertIn(('L1', 'WheelLeft'), found)
        self.assertIn(('L2', 'WheelLeft'), found)
        self.assertNotIn(('L1', 'WheelRight'), found)

    def test_l2_second_encoder_not_linked(self):
        self.copy('amr_demo')
        path = self.amr('_Config/NC/Axes/WheelLeft.xti')
        edit(path, '\t\t<Drive Name="Drive"',
             '\t\t<Encoder Name="Enc_2" EncType="19"><EncPara/></Encoder>\n'
             '\t\t<Drive Name="Drive"')
        pr, found = project(self.amr())
        self.assertIn(('L2', 'WheelLeft'), found)
        l2 = [f for f in pr['findings'] if f['rule'] == 'L2']
        self.assertEqual(len(l2), 1)  # Enc is linked, Enc_2 is not
        self.assertIn('Enc_2', l2[0]['message'])

    def test_l1_follows_a_renamed_drive_sub_item(self):
        self.copy('geardemo')
        path = tsproj_in(os.path.join(self.tmp, 'geardemo'))
        edit(path, '<Drive Name="Drive"', '<Drive Name="Servo"')
        found = project(os.path.join(self.tmp, 'geardemo'))[1]
        self.assertIn(('L1', 'Axis 1'), found)  # links still say Drive^: not this drive
        edit(path, 'VarA="Drive^', 'VarA="Servo^')
        self.assertEqual(project(os.path.join(self.tmp, 'geardemo'))[1], [])

    def test_l3_l4_axis_renamed_after_linking(self):
        self.copy('amr_demo')
        os.rename(self.amr('_Config/NC/Axes/WheelLeft.xti'),
                  self.amr('_Config/NC/Axes/WheelL.xti'))
        edit(self.amr('_Config/NC/NC.xti'), 'File="WheelLeft.xti"', 'File="WheelL.xti"')
        pr, found = project(self.amr())
        self.assertIn(('L4', 'WheelLeft'), found)   # PLC links still name the old axis
        self.assertIn(('L3', 'WheelL'), found)
        self.assertNotIn(('L1', 'WheelL'), found)   # drive links travel with the axis file

    def test_l5_unrestored_link_to_an_existing_axis(self):
        self.copy('amr_demo')
        plc = self.amr('_Config/PLC/PLC Instance.xti')
        edit(plc, 'Axes^Lift">', 'Axes^WheelLeft">')
        edit(plc, '<OwnerB Name="TINC^NC-Task 1 SAF^Axes^WheelLeft">\n\t\t\t\t<Link VarA="PlcTask '
             'Inputs^MAIN.AmrModule.WheelLeftRef.NcToPlc" VarB="Outputs^ToPlc" />\n\t\t\t\t<Link '
             'VarA="PlcTask Outputs^MAIN.AmrModule.WheelLeftRef.PlcToNc" VarB="Inputs^FromPlc" />'
             '\n\t\t\t</OwnerB>', '')
        pr, found = project(self.amr())
        self.assertIn(('L5', 'WheelLeft'), found)
        l5 = [f for f in pr['findings'] if f['rule'] == 'L5'][0]
        self.assertEqual(l5['level'], 'warning')
        self.assertIn('Inputs^FromPlc', l5['message'])

    def test_l5_quiet_when_the_link_was_made_again(self):
        self.copy('amr_demo')
        edit(self.amr('_Config/PLC/PLC Instance.xti'), 'Axes^Lift">', 'Axes^WheelLeft">')
        self.assertNotIn('L5', [r for r, _ in project(self.amr())[1]])

    def test_l8_linked_box_not_in_io_tree(self):
        self.copy('amr_demo')
        edit(self.amr('_Config/NC/Axes/WheelLeft.xti'), 'Motion 1 (ELM7231-9018)',
             'Motion 9 (ELM7231-9018)')
        self.assertIn(('L8', 'WheelLeft'), project(self.amr())[1])

    def test_mc3_axes_are_not_nc_axes(self):
        d = os.path.join(self.tmp, 'mc3')
        os.makedirs(d)
        with open(os.path.join(d, 'P.tsproj'), 'w') as f:
            f.write('<TcSmProject><Project><Motion><MC File="MC Project1.xti"/>'
                    '<NC><SafTask><Name>NC-Task 1 SAF</Name></SafTask></NC></Motion></Project>'
                    '<Mappings><OwnerA Name="TIPC^PLC^PLC Instance">'
                    '<OwnerB Name="TINC^MC Project1^Axes^Master">'
                    '<Link VarA="x" VarB="Inputs^FromPlc"/></OwnerB></OwnerA></Mappings>'
                    '</TcSmProject>')
        pr, found = project(d)
        self.assertEqual(found, [])
        self.assertIn('MC3', ' '.join(pr['notes']))

    def test_limit_by_name_or_cia402_index(self):
        def entry(name, index):
            return axis_xti.ET.fromstring('<Entry Name="%s" Index="%s"/>' % (name, index))
        self.assertTrue(axis_xti.is_limit(entry('Torque limitation', '#x7010')))
        self.assertTrue(axis_xti.is_limit(entry('Max torque', '#x6072')))
        self.assertTrue(axis_xti.is_limit(entry('Drehmoment', '#x68e1')))  # channel 2
        self.assertFalse(axis_xti.is_limit(entry('Output', '#x70e0')))     # digital output
        self.assertFalse(axis_xti.is_limit(entry('Offset torque', '#x60b2')))


class CommandLine(unittest.TestCase):
    def test_lint_project_folder(self):
        r = run('lint', os.path.join(PROJ, 'i950_dual_axis'))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('WARNING L6 [Axis_M]', r.stdout)
        self.assertIn('Axis_M  (', r.stdout)   # per-axis lint of inline axes follows
        r.stdout.encode('ascii')

    def test_lint_clean_project_exit_0(self):
        r = run('lint', tsproj_in(os.path.join(PROJ, 'geardemo')))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('no project findings', r.stdout)

    def test_lint_project_json(self):
        data = json.loads(run('lint', os.path.join(PROJ, 'amr_demo'), '--json').stdout)
        self.assertEqual(data['axes'], [])
        pr = data['projects'][0]
        self.assertEqual([a['name'] for a in pr['axes']], ['WheelLeft', 'WheelRight'])
        self.assertIn('L5', [f['rule'] for f in pr['findings']])

    def test_diff_table(self):
        r = run('diff', HOMING, EXTSEQ, '--table')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn('| `.xti` path (to check) | Old | New | Why |', r.stdout)
        self.assertIn('| spt_ExternalSequence_Axis1 | encoder scaling numerator | '
                      '`Encoder/EncPara@ScaleFactorNumerator` | default | 1 |  |', r.stdout)
        r = run('diff', EXTSEQ, HOMING, '--table')
        self.assertIn('| 100 | default (value not known to this tool) |', r.stdout)

    def test_diff_ai_csv_written(self):
        d = tempfile.mkdtemp()
        try:
            xml, csv_path = os.path.join(d, 'p.xml'), os.path.join(d, 'changes.csv')
            with open(xml, 'w') as f:
                f.write(PRODUCED)
            r = run('diff', HOMING, EXTSEQ, '--ai-csv', xml, csv_path)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(csv_path, encoding='utf-8-sig') as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0], 'XPath,Old,New')
            self.assertIn('/TreeItem/NcAxisDef/Encoder/EncParam/ScaleFactorNumerator,'
                          '0.0001,1', lines)
            self.assertEqual(len(lines), 4)
        finally:
            shutil.rmtree(d)

    def test_diff_ai_csv_all_or_nothing(self):
        d = tempfile.mkdtemp()
        try:
            xml, csv_path = os.path.join(d, 'p.xml'), os.path.join(d, 'changes.csv')
            with open(xml, 'w') as f:
                f.write(PRODUCED)
            r = run('diff', EXTSEQ, HOMING, '--ai-csv', xml, csv_path)  # back to default
            self.assertEqual(r.returncode, 2)
            self.assertFalse(os.path.exists(csv_path))
            self.assertIn('nothing written', r.stdout)
        finally:
            shutil.rmtree(d)

    def test_diff_formats_exclusive(self):
        self.assertEqual(run('diff', LCLS, LCLS, '--table', '--json').returncode, 2)

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
