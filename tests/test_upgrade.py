import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('check_upgrade', ROOT / 'scripts/check_upgrade.py')
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


class UpgradeAdmissionTests(unittest.TestCase):
    def test_bootstrap_and_same_version_are_explicitly_skipped(self):
        self.assertEqual(upgrade.admission(None, '0.15.0-rc.2'), 'skipped-bootstrap-no-prior-formulas')
        self.assertEqual(upgrade.admission('0.15.0-rc.2', '0.15.0-rc.2'), 'skipped-same-version')
        self.assertEqual(upgrade.admission('0.15.0-rc.2', '0.15.0-rc.3'), 'qualified-upgrade-required')

    def test_downgrades_and_stable_versions_reject(self):
        for base, candidate in [('0.15.0-rc.3', '0.15.0-rc.2'), ('0.15.0-rc.2', '0.15.0'), ('0.15.0-rc.2', '1.0.0-rc.1')]:
            with self.subTest(base=base, candidate=candidate), self.assertRaises(ValueError):
                upgrade.admission(base, candidate)

    def test_mixed_implementation_versions_reject(self):
        with self.assertRaisesRegex(ValueError, 'versions differ'):
            upgrade.version({'prose-bun': '  version "0.15.0-rc.2"\n', 'prose-rust': '  version "0.15.0-rc.3"\n'})

    def test_mutable_revision_names_reject_before_git(self):
        with patch.object(upgrade, 'git') as git:
            for reference in ('main', 'refs/heads/main', '../bad', 'a' * 39):
                with self.subTest(reference=reference), self.assertRaises(ValueError):
                    upgrade.revision(ROOT, reference)
            git.assert_not_called()

    def test_partial_baseline_does_not_masquerade_as_bootstrap(self):
        def read(root, *args, **kwargs):
            if args[0] == 'cat-file':
                return ''
            return None if 'prose-bun' in args[1] else '  version "0.15.0-rc.2"\n'
        with patch.object(upgrade, 'git', side_effect=read), self.assertRaisesRegex(ValueError, 'Both reviewed formulas'):
            upgrade.revision(ROOT, 'a' * 40, allow_bootstrap=True)

    def test_preexisting_keg_rejects_before_formula_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Formula').mkdir()
            (root / 'output').mkdir()
            texts = {name: (ROOT / 'Formula' / f'{name}.rb').read_text() for name in upgrade.NAMES}
            for name, text in texts.items():
                (root / 'Formula' / f'{name}.rb').write_text(text)
            def existing(args, **kwargs):
                stdout = 'prose-bun 0.15.0-rc.2' if '--versions' in args else str(root / 'prefix')
                return subprocess.CompletedProcess(args, 0, stdout, '')
            with self.assertRaisesRegex(ValueError, 'refuses existing Prose kegs'):
                upgrade.exercise(root, {'formulas': {}}, {'formulas': texts}, 'brew', root / 'output', runner=existing)
            self.assertEqual(texts, {name: (root / 'Formula' / f'{name}.rb').read_text() for name in upgrade.NAMES})

    def test_failed_brew_restores_exact_candidate_files(self):
        # Fault injection exercises restoration; no package or executable is relabeled.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Formula').mkdir()
            (root / 'output').mkdir()
            texts = {name: (ROOT / 'Formula' / f'{name}.rb').read_text() for name in upgrade.NAMES}
            for name, text in texts.items():
                (root / 'Formula' / f'{name}.rb').write_text(text)
            candidate = {'formulas': texts}
            base = {'formulas': {name: text + '# offline restoration control\n' for name, text in texts.items()}}
            def fail(args, **kwargs):
                if args == ['brew', '--prefix']:
                    return subprocess.CompletedProcess(args, 0, str(root / 'prefix'), '')
                if args == ['brew', 'list', '--formula', '--versions']:
                    return subprocess.CompletedProcess(args, 0, '', '')
                return subprocess.CompletedProcess(args, 1, '', 'Injected offline failure')
            with self.assertRaisesRegex(ValueError, 'Upgrade check failed'):
                upgrade.exercise(root, base, candidate, 'brew', root / 'output', runner=fail)
            self.assertEqual(texts, {name: (root / 'Formula' / f'{name}.rb').read_text() for name in upgrade.NAMES})


if __name__ == '__main__':
    unittest.main()
