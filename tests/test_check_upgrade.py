"""Exercise ordinary upgrade linking with two formulas sharing one command."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_upgrade as upgrade


class LinkingBrew:
    """Offline command control: unlinked upgrades attempt ordinary linking."""
    def __init__(self, root, formulas, fail_upgrade=False):
        self.prefix = root / 'prefix'
        (self.prefix / 'bin').mkdir(parents=True)
        self.active = self.prefix / 'bin/prose'
        self.formulas = formulas
        self.installed = {}
        self.commands = []
        self.fail_upgrade = fail_upgrade

    def run(self, argv, **kwargs):
        self.commands.append(argv)
        command = argv[1]
        if command == '--prefix':
            output = str(self.prefix if len(argv) == 2 else self.prefix / 'Cellar' / argv[2].split('/')[-1])
        elif command == 'list':
            output = '\n'.join(name + ' ' + version for name, version in self.installed.items())
        elif command in ('install', 'upgrade'):
            names = [arg.split('/')[-1] for arg in argv[2:] if not arg.startswith('--')]
            for name in names:
                if command == 'upgrade' and self.fail_upgrade:
                    return subprocess.CompletedProcess(argv, 1, '', 'Injected upgrade failure')
                if self.active.is_symlink() and self.active.resolve().parent.parent.name != name:
                    return subprocess.CompletedProcess(argv, 1, '', 'Could not symlink bin/prose')
                self.installed[name] = upgrade.version({n: (self.formulas / (n + '.rb')).read_text() for n in upgrade.NAMES})
                target = self.prefix / 'Cellar' / name / 'bin/prose'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('offline command control; never executed')
                if self.active.is_symlink(): self.active.unlink()
                self.active.symlink_to(target)
            output = ''
        elif command == 'unlink':
            name = argv[2].split('/')[-1]
            if self.active.is_symlink() and self.active.resolve().parent.parent.name == name:
                self.active.unlink()
            output = ''
        elif command == 'link':
            name = argv[2].split('/')[-1]
            if self.active.is_symlink() and self.active.resolve().parent.parent.name != name:
                return subprocess.CompletedProcess(argv, 1, '', 'Could not symlink bin/prose')
            if not self.active.is_symlink(): self.active.symlink_to(self.prefix / 'Cellar' / name / 'bin/prose')
            output = ''
        elif command == 'uninstall':
            for arg in argv[2:]:
                name = arg.split('/')[-1]
                self.installed.pop(name, None)
                if self.active.is_symlink() and self.active.resolve().parent.parent.name == name:
                    self.active.unlink()
            output = ''
        elif command == 'test':
            output = ''
        elif command == '--version':
            name = Path(argv[0]).resolve().parent.parent.name
            output = 'prose ' + self.installed[name] + ' (' + name.split('-')[1] + ')'
        else:
            raise AssertionError('Unexpected command: ' + repr(argv))
        return subprocess.CompletedProcess(argv, 0, output, '')


class UpgradeSelectionTests(unittest.TestCase):
    def exercise(self, fail_upgrade=False):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root / 'Formula').mkdir(); (root / 'output').mkdir()
        candidate = {n: '  version "0.15.0-rc.3"\n' for n in upgrade.NAMES}
        base = {n: '  version "0.15.0-rc.2"\n' for n in upgrade.NAMES}
        for name, text in candidate.items(): (root / 'Formula' / (name + '.rb')).write_text(text)
        brew = LinkingBrew(root, root / 'Formula', fail_upgrade)
        args = (root, {'version': '0.15.0-rc.2', 'formulas': base},
                {'version': '0.15.0-rc.3', 'formulas': candidate}, 'brew', root / 'output')
        return root, candidate, brew, args

    def test_both_selections_upgrade_without_overwriting_or_link_collision(self):
        root, candidate, brew, args = self.exercise()
        checks = upgrade.exercise(*args, runner=brew.run)
        for selected, other in (('bun', 'rust'), ('rust', 'bun')):
            labels = [check['name'] for check in checks]
            expected = [selected + suffix for suffix in ('-unlink-selected-before-upgrade', '-upgrade-inactive',
                        '-unlink-upgraded-inactive', '-upgrade-selected', '-restore-selected-link')]
            positions = [labels.index(label) for label in expected]
            self.assertEqual(positions, list(range(positions[0], positions[0] + 5)))
            self.assertIn(['brew', 'upgrade', 'openprose/tap/prose-' + other], brew.commands)
        self.assertEqual(len([c for c in brew.commands if c[1] == 'upgrade']), 4)
        self.assertFalse(any('--force' in c or '--overwrite' in c for c in brew.commands))
        self.assertEqual(brew.installed, {})
        self.assertFalse(brew.active.is_symlink())
        self.assertEqual(candidate, {n: (root / 'Formula' / (n + '.rb')).read_text() for n in upgrade.NAMES})

    def test_upgrade_failure_restores_candidate_and_cleans_owned_kegs(self):
        root, candidate, brew, args = self.exercise(fail_upgrade=True)
        with self.assertRaisesRegex(ValueError, 'upgrade-inactive'):
            upgrade.exercise(*args, runner=brew.run)
        self.assertEqual(candidate, {n: (root / 'Formula' / (n + '.rb')).read_text() for n in upgrade.NAMES})
        self.assertEqual(brew.installed, {})
        self.assertFalse(brew.active.is_symlink())


if __name__ == '__main__': unittest.main()
