import copy
import importlib.util
import json
from pathlib import Path
import shutil
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('update', ROOT / 'scripts/update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'Formula', self.root / 'Formula')
        (self.root / 'records').mkdir()
        shutil.copyfile(ROOT / 'records/0.15.0-rc.2-inputs.json', self.root / 'records/0.15.0-rc.2-inputs.json')
        shutil.copyfile(ROOT / 'README.md', self.root / 'README.md')
        current = json.loads((ROOT / 'records/0.15.0-rc.2-inputs.json').read_text())
        # Normalize the baseline fixture so ordinary tap upgrades cannot break
        # these tests merely by changing the live selected release.
        original = { (x['implementation'], x['platform']): x for x in current['archives'] }
        formulas = []
        selected = None
        for impl in ('bun', 'rust'):
            p = self.root / 'Formula' / f'prose-{impl}.rb'
            text = p.read_text()
            selected = re.search(r'^  version "([^"]+)"$', text, re.MULTILINE)[1]
            text = text.replace(selected, '0.15.0-rc.2')
            pattern = r'      url "[^\n]+-((?:darwin|linux)-(?:arm64|x64)(?:-gnu)?)\.tar\.gz"\n      sha256 "[0-9a-f]{64}"'
            def replace(match):
                item = original[impl, match[1]]
                return f'      url "{current["archiveBase"]}{item["name"]}"\n      sha256 "{item["sha256"]}"'
            text, count = re.subn(pattern, replace, text)
            self.assertEqual(count, 4)
            p.write_text(text)
            formulas.append({'file': p.name, 'sha256': update.sha256(text.encode())})
        current['formulas'] = formulas
        (self.root / 'records/0.15.0-rc.2-inputs.json').write_text(json.dumps(current))
        p = self.root / 'README.md'
        p.write_text(p.read_text().replace(f'currently select `{selected}`', 'currently select `0.15.0-rc.2`'))
        self.manifest = {'schema': 'openprose.cli-distribution/1', 'version': '0.15.0-rc.3',
                         'source': current['runtimeSource'], 'qualification': current['qualification'],
                         'artifacts': copy.deepcopy(current['archives'])}
        for item in self.manifest['artifacts']:
            item['name'] = item['name'].replace('rc.2', 'rc.3')
            item['sha256'] = 'a' * 64

    def run_update(self, manifest=None, pointer_change=None, corrupt=False):
        manifest = self.manifest if manifest is None else manifest
        raw = json.dumps(manifest).encode()
        version = manifest['version']
        pointer = {'schema': 'openprose.cli-channel/1', 'version': version,
                   'manifest': f'cli/releases/{version}/manifest.json', 'sha256': update.sha256(raw)}
        if pointer_change:
            pointer.update(pointer_change)
        if corrupt:
            pointer['sha256'] = '0' * 64
        return update.prepare(self.root, json.dumps(pointer).encode(), raw)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def reject(self, mutation=None, **kwargs):
        if mutation:
            mutation(self.manifest)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.run_update(**kwargs)
        self.assertEqual(before, self.snapshot())

    def test_update_preserves_names_commands_and_retains_inputs(self):
        result = self.run_update()
        self.assertTrue(result['changed'])
        for impl in ('bun', 'rust'):
            text = (self.root / 'Formula' / f'prose-{impl}.rb').read_text()
            self.assertIn('bin.install "prose" => "prose"', text)
            self.assertIn(f'prose 0.15.0-rc.3 ({impl})', text)
            self.assertNotIn('rc.2', text)
            self.assertEqual(4, text.count('sha256 "' + 'a' * 64 + '"'))
        self.assertTrue((self.root / 'records/0.15.0-rc.2-inputs.json').exists())
        record = json.loads((self.root / 'records/0.15.0-rc.3-inputs.json').read_text())
        for formula in record['formulas']:
            self.assertEqual(formula['sha256'], update.sha256((self.root / 'Formula' / formula['file']).read_bytes()))
        self.assertIn('currently select `0.15.0-rc.3`', (self.root / 'README.md').read_text())
        self.assertFalse(self.run_update()['changed'])

    def checked_inputs(self):
        raw = json.dumps(self.manifest).encode()
        version = self.manifest['version']
        pointer = {'schema': 'openprose.cli-channel/1', 'version': version,
                   'manifest': f'cli/releases/{version}/manifest.json', 'sha256': update.sha256(raw)}
        return json.dumps(pointer).encode(), raw

    def test_check_current_no_mutation(self):
        self.run_update()
        before = self.snapshot()
        result = update.check_current(self.root, *self.checked_inputs())
        self.assertFalse(result['changed'])
        self.assertEqual(before, self.snapshot())

    def test_check_current_rejects_changed_record_metadata(self):
        self.run_update()
        path = self.root / 'records/0.15.0-rc.3-inputs.json'
        record = json.loads(path.read_text())
        record['runtimeSource'] = 'b' * 40
        path.write_text(json.dumps(record))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            update.check_current(self.root, *self.checked_inputs())
        self.assertEqual(before, self.snapshot())

    def test_check_current_rejects_lag_without_mutation(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            update.check_current(self.root, *self.checked_inputs())
        self.assertEqual(before, self.snapshot())

    def test_manifest_hash_mismatch(self):
        self.reject(corrupt=True)

    def test_unqualified_release(self):
        self.reject(lambda m: m['qualification'].update(status='built'))

    def test_missing_platform(self):
        self.reject(lambda m: m['artifacts'].pop())

    def test_duplicate_archive(self):
        self.reject(lambda m: m['artifacts'].append(copy.deepcopy(m['artifacts'][0])))

    def test_unsafe_archive(self):
        self.reject(lambda m: m['artifacts'][0].update(name='../payload.tar.gz'))

    def test_wrong_archive_implementation(self):
        self.reject(lambda m: m['artifacts'][0].update(implementation='other'))

    def test_unsafe_pointer(self):
        self.reject(pointer_change={'manifest': 'https://attacker.invalid/manifest.json'})

    def test_invalid_digest(self):
        self.reject(lambda m: m['artifacts'][0].update(sha256='bogus'))

    def test_stable_not_implicitly_promoted(self):
        self.reject(lambda m: m.update(version='0.15.0'))

    def test_downgrade(self):
        def mutate(m):
            m['version'] = '0.15.0-rc.1'
            for item in m['artifacts']:
                item['name'] = item['name'].replace('rc.3', 'rc.1')
        self.reject(mutate)

    def test_same_version_changed_bytes(self):
        self.run_update()
        self.reject(lambda m: m.update(source='b' * 40))

    def test_locally_modified_formula(self):
        p = self.root / 'Formula/prose-bun.rb'
        p.write_text(p.read_text() + '# unrelated edit\n')
        self.reject()

    def test_old_records_never_overwritten(self):
        p = self.root / 'records/0.15.0-rc.3-inputs.json'
        p.write_text('{}')
        self.reject()

    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):
            update.decode('{"version":"first","version":"last"}')


if __name__ == '__main__':
    unittest.main()
