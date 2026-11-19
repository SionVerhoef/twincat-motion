#!/usr/bin/env python3
"""Read, lint and diff TwinCAT NC axis files (_Config/NC/Axes/*.xti, classic NC / Tc2_MC2).

    axis_xti.py show  Axis1.xti              the parameters this axis sets explicitly
    axis_xti.py lint  _Config/NC/Axes        check every NC axis file under a folder
    axis_xti.py lint  MyProject              a project folder or .tsproj: its NC
                                             configuration, axis files and links, then
                                             every axis (inline ones too)
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
process-image structure) are skipped: they describe types, not settings. An axis with
more than one encoder keys each by its Name (Encoder[Enc_2]/EncPara@...): lint checks
every encoder and diff pairs them by name, not by their order in the file.

Project lint reads the .tsproj with NC.xti, the axis files, the I/O tree and every
Mappings block, in whichever mix of inline and separate files the project uses. It reports
an axis file the NC lists but that is missing (P1), an axis file the NC does not list (P2),
a shared axis Id (P3), a real drive or encoder linked to nothing (L1, L2; a LinkedTo
TcCOM connection counts), an axis no PLC AXIS_REF is linked to (L3), links to an axis the
NC does not have (L4), unrestored links still missing (L5), and outputs in the PDO
assignment of an axis's drive that no link writes, which go out as 0: limits (L6) and the
rest (L7). A box named in a link but not found in the I/O tree is reported, not guessed
at (L8). MC3 (Tc3_Mc3) axes and their links are not read.

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
import re
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
    return read_axis(axis, path, root.get('TcVersion'))


def read_axis(axis, path, version):
    """An Axis element, from an axis file or inline in NC.xti or a .tsproj, as load() returns it."""
    params, book = {}, {}
    _flatten(axis, '', params, book)
    name = params.get('Name')
    if not name or name == '__FILENAME__':
        name = os.path.splitext(os.path.basename(path))[0]
    return {'path': path, 'version': version, 'name': name, 'params': params,
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
        # Repeated siblings (an axis with two encoders) are keyed by their Name when each
        # has its own, so diff pairs them by name and not by position; else by position.
        names = [c.get('Name') for c in children if c.tag == child.tag]
        if tags.count(child.tag) == 1:
            tag = child.tag
        elif all(names) and len(set(names)) == len(names):
            tag = '%s[%s]' % (child.tag, child.get('Name'))
        else:
            tag = '%s[%d]' % (child.tag, count[child.tag])
        _flatten(child, (prefix + '/' if prefix else '') + tag, out, book)


def encoders(p):
    """(path prefix, name) of each encoder of a flattened axis: 'Encoder', or one
    'Encoder[...]' per encoder when the axis has more than one."""
    prefixes = sorted({k.split('@')[0].split('/')[0] for k in p
                       if k.startswith('Encoder@') or k.startswith('Encoder/')
                       or k.startswith('Encoder[')})
    return [(e, p.get(e + '@Name', 'Enc')) for e in prefixes]


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
    key = re.sub(r'\[[^]]*\]', '', path)
    return path + (' (%s)' % LABELS[key] if key in LABELS else '')


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

    encs = encoders(p)
    for enc, enc_name in encs:
        # On an axis with more than one encoder, say which one.
        which = '%s: ' % enc_name if len(encs) > 1 else ''
        num_path = enc + '/EncPara@ScaleFactorNumerator'
        den_path = enc + '/EncPara@ScaleFactorDenominator'
        if num(num_path) == 0:
            add('E1', 'error', [num_path], which + 'Encoder scaling numerator is 0: every '
                'position reads as 0.')
        den = num(den_path)
        if den is not None and den <= 0:
            add('E1', 'error', [den_path], which + 'Encoder scaling denominator is %s. It '
                'must be positive.' % p[den_path])

        smin, smax = enc + '/EncPara/SoftEndMinControl@', enc + '/EncPara/SoftEndMaxControl@'
        lo, hi = num(smin + 'Range'), num(smax + 'Range')
        if (is_true(p.get(smin + 'Enable')) and is_true(p.get(smax + 'Enable'))
                and lo is not None and hi is not None and lo >= hi):
            add('E2', 'error', [smin + 'Range', smax + 'Range'],
                which + 'Soft limit minimum %s is not below the maximum %s: no position is '
                'allowed.' % (p[smin + 'Range'], p[smax + 'Range']))

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
    enc_types = [enc + '@EncType' for enc, _ in encs] or ['Encoder@EncType']
    if p.get('Drive@DrvType') == '5' or any(p.get(t) == '1' for t in enc_types):
        add('S1', 'info', ['Drive@DrvType'] + enc_types,
            'Simulation drive or encoder (DrvType %s, EncType %s). Fine for testing; a '
            'machine axis linked to real hardware uses other types.'
            % (p.get('Drive@DrvType', '-'), '/'.join(p.get(t, '-') for t in enc_types)))
    return found


def is_true(value):
    return value is not None and value.lower() == 'true'


def is_false(value):
    return value is not None and value.lower() == 'false'


# --- Project lint: NC configuration, axis files and links --------------------------------
#
# A project is its .tsproj. The NC configuration is either inline in it or in
# _Config/NC/NC.xti; axes are either inline in that NC configuration or in
# _Config/NC/Axes/*.xti; the I/O tree is inline or in _Config/IO/. Links (Mappings) sit in
# the .tsproj, in NC.xti, in each axis file (owner left empty: the axis itself), in the
# PLC instance .xti and in I/O files. Every layout seen in public projects mixes these.

SIM_DRIVE, SIM_ENCODER = '5', '1'
PLC_LINK_VARS = ('Inputs^FromPlc', 'Outputs^ToPlc')
# CiA 402 limit objects (max torque, max current, positive and negative torque limit) for
# drive channels 1 and 2 (+0x800); caught by index when a localised name hides "limit".
# Channel 3 on would collide with terminals' own output objects from 0x7000. Beckhoff
# servo terminals name theirs "Torque limitation", "... limit value" (0x7010).
CIA402_LIMITS = {base + channel for base in (0x6072, 0x6073, 0x60E0, 0x60E1)
                 for channel in (0, 0x800)}


def _root(path):
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


def find_file(folder, name):
    """A project-relative file name resolved under folder. Projects come from Windows:
    separators are backslashes and the case on disk need not match. None if absent."""
    path = folder
    for part in name.replace('\\', '/').split('/'):
        if os.path.exists(os.path.join(path, part)):
            path = os.path.join(path, part)
            continue
        try:
            match = [f for f in os.listdir(path) if f.lower() == part.lower()]
        except OSError:
            return None
        if not match:
            return None
        path = os.path.join(path, match[0])
    return path


def item_name(elem, path):
    name = (elem.findtext('Name') or '').strip()
    if name in ('', '__FILENAME__'):
        return os.path.splitext(os.path.basename(path))[0]
    return name


def axis_of(owner, tasks):
    """The NC axis a link owner names: 'TINC^<task>^Axes^<axis>[^<sub-object>]' for one of
    the NC tasks, or 'Axes^<axis>' inside NC.xti. None for any other owner, including the
    axes of an MC3 project, which are named the same way under the project's name."""
    if owner.startswith('TINC^') and '^Axes^' in owner:
        task, rest = owner[len('TINC^'):].split('^Axes^', 1)
        return rest.split('^', 1)[0] if task in tasks else None
    if owner.startswith('Axes^'):
        return owner[len('Axes^'):].split('^', 1)[0]
    return None


def mappings(root, self_name):
    """Links in a file's Mappings block as (owner A, var A, owner B, var B). An owner
    without a name is the item the file holds, passed as self_name."""
    out = []
    block = root.find('Mappings')
    for oa in (block.findall('OwnerA') if block is not None else []):
        for ob in oa.findall('OwnerB'):
            for link in ob.findall('Link'):
                out.append((oa.get('Name') or self_name, link.get('VarA', ''),
                            ob.get('Name') or self_name, link.get('VarB', '')))
    return out


def unrestored(root):
    """Links XAE kept but could not restore (UnrestoredVarLinks), as (owner A, owner B,
    var A, var B, RestoreInfo). Owner A is written as a Prefix there."""
    out = []
    for block in root.iter('UnrestoredVarLinks'):
        for oa in block.findall('OwnerA'):
            for ob in oa.findall('OwnerB'):
                for link in ob.findall('Link'):
                    out.append((oa.get('Prefix') or oa.get('Name', ''), ob.get('Name', ''),
                                link.get('VarA', ''), link.get('VarB', ''),
                                link.get('RestoreInfo', '')))
    return out


def io_boxes(io, cfg):
    """Every box of the I/O tree as {link name 'TIID^device^box...': Box element}, plus
    {file: link name} for box and device files, whose own links leave the owner empty."""
    boxes, files = {}, {}

    def walk(elem, folder, file, prefix):
        for child in elem.findall('Box'):
            path, sub = file, folder
            if child.get('File'):
                path = find_file(folder, child.get('File'))
                root = _root(path) if path else None
                child = root.find('Box') if root is not None else None
                if child is None:
                    continue
                sub = os.path.splitext(path)[0]
            name = prefix + '^' + item_name(child, path or '')
            boxes[name] = child
            if path != file:
                files[path] = name
            walk(child, sub, path, name)

    io_dir = os.path.join(cfg, 'IO')
    for dev in io.findall('Device') if io is not None else []:
        path = None
        if dev.get('File'):
            path = find_file(io_dir, dev.get('File'))
            root = _root(path) if path else None
            dev = root.find('Device') if root is not None else None
            if dev is None:
                continue
        name = 'TIID^' + item_name(dev, path or '')
        if path:
            files[path] = name
        # An inline device still keeps its box files in a folder named after it.
        walk(dev, os.path.splitext(path)[0] if path else os.path.join(io_dir, name[5:]),
             path, name)
    return boxes, files


def is_limit(entry):
    name = entry.get('Name', '').lower()
    if 'limit' in name:
        return True
    try:
        return int(entry.get('Index', '').replace('#x', ''), 16) in CIA402_LIMITS
    except ValueError:
        return False


def unlinked_outputs(box, box_vars):
    """Output PDO entries the box sends (PDO assigned to a sync manager) that no link
    writes, as (limits, others). Link names of modular and multi-channel drives put a
    module or channel in front ('Ch A^<pdo>^<entry>'), so an entry matches on its tail.
    FSoE frames are filled by TwinSAFE, not by links, and are left out."""
    limits, others = [], []
    for pdo in box.findall('EtherCAT/Pdo'):
        if pdo.get('InOut') != '1' or not pdo.get('SyncMan') or 'FSoE' in pdo.get('Name', ''):
            continue
        for entry in pdo.findall('Entry'):
            if entry.get('Index', '#x0') in ('#x0', '#x0000') or not entry.get('Name'):
                continue  # padding
            var = '%s^%s' % (pdo.get('Name'), entry.get('Name'))
            if any(v == var or v.endswith('^' + var) for v in box_vars):
                continue
            group = limits if is_limit(entry) else others
            if var not in group:
                group.append(var)
    return limits, others


def load_project(tsproj):
    """Read a project: its NC axes (inline or in files), links and I/O boxes.
    Returns {'path', 'axes', 'findings'}; findings here are the file-level ones."""
    root = _root(tsproj)
    if root is None:
        raise XtiError('%s: cannot read as XML' % tsproj)
    base = os.path.dirname(tsproj)
    cfg = os.path.join(base, '_Config')
    found, axes, links, lost = [], [], [], []

    def add(rule, level, message, axis=None):
        found.append({'rule': rule, 'level': level, 'axis': axis, 'message': message})

    links += mappings(root, 'file:' + tsproj)
    lost += unrestored(root)
    project = root.find('Project')
    nc = project.find('Motion/NC') if project is not None else None
    notes = []
    if project is not None and project.find('Motion/MC') is not None:
        notes.append('The project has an MC3 motion project (Tc3_Mc3); its axes and their links '
                     'are not read.')
    nc_path, version = tsproj, root.get('TcVersion')
    if nc is not None and nc.get('File'):
        nc_file = nc.get('File')
        nc_path = find_file(os.path.join(cfg, 'NC'), nc_file)
        nc_root = _root(nc_path) if nc_path else None
        nc = nc_root.find('NC') if nc_root is not None else None
        if nc is None:
            add('P1', 'error', 'The project names NC configuration file %s, but it is %s.'
                % (nc_file, 'missing' if not nc_path else 'not readable'))
            return {'path': tsproj, 'axes': [], 'findings': found, 'notes': notes}
        links += mappings(nc_root, 'file:' + nc_path)
        lost += unrestored(nc_root)
        version = nc_root.get('TcVersion') or version

    axes_dir = os.path.join(cfg, 'NC', 'Axes')
    listed = set()
    for ref in nc.findall('Axis') if nc is not None else []:
        if not ref.get('File'):
            axis = read_axis(ref, nc_path, version)
            axis['path'] = '%s, inline' % nc_path
        else:
            path = find_file(axes_dir, ref.get('File'))
            if path is None:
                add('P1', 'error', 'NC lists axis file %s (Id %s), but it is not in %s. '
                    'TwinCAT cannot load that axis.' % (ref.get('File'), ref.get('Id'),
                                                       os.path.relpath(axes_dir, base)))
                axes.append({'name': os.path.splitext(ref.get('File'))[0], 'id': ref.get('Id'),
                             'axis': None})
                continue
            listed.add(os.path.normcase(os.path.abspath(path)))
            try:
                axis = load(path)
            except XtiError as exc:
                add('P1', 'error', str(exc))
                continue
            axis_root = _root(path)
            links += mappings(axis_root, 'TINC^^Axes^' + axis['name'])
            lost += unrestored(axis_root)
        axes.append({'name': axis['name'], 'id': ref.get('Id'), 'axis': axis})

    if os.path.isdir(axes_dir):
        for dirpath, dirnames, filenames in os.walk(axes_dir):
            dirnames.sort()
            for fn in sorted(filenames):
                path = os.path.join(dirpath, fn)
                if (fn.lower().endswith('.xti')
                        and os.path.normcase(os.path.abspath(path)) not in listed):
                    add('P2', 'info', '%s is not listed in the NC configuration: TwinCAT '
                        'ignores it, and editing it changes nothing.'
                        % os.path.relpath(path, base))

    ids = {}
    for a in axes:
        ids.setdefault(a['id'], []).append(a['name'])
    for axis_id, names in sorted(ids.items(), key=lambda kv: str(kv[0])):
        if axis_id is not None and len(names) > 1:
            add('P3', 'error', 'Axes %s share Id %s. Each NC axis needs its own Id.'
                % (', '.join(names), axis_id))

    boxes, io_files = io_boxes(project.find('Io') if project is not None else None, cfg)
    if os.path.isdir(cfg):
        seen = {os.path.normcase(os.path.abspath(p)) for p in [nc_path] + list(listed)}
        for dirpath, dirnames, filenames in os.walk(cfg):
            dirnames.sort()
            for fn in sorted(filenames):
                path = os.path.join(dirpath, fn)
                if (not fn.lower().endswith('.xti')
                        or os.path.normcase(os.path.abspath(path)) in seen):
                    continue
                file_root = _root(path)
                if file_root is not None:
                    links += mappings(file_root, io_files.get(path, 'file:' + path))
                    lost += unrestored(file_root)

    if nc is None:
        notes.append('No classic NC configuration (Motion/NC) in this project: nothing to check.')
    else:
        # '' is the task of the implicit owner in axis files.
        tasks = {(t.findtext('Name') or '').strip() for t in nc.findall('SafTask')} | {''}
        check_links(axes, links, lost, boxes, tasks, add)
    return {'path': tsproj, 'axes': axes, 'findings': found, 'notes': notes}


def check_links(axes, links, lost, boxes, tasks, add):
    """Link findings for the project's axes (rules L1-L8)."""
    names = {a['name'] for a in axes}
    on_axis = {}      # axis name -> [(axis var, partner owner)]
    box_vars = {}     # box link name -> box-side vars of every link it has
    for a, va, b, vb in links:
        for owner, var, partner in ((a, va, b), (b, vb, a)):
            if axis_of(owner, tasks) is not None:
                on_axis.setdefault(axis_of(owner, tasks), []).append((var, partner))
            if owner.startswith('TIID^'):
                box_vars.setdefault(owner, set()).add(var)

    for name in sorted(set(on_axis) - names):
        partners = sorted({p for _, p in on_axis[name]})
        add('L4', 'warning', 'Links name axis "%s", which the NC configuration does not have '
            '(renamed or deleted?): %s. Those links connect nothing.'
            % (name, ', '.join(partners)), name)

    # UnrestoredVarLinks are links XAE could not restore, mostly after a PLC was renamed or
    # re-imported. Most were made again since; only those still missing now matter.
    stale = {}
    for prefix, owner, var_a, var_b, info in lost:
        for side, var in ((prefix, var_a), (owner, var_b)):
            name = axis_of(side, tasks)
            if name is not None and not any(v == var for v, _ in on_axis.get(name, [])):
                stale.setdefault(name, set()).add(var)
    for name in sorted(stale):
        if name in names:
            add('L5', 'warning', 'XAE could not restore the link(s) on %s, and they are not '
                'linked now: the PLC or I/O side was renamed or removed. Link them again.'
                % ', '.join(sorted(stale[name])), name)
        else:
            add('L5', 'info', 'Leftover unrestored link(s) to axis "%s", which the NC '
                'configuration no longer has. They connect nothing; delete them in XAE.'
                % name, name)

    checked = set()
    for a in axes:
        ax = a['axis']
        if ax is None:
            continue
        p, mine = ax['params'], on_axis.get(a['name'], [])
        # Link names start with the Drive and Encoder sub-items' own names ('Drive^...',
        # 'Enc^...' unless renamed). A LinkedTo element connects one to a TcCOM object
        # instead (XTS and XPlanar movers), with no links at all.
        drive, drv_type = p.get('Drive@Name', 'Drive'), p.get('Drive@DrvType')
        encs = encoders(p)
        if (drv_type not in (None, SIM_DRIVE) and 'Drive/LinkedTo@ObjectId' not in p
                and not any(v.startswith(drive + '^') for v, _ in mine)):
            add('L1', 'warning', 'Drive (DrvType %s) is linked to nothing: the set point and '
                'control word reach no drive, so the axis cannot enable or move. Link the '
                'axis drive to its drive or terminal in XAE.' % drv_type, a['name'])
        for e, enc in encs:
            enc_type = p.get(e + '@EncType')
            which = ' %s' % enc if len(encs) > 1 else ''
            if (enc_type not in (None, SIM_ENCODER) and e + '/LinkedTo@ObjectId' not in p
                    and not any(v.startswith(enc + '^') for v, _ in mine)):
                add('L2', 'warning', 'Encoder%s (EncType %s) is linked to nothing: the actual '
                    'position never changes. Link the axis encoder in XAE.'
                    % (which, enc_type), a['name'])
        if not any(v in PLC_LINK_VARS for v, _ in mine):
            add('L3', 'info', 'Not linked to a PLC AXIS_REF (Inputs^FromPlc, '
                'Outputs^ToPlc): MC_ blocks cannot command this axis.', a['name'])
        for box in sorted({o for v, o in mine if o.startswith('TIID^')
                           and v.split('^', 1)[0] in [drive] + [n for _, n in encs]}):
            if box in checked:
                continue
            checked.add(box)
            axes_on_box = sorted({n for n, items in on_axis.items()
                                  for v, o in items if o == box})
            if box not in boxes:
                add('L8', 'info', 'Linked to %s, which is not in the I/O tree under that name, '
                    'so its PDO outputs were not checked. If that box was renamed or removed, '
                    'the link connects nothing.' % box[len('TIID^'):], a['name'])
                continue
            limits, others = unlinked_outputs(boxes[box], box_vars.get(box, set()))
            where = '%s (axis %s)' % (box[len('TIID^'):], ', '.join(axes_on_box))
            if limits:
                add('L6', 'warning', '%s sends limit output(s) that nothing is linked to: %s. '
                    'An unlinked PDO output goes out as 0, and depending on the drive a limit '
                    'of 0 means no torque or no speed: the axis enables but does not move or '
                    'lags out. Link it, write it from the PLC, or remove it from the PDO '
                    'assignment.' % (where, ', '.join(limits)), a['name'])
            if others:
                add('L7', 'info', '%s sends output(s) nothing is linked to, so they go out as '
                    '0: %s. Usually harmless; check each is meant to be 0.'
                    % (where, ', '.join(others)), a['name'])


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


def project_files(paths):
    """Split lint arguments: .tsproj files, and folders holding one, are projects; the
    rest are axis files and folders. Returns (projects, axis paths)."""
    projects, rest = [], []
    for path in paths:
        if path.lower().endswith('.tsproj'):
            projects.append(path)
            continue
        found = []
        if os.path.isdir(path):
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames.sort()
                found += [os.path.join(dirpath, fn) for fn in sorted(filenames)
                          if fn.lower().endswith('.tsproj')]
        if found:
            projects += found
        else:
            rest.append(path)
    return projects, rest


def lint_result(axis):
    return {'name': axis['name'], 'path': axis['path'], 'version': axis['version'],
            'findings': lint(axis)}


def print_axis_result(res):
    print('%s  (%s, TwinCAT %s)' % (ascii_text(res['name']), ascii_text(res['path']),
                                    res['version'] or 'unknown'))
    if not res['findings']:
        print('  no findings')
    for f in res['findings']:
        print('  %-7s %s %s' % (f['level'].upper(), f['rule'], ascii_text(f['message'])))
    print()


def cmd_lint(args):
    tsprojs, paths = project_files(args.paths)
    projects, problems = [], []
    for tsproj in tsprojs:
        try:
            pr = load_project(tsproj)
        except XtiError as exc:
            problems.append(str(exc))
            continue
        projects.append({'path': tsproj, 'findings': pr['findings'], 'notes': pr['notes'],
                         'axes': [lint_result(a['axis']) for a in pr['axes'] if a['axis']]})
    axes, more = axis_files(paths) if paths else ([], [])
    problems += more
    results = [lint_result(a) for a in axes]
    if args.json:
        print(json.dumps({'projects': projects, 'axes': results, 'problems': problems,
                          'note': DEFAULTS_NOTE}, indent=2))
    else:
        for pr in projects:
            print('Project %s' % ascii_text(pr['path']))
            if not pr['findings']:
                print('  no project findings')
            for f in pr['findings']:
                print('  %-7s %s %s%s' % (f['level'].upper(), f['rule'],
                                          '[%s] ' % ascii_text(f['axis']) if f['axis'] else '',
                                          ascii_text(f['message'])))
            for msg in pr['notes']:
                print('  note: ' + ascii_text(msg))
            print()
            for res in pr['axes']:
                print_axis_result(res)
        for res in results:
            print_axis_result(res)
        for msg in problems:
            print('ERROR ' + ascii_text(msg))
        if not projects and not axes and not problems:
            print('No NC axis files (ClassName=%s) or .tsproj found.' % NC2_CLASS)
        print('note: ' + DEFAULTS_NOTE)
    if problems or not (projects or axes):
        return 2
    every = [f for pr in projects for f in pr['findings']]
    every += [f for r in results + [a for pr in projects for a in pr['axes']]
              for f in r['findings']]
    return 1 if any(f['level'] in ('error', 'warning') for f in every) else 0


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
