"""Text checks on templates/ that hold without TwinCAT. Standard library only.

They prove no build; CI's twincat-st step and a field test do the rest.
"""
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / 'templates'


def read(name):
    return (TEMPLATES / name).read_text(encoding='utf-8-sig')


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
