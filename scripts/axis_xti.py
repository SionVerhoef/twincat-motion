#!/usr/bin/env python3
"""Read, lint and diff TwinCAT NC axis files (_Config/NC/Axes/*.xti, classic NC / Tc2_MC2).

    axis_xti.py show  Axis1.xti              the parameters this axis sets explicitly
    axis_xti.py lint  _Config/NC/Axes        check every NC axis file under a folder
    axis_xti.py diff  old.xti new.xti        what changed between two versions of an axis
    axis_xti.py diff  old.xti new.xti --table
                                             the change as a parameter-change table
    axis_xti.py diff  old.xti new.xti --ai-csv produced.xml changes.csv
                                             the change as changes.csv for axis-change.ps1
    axis_xti.py lint  Axis1.xti --json       the same result for a program

To diff against git history, write the old version to a file first:
    git show HEAD~1:"_Config/NC/Axes/Axis 1.xti" > old.xti

An NC axis file stores only the parameters that differ from the TwinCAT defaults. This
tool does not carry a table of default values, so:
  - an absent parameter is at its default, whatever that is on your TwinCAT build;
  - lint checks explicit values only, and checks a pair of parameters only when both
    are explicit;
  - diff reports a parameter that disappeared as "back to default".
The output says so every time, so nobody reads a clean result as a full audit.

What is compared: the attributes of the Axis element and its AxisPara, Encoder, Drive and
Controller sub-trees. The DataTypes block (most of the file) and the Vars blocks (I/O
process-image structure) are skipped: they describe types, not settings.

ParameterChanged elements are kept apart as bookkeeping. XAE writes them into AxisPara
and EncPara when a parameter is changed in its UI, and drops some or all of them on later
saves; they record that something was edited, not a setting. show hides them (it prints
how many there are), and diff reports them on one line per group, compared as a set of
values, never as parameter changes and never by position.

The tool never writes an .xti file; change an axis in XAE, through the Automation
Interface, or from a parameter-change table a person applies. diff can write those last
two for a person to review: --table prints the table, --ai-csv writes the changes.csv that
the axis-change.ps1 script in references/config-changes.md applies. --ai-csv needs that
script's produce-pass XML of the target axis: the produced XML names values differently
from the .xti and lists defaults too, so each row is looked up in it and its old value is
read from it. If any row cannot be found there, nothing is written. Running the script
stays with the person.

Standard library only, so it runs on an engineering PC with nothing but Python 3.8.
Output is ASCII so a legacy Windows console prints it unchanged.
"""
import argparse
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

NC2_CLASS = 'CNcAxisDef'
MC3_CLASS = 'CTComMcAxisDef'
SKIPPED_TAGS = ('DataTypes', 'Vars')
BOOKKEEPING_TAG = 'ParameterChanged'

DEFAULTS_NOTE = ('An .xti stores only non-default parameters. Absent ones are at their '
                 'TwinCAT default, which this tool does not know: it checks explicit '
                 'values only, and a pair only when both are explicit.')

# Plain-language names for the parameter paths seen in public NC2 axis files. A path
# missing here is still read, compared and printed, just under its raw name.
LABELS = {
    'AxisPara/General@UnitName': 'unit',
    'AxisPara/Velo@Maximum': 'maximum velocity',
    'AxisPara/Velo@Fast': 'rapid traverse velocity',
    'AxisPara/Velo@FastManual': 'manual velocity, fast',
    'AxisPara/Velo@SlowManual': 'manual velocity, slow',
    'AxisPara/Velo@RefSearch': 'homing velocity towards the cam',
    'AxisPara/Velo@RefSync': 'homing velocity off the cam',
    'AxisPara/Dynamic@Acceleration': 'default acceleration',
    'AxisPara/Dynamic@Deceleration': 'default deceleration',
    'AxisPara/Dynamic@Jerk': 'default jerk',
    'AxisPara/Dynamic@DelayTime': 'axis dead time compensation, s',
    'AxisPara/OtherSettings@AllowMotionCmdToSlave': 'allow motion commands to slave axis',
    'AxisPara/OtherSettings@AllowMotionCmdToExtSetGenAxis':
        'allow motion commands to external setpoint axis',
    'AxisPara/PositionAreaControl@Range': 'position range monitoring window',
    'Encoder/EncPara@ScaleFactorNumerator': 'encoder scaling numerator',
    'Encoder/EncPara@ScaleFactorDenominator': 'encoder scaling denominator',
    'Encoder/EncPara@Offset': 'encoder position offset',
    'Encoder/EncPara/SoftEndMinControl@Enable': 'soft limit minimum enabled',
    'Encoder/EncPara/SoftEndMinControl@Range': 'soft limit minimum',
    'Encoder/EncPara/SoftEndMaxControl@Enable': 'soft limit maximum enabled',
    'Encoder/EncPara/SoftEndMaxControl@Range': 'soft limit maximum',
    'Encoder/EncPara/TimeComp@TimeCompMode': 'encoder time compensation mode',
    'Encoder/EncPara/TimeComp@EncDelayCycles': 'encoder delay in cycles',
    'Encoder/EncPara/TimeComp@AdditionalTimeShift': 'additional encoder delay',
    'Drive/DrvPara/TimeComp@TimeCompMode': 'drive time compensation mode',
    'Drive/DrvPara/TimeComp@TaskDelayCycles': 'drive task delay in cycles',
    'Drive/DrvPara/TimeComp@DriveDelayCycles': 'drive delay in cycles',
    'Drive/DrvPara/Analog@VeloReferenz': 'reference velocity',
    'Controller/CtrPara/PosDiffControl@Enable': 'position lag monitoring enabled',
    'Controller/CtrPara/PosDiffControl@Range': 'position lag monitoring window',
    'Controller/CtrPara/PosDiffControl@Time': 'position lag monitoring filter time',
}

VELO = 'AxisPara/Velo@'
SPEEDS_BELOW_MAX = ('Fast', 'FastManual', 'SlowManual', 'RefSearch', 'RefSync')


class XtiError(Exception):
    """The file is not a readable NC2 axis file."""


def ascii_text(s):
    return s.encode('ascii', 'backslashreplace').decode('ascii')


# --- Reading ------------------------------------------------------------------------

def load(path):
    """Parse an NC2 axis .xti. Returns {'version', 'name', 'params': {path: value}}."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise XtiError('%s: cannot read as XML (%s)' % (path, exc))
    cls = root.get('ClassName')
    if cls == MC3_CLASS:
        raise XtiError('%s: an MC3 (Tc3_Mc3) axis. This tool reads classic NC2 axes only.'
                       % path)
    axis = root.find('Axis')
    if cls != NC2_CLASS or axis is None:
        raise XtiError('%s: not an NC axis file (ClassName=%s)' % (path, cls))
    params, book = {}, {}
    _flatten(axis, '', params, book)
    name = params.get('Name')
    if not name or name == '__FILENAME__':
        name = os.path.splitext(os.path.basename(path))[0]
    return {'path': path, 'version': root.get('TcVersion'), 'name': name, 'params': params,
            'bookkeeping': book}


def _flatten(elem, prefix, out, book):
    for key, value in elem.attrib.items():
        out[prefix + '@' + key] = value
    text = (elem.text or '').strip()
    if text and prefix:
        out[prefix] = text
    for child in elem:
        if child.tag == BOOKKEEPING_TAG:
            book.setdefault(prefix + '/' + child.tag, []).append((child.text or '').strip())
    children = [c for c in elem if c.tag not in SKIPPED_TAGS and c.tag != BOOKKEEPING_TAG]
    tags = [c.tag for c in children]
    count = {}
    for child in children:
        count[child.tag] = count.get(child.tag, 0) + 1
        tag = child.tag if tags.count(child.tag) == 1 else '%s[%d]' % (child.tag,
                                                                        count[child.tag])
        _flatten(child, (prefix + '/' if prefix else '') + tag, out, book)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def same(a, b):
    if a == b:
        return True
    na, nb = number(a), number(b)
    if na is not None and nb is not None:
        return na == nb
    return a is not None and b is not None and a.lower() == b.lower()


def label(path):
    return path + (' (%s)' % LABELS[path] if path in LABELS else '')


# --- Lint ---------------------------------------------------------------------------

def lint(axis):
    """Return findings for one loaded axis: dicts with rule, level, path(s), message."""
    p = axis['params']
    found = []

    def add(rule, level, paths, message):
        found.append({'rule': rule, 'level': level, 'paths': paths, 'message': message})

    def num(path):
        return number(p.get(path))

    vmax = num(VELO + 'Maximum')
    if vmax is not None and vmax <= 0:
        add('V1', 'error', [VELO + 'Maximum'],
            'Maximum velocity is %s. It must be positive.' % p[VELO + 'Maximum'])
    if vmax is not None and vmax > 0:
        for name in SPEEDS_BELOW_MAX:
            v = num(VELO + name)
            if v is not None and v > vmax:
                add('V2', 'warning', [VELO + name, VELO + 'Maximum'],
                    '%s %s is above the maximum velocity %s; moves at it are rejected '
                    'or limited.' % (LABELS[VELO + name].capitalize(), p[VELO + name],
                                     p[VELO + 'Maximum']))

    for name in ('Acceleration', 'Deceleration'):
        path = 'AxisPara/Dynamic@' + name
        v = num(path)
        if v is not None and v <= 0:
            add('V3', 'error', [path], 'Default %s is %s. It must be positive.'
                % (name.lower(), p[path]))
    jerk = num('AxisPara/Dynamic@Jerk')
    if jerk is not None and jerk < 0:
        add('V3', 'error', ['AxisPara/Dynamic@Jerk'], 'Default jerk is negative.')

    vref_path = 'Drive/DrvPara/Analog@VeloReferenz'
    vref = num(vref_path)
    if vref is not None and vref <= 0:
        add('D1', 'error', [vref_path], 'Reference velocity is %s. It must be positive.'
            % p[vref_path])
    elif vref is not None and vmax is not None and vmax > vref:
        add('D2', 'warning', [VELO + 'Maximum', vref_path],
            'Maximum velocity %s is above the reference velocity %s. With a velocity-'
            'interface drive the set point saturates at 100 %% output there and the '
            'position lag grows; keep the maximum below the reference velocity. '
            'Does not apply to a position-interface (CSP) drive.'
            % (p[VELO + 'Maximum'], p[vref_path]))

    num_path = 'Encoder/EncPara@ScaleFactorNumerator'
    den_path = 'Encoder/EncPara@ScaleFactorDenominator'
    if num(num_path) == 0:
        add('E1', 'error', [num_path], 'Encoder scaling numerator is 0: every position '
            'reads as 0.')
    den = num(den_path)
    if den is not None and den <= 0:
        add('E1', 'error', [den_path], 'Encoder scaling denominator is %s. It must be '
            'positive.' % p[den_path])

    smin, smax = 'Encoder/EncPara/SoftEndMinControl@', 'Encoder/EncPara/SoftEndMaxControl@'
    lo, hi = num(smin + 'Range'), num(smax + 'Range')
    if (is_true(p.get(smin + 'Enable')) and is_true(p.get(smax + 'Enable'))
            and lo is not None and hi is not None and lo >= hi):
        add('E2', 'error', [smin + 'Range', smax + 'Range'],
            'Soft limit minimum %s is not below the maximum %s: no position is allowed.'
            % (p[smin + 'Range'], p[smax + 'Range']))

    lag = 'Controller/CtrPara/PosDiffControl@'
    if is_false(p.get(lag + 'Enable')):
        add('C1', 'warning', [lag + 'Enable'],
            'Position lag monitoring is switched off: the NC will not stop an axis that '
            'cannot follow its set point (stalled, blocked or wrongly scaled).')
    rng = num(lag + 'Range')
    if rng is not None and rng <= 0:
        add('C2', 'error', [lag + 'Range'], 'Position lag window is %s. It must be '
            'positive.' % p[lag + 'Range'])
    t = num(lag + 'Time')
    if t is not None and t < 0:
        add('C2', 'error', [lag + 'Time'], 'Position lag filter time is negative.')

    # Type ids 5 (drive) and 1 (encoder) are what every simulated axis in the public
    # sample projects uses; real drives use other ids.
    if p.get('Drive@DrvType') == '5' or p.get('Encoder@EncType') == '1':
        add('S1', 'info', ['Drive@DrvType', 'Encoder@EncType'],
            'Simulation drive or encoder (DrvType %s, EncType %s). Fine for testing; a '
            'machine axis linked to real hardware uses other types.'
            % (p.get('Drive@DrvType', '-'), p.get('Encoder@EncType', '-')))
    return found


def is_true(value):
    return value is not None and value.lower() == 'true'


def is_false(value):
    return value is not None and value.lower() == 'false'


# --- Diff ---------------------------------------------------------------------------

def diff(old, new):
    """Compare two loaded axes. Returns a list of {path, change, old, new}."""
    a, b = old['params'], new['params']
    rows = []
    for path in sorted(set(a) | set(b)):
        if path in a and path in b:
            if not same(a[path], b[path]):
                rows.append({'path': path, 'change': 'changed', 'old': a[path], 'new': b[path]})
        elif path in b:
            rows.append({'path': path, 'change': 'set', 'old': None, 'new': b[path]})
        else:
            rows.append({'path': path, 'change': 'back to default', 'old': a[path],
                         'new': None})
    return rows


def bookkeeping_diff(old, new):
    """ParameterChanged entries per group whose set of values differs."""
    a, b = old.get('bookkeeping', {}), new.get('bookkeeping', {})
    return [{'path': path, 'old': a.get(path, []), 'new': b.get(path, [])}
            for path in sorted(set(a) | set(b))
            if sorted(a.get(path, [])) != sorted(b.get(path, []))]


# --- Change output: table and Automation Interface CSV ---------------------------------

PRODUCED_ROOT = '/TreeItem/NcAxisDef/'
# Parameter groups the produced XML names differently (references/config-changes.md).
PRODUCED_GROUPS = {'AxisPara': 'AxisParam', 'EncPara': 'EncParam', 'DrvPara': 'DrvParam',
                   'CtrPara': 'CtrParam'}
UNKNOWN_DEFAULT = 'default (value not known to this tool)'


def produced_path(path):
    """An .xti parameter path as the XPath of its value element in ProduceXml output."""
    parts = path.replace('@', '/').strip('/').split('/')
    return PRODUCED_ROOT + '/'.join(PRODUCED_GROUPS.get(part, part) for part in parts)


def ai_changes(rows, root):
    """Match diff rows to a produced axis XML. Returns (rows, problems, notes):
    rows as (xpath, old, new) with old read from the produced XML; problems for diff rows
    that cannot be written; notes where the target's value differs from the old file."""
    if root.tag != 'TreeItem' or root.find('NcAxisDef') is None:
        raise XtiError('not ProduceXml output of an NC axis (expected TreeItem/NcAxisDef)')
    out, problems, notes = [], [], []
    for r in rows:
        path = r['path']
        if r['change'] == 'back to default':
            problems.append('%s: goes back to its default, a value this tool does not know. '
                            'Set it in XAE.' % path)
            continue
        if '[' in path:
            problems.append('%s: repeated element; its position in the produced XML is not '
                            'known. Set it in XAE.' % path)
            continue
        xpath = produced_path(path)
        nodes = root.findall(xpath[len('/TreeItem/'):])
        if len(nodes) != 1:
            problems.append('%s: %s matches %d elements in the produced XML, not 1.'
                            % (path, xpath, len(nodes)))
            continue
        if len(nodes[0]):
            problems.append('%s: %s is a group, not a value.' % (path, xpath))
            continue
        current = nodes[0].text or ''
        if r['old'] is not None and not same(current, r['old']):
            notes.append('%s: the target has %s, the old file had %s; the CSV expects %s.'
                         % (xpath, current, r['old'], current))
        out.append((xpath, current, r['new']))
    return out, problems, notes


def table_cell(value):
    return ascii_text(value).replace('|', '\\|')


def print_table(axis, rows):
    print('| Axis | Parameter | `.xti` path (to check) | Old | New | Why |')
    print('|---|---|---|---|---|---|')
    for r in rows:
        print('| %s | %s | `%s` | %s | %s |  |' % (
            table_cell(axis['name']), LABELS.get(r['path'], ''), r['path'],
            'default' if r['old'] is None else table_cell(r['old']),
            UNKNOWN_DEFAULT if r['new'] is None else table_cell(r['new'])))


def write_ai_csv(rows, produced_xml, csv_path):
    try:
        root = ET.parse(produced_xml).getroot()
        out, problems, notes = ai_changes(rows, root)
    except (ET.ParseError, OSError, XtiError) as exc:
        print('ERROR %s: %s' % (ascii_text(produced_xml), ascii_text(str(exc))))
        return 2
    for msg in problems:
        print('ERROR ' + ascii_text(msg))
    if problems:
        print('nothing written: every change must resolve, so the script never applies '
              'half of it.')
        return 2
    if not out:
        print('no parameter differences: nothing written.')
        return 0
    # UTF-8 with a BOM: Windows PowerShell 5.1 Import-Csv reads it without -Encoding.
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, lineterminator='\r\n')
        writer.writerow(['XPath', 'Old', 'New'])
        writer.writerows(out)
    for xpath, old, new in out:
        print('  %s: %s -> %s' % (xpath, ascii_text(old), ascii_text(new)))
    for msg in notes:
        print('NOTE ' + ascii_text(msg))
    print('Wrote %s (%d rows). Review it, then run the apply pass of axis-change.ps1 '
          '(references/config-changes.md).' % (ascii_text(csv_path), len(out)))
    return 0


# --- Command line -------------------------------------------------------------------

def axis_files(paths):
    """Expand folders to the .xti files under them. Returns (axes, problems)."""
    axes, problems = [], []
    for path in paths:
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames.sort()
                for fn in sorted(filenames):
                    if not fn.lower().endswith('.xti'):
                        continue
                    try:
                        axes.append(load(os.path.join(dirpath, fn)))
                    except XtiError:
                        pass  # NC.xti, PLC and I/O files live next to axes; not ours
        else:
            try:
                axes.append(load(path))
            except XtiError as exc:
                problems.append(str(exc))
    return axes, problems


def head(axis):
    return '%s  (%s, TwinCAT %s)' % (ascii_text(axis['name']), ascii_text(axis['path']),
                                     axis['version'] or 'unknown')


def cmd_show(args):
    axes, problems = axis_files(args.paths)
    if args.json:
        print(json.dumps({'axes': axes, 'problems': problems, 'note': DEFAULTS_NOTE},
                         indent=2))
    else:
        for axis in axes:
            print(head(axis))
            for path in sorted(axis['params']):
                print('  %s = %s' % (label(path), ascii_text(axis['params'][path])))
            n = sum(len(v) for v in axis['bookkeeping'].values())
            if n:
                print('  (%d ParameterChanged entries hidden: XAE bookkeeping, not settings)'
                      % n)
            print()
        for msg in problems:
            print('ERROR ' + ascii_text(msg))
        print('note: ' + DEFAULTS_NOTE)
    return 2 if problems or not axes else 0


def cmd_lint(args):
    axes, problems = axis_files(args.paths)
    results = [{'name': a['name'], 'path': a['path'], 'version': a['version'],
                'findings': lint(a)} for a in axes]
    if args.json:
        print(json.dumps({'axes': results, 'problems': problems, 'note': DEFAULTS_NOTE},
                         indent=2))
    else:
        for axis, res in zip(axes, results):
            print(head(axis))
            if not res['findings']:
                print('  no findings')
            for f in res['findings']:
                print('  %-7s %s %s' % (f['level'].upper(), f['rule'], f['message']))
            print()
        for msg in problems:
            print('ERROR ' + ascii_text(msg))
        if not axes and not problems:
            print('No NC axis files (ClassName=%s) found.' % NC2_CLASS)
        print('note: ' + DEFAULTS_NOTE)
    if problems or not axes:
        return 2
    bad = any(f['level'] in ('error', 'warning') for r in results for f in r['findings'])
    return 1 if bad else 0


def cmd_diff(args):
    if sum(map(bool, (args.json, args.table, args.ai_csv))) > 1:
        print('ERROR choose one of --json, --table, --ai-csv', file=sys.stderr)
        return 2
    try:
        old, new = load(args.old), load(args.new)
    except XtiError as exc:
        print('ERROR ' + ascii_text(str(exc)), file=sys.stderr)
        return 2
    rows = diff(old, new)
    if args.ai_csv:
        return write_ai_csv(rows, *args.ai_csv)
    if args.table:
        print_table(new, rows)
        return 1 if rows else 0
    book = bookkeeping_diff(old, new)
    if args.json:
        print(json.dumps({'old': args.old, 'new': args.new, 'changes': rows,
                          'bookkeeping': book, 'note': DEFAULTS_NOTE}, indent=2))
    else:
        print('--- ' + head(old))
        print('+++ ' + head(new))
        if not rows:
            print('  no parameter differences')
        for r in rows:
            if r['change'] == 'changed':
                text = '%s -> %s' % (r['old'], r['new'])
            elif r['change'] == 'set':
                text = '(default) -> %s' % r['new']
            else:
                text = '%s -> (default)' % r['old']
            print('  %-16s %s: %s' % (r['change'], label(r['path']), ascii_text(text)))
        for r in book:
            print('  %-16s %s: %s -> %s (XAE bookkeeping, not a setting)'
                  % ('bookkeeping', r['path'], ', '.join(r['old']) or 'none',
                     ', '.join(r['new']) or 'none'))
        print('note: "(default)" means the parameter is absent from the file: TwinCAT '
              'uses its default value, which this tool does not know.')
    return 1 if rows else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Read, lint and diff TwinCAT NC2 axis files (_Config/NC/Axes/*.xti).',
        epilog='Absent parameters are at their TwinCAT default; only explicit values are '
               'checked. ParameterChanged elements are XAE bookkeeping: show hides them, '
               'diff lists them apart and they do not count as a difference. Exit codes: '
               'lint 0 clean, 1 findings; diff 0 same, 1 different (--ai-csv: 0 written or '
               'nothing to change); 2 unreadable input or nothing written.')
    sub = ap.add_subparsers(dest='command')
    p = sub.add_parser('show', help='list the parameters an axis sets explicitly')
    p.add_argument('paths', nargs='+', help='.xti files or folders')
    p.set_defaults(run=cmd_show)
    p = sub.add_parser('lint', help='check axis parameters for inconsistencies')
    p.add_argument('paths', nargs='+', help='.xti files or folders')
    p.set_defaults(run=cmd_lint)
    p = sub.add_parser('diff', help='compare two versions of an axis')
    p.add_argument('old')
    p.add_argument('new')
    p.add_argument('--table', action='store_true',
                   help='print the change as a markdown parameter-change table')
    p.add_argument('--ai-csv', nargs=2, metavar=('PRODUCED_XML', 'CHANGES_CSV'),
                   help='write changes.csv for axis-change.ps1, checked against the '
                        'target axis XML from its produce pass')
    p.set_defaults(run=cmd_diff)
    for p in sub.choices.values():
        p.add_argument('--json', action='store_true', help='machine-readable output')
    args = ap.parse_args(argv)
    if not args.command:
        ap.error('choose show, lint or diff')
    return args.run(args)


if __name__ == '__main__':
    sys.exit(main())
