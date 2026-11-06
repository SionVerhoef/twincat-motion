"""Tests for scripts/nc_error.py. Standard library only."""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'scripts', 'nc_error.py')
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import nc_error  # noqa: E402


class Parse(unittest.TestCase):
    def test_every_notation_of_one_code(self):
        for text in ('0x4550', '0X4550', '16#4550', '16#45_50', '4550', '17744', ' 0x4550 '):
            self.assertEqual(nc_error.parse(text)[0], 0x4550, text)

    def test_letters_mean_hex(self):
        self.assertEqual(nc_error.parse('4b09'), (0x4B09, 'hex'))

    def test_bare_digits_never_ambiguous_in_nc_range(self):
        # Four digits can only be an NC code as hex, five only as decimal.
        for code in list(nc_error.CODES) + [0x4000, 0x4FFF, 0x8100, 0x81FF]:
            self.assertEqual(nc_error.parse('%X' % code)[0], code)
            self.assertEqual(nc_error.parse(str(code)), (code, 'decimal'))

    def test_garbage_rejected(self):
        for text in ('', 'axis', '0xZZ', '45.50'):
            with self.assertRaises(ValueError):
                nc_error.parse(text)


class Lookup(unittest.TestCase):
    def test_curated_code_full_answer(self):
        r = nc_error.lookup('0x4550')
        self.assertTrue(r['known'])
        self.assertEqual(r['family'], 'Controller')
        self.assertIn('lag', r['label'].lower())
        self.assertTrue(r['check'])
        self.assertTrue(r['link'].endswith('513140491.html'))

    def test_feed_enable_directions_not_swapped(self):
        minus, plus = nc_error.lookup('4357'), nc_error.lookup('4358')
        self.assertIn('minus', minus['label'])
        self.assertIn('Enable_Negative', minus['meaning'])
        self.assertIn('plus', plus['label'])
        self.assertIn('Enable_Positive', plus['meaning'])

    def test_enable_missing_vs_drive_not_ready(self):
        self.assertIn('enable', nc_error.lookup('0x4223')['label'].lower())
        drive = nc_error.lookup('0x4225')
        self.assertIn('drive', drive['label'].lower())
        self.assertEqual(drive['handoff'], 'cia402-motion')

    def test_unknown_code_gets_family_never_a_neighbour(self):
        r = nc_error.lookup('0x4359')     # between two curated codes
        self.assertFalse(r['known'])
        self.assertEqual(r['family'], 'Axis')
        self.assertNotIn('label', r)
        self.assertIn('nearby code', r['note'])
        self.assertEqual(r['kind'], 'raised while commanding or moving the axis')

    def test_sub_range_kind(self):
        self.assertIn('parameter', nc_error.lookup('0x4306')['kind'])
        self.assertIn('start-up', nc_error.lookup('0x4342')['kind'])

    def test_mc3_gets_pointer(self):
        r = nc_error.lookup('0x8145')
        self.assertIn('MC3', r['family'])
        self.assertIn('Tc2_MC2 only', r['action'])

    def test_kinematics_out_of_scope(self):
        self.assertIn('outside this skill', nc_error.lookup('0x4C00')['action'])

    def test_not_an_nc_code(self):
        r = nc_error.lookup('1798')
        self.assertNotIn('family', r)
        self.assertIn('ADS', r['note'])

    def test_bus_codes_hand_off(self):
        for code in ('0x4466', '0x4651', '0x4655'):
            self.assertEqual(nc_error.lookup(code)['handoff'], 'ethercat-diagnostics', code)


class Table(unittest.TestCase):
    def test_curated_subset_stays_small(self):
        # Legal rule: a selection of the codes that come up, never the full vendor list.
        self.assertLessEqual(len(nc_error.CODES), 100)

    def test_every_code_in_a_family_with_a_page(self):
        for code in nc_error.CODES:
            _, fam = nc_error.family_of(code)
            self.assertIsNotNone(fam, hex(code))
            self.assertTrue(fam['page'], hex(code))

    def test_entries_complete(self):
        skills = {'cia402-motion', 'ethercat-diagnostics', 'twincat-scope', 'twincat-st'}
        for code, e in nc_error.CODES.items():
            self.assertTrue(e['label'] and e['meaning'] and e['check'], hex(code))
            self.assertIsInstance(e['check'], list, hex(code))
            if 'handoff' in e:
                self.assertIn(e['handoff'], skills, hex(code))

    def test_all_text_is_ascii(self):
        # A legacy Windows console must print every answer unchanged.
        for code in list(nc_error.CODES) + [0x4359, 0x8145, 0x4C00]:
            nc_error.render(nc_error.lookup(hex(code))).encode('ascii')


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def test_text_and_exit_zero(self):
        p = self.run_cli('0x4357')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('Feed enable minus missing', p.stdout)

    def test_json_one_and_many(self):
        one = json.loads(self.run_cli('0x4550', '--json').stdout)
        self.assertEqual(one['code'], '0x4550')
        many = json.loads(self.run_cli('4357', '4358', '--json').stdout)
        self.assertEqual([r['code'] for r in many], ['0x4357', '0x4358'])

    def test_non_nc_code_exits_one(self):
        self.assertEqual(self.run_cli('1798').returncode, 1)

    def test_bad_input_exits_two(self):
        self.assertEqual(self.run_cli('axis').returncode, 2)

    def test_list(self):
        p = self.run_cli('--list', '--json')
        self.assertEqual(len(json.loads(p.stdout)), len(nc_error.CODES))


if __name__ == '__main__':
    unittest.main()
