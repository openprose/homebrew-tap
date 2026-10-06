"""Check genuine qualified base-to-candidate Homebrew upgrades; never publish."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import update

NAMES = ('prose-bun', 'prose-rust')


def git(root, *args, optional=False):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=30)
    if optional and result.returncode:
        return None
    update.require(result.returncode == 0, 'Cannot read the specified Git revision')
    return result.stdout.strip() if args[0] != 'show' else result.stdout


def version(texts):
    versions = set()
    for name in NAMES:
        found = re.findall(r'^  version "([^\"]+)"$', texts[name], re.MULTILINE)
        update.require(len(found) == 1, 'Each implementation needs one version')
        update.version_key(found[0])
        versions.add(found[0])
    update.require(len(versions) == 1, 'Implementation versions differ')
    return versions.pop()


def admission(base_version, candidate_version):
    update.version_key(candidate_version)
    if base_version is None:
        return 'skipped-bootstrap-no-prior-formulas'
    update.version_key(base_version)
    update.require(update.version_key(candidate_version) >= update.version_key(base_version), 'Candidate would downgrade the tap')
    return 'skipped-same-version' if base_version == candidate_version else 'qualified-upgrade-required'


def revision(root, commit, *, allow_bootstrap=False):
    update.require(isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), 'Expected an immutable Git commit')
    git(root, 'cat-file', '-e', commit + '^{commit}')
    formulas = {name: git(root, 'show', f'{commit}:Formula/{name}.rb', optional=True) for name in NAMES}
    if allow_bootstrap and all(text is None for text in formulas.values()):
        return None
    update.require(all(isinstance(text, str) for text in formulas.values()), 'Both reviewed formulas are required')
    selected = version(formulas)
    inputs = git(root, 'show', f'{commit}:records/{selected}-inputs.json')
    record = update.decode(inputs)
    manifest_url = update.BASE + f'cli/releases/{selected}/manifest.json'
    update.require(record.get('manifestUrl') == manifest_url, 'Unexpected immutable manifest URL')
    pointer = {'schema': 'openprose.cli-channel/1', 'version': selected,
               'manifest': f'cli/releases/{selected}/manifest.json', 'sha256': record.get('manifestSha256')}
    # Validate each revision against its own immutable release, not today's pointer.
    with tempfile.TemporaryDirectory(prefix='upgrade-inputs-') as directory:
        scratch = Path(directory)
        (scratch / 'Formula').mkdir()
        (scratch / 'records').mkdir()
        for name, text in formulas.items():
            (scratch / 'Formula' / f'{name}.rb').write_text(text)
        (scratch / 'README.md').write_text(git(root, 'show', f'{commit}:README.md'))
        (scratch / 'records' / f'{selected}-inputs.json').write_text(inputs)
        update.check_current(scratch, json.dumps(pointer).encode(), update.fetch(manifest_url))
    return {'commit': commit, 'version': selected, 'formulas': formulas, 'manifestSha256': record['manifestSha256']}


def exercise(root, base, candidate, brew, output, runner=subprocess.run):
    original = {name: (root / 'Formula' / f'{name}.rb').read_text() for name in NAMES}
    update.require(original == candidate['formulas'], 'Working formulas differ from the checked candidate commit')
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'DEVELOPER_DIR', 'SDKROOT') if key in os.environ}
    env.update(HOMEBREW_NO_AUTO_UPDATE='1', HOMEBREW_NO_ANALYTICS='1',
               XDG_CONFIG_HOME=str(output / 'trust'))
    (output / 'trust').mkdir()
    checks = []

    def command(label, args):
        result = runner(args, env=env, capture_output=True, text=True, timeout=180)
        (output / f'{label}.log').write_text(result.stdout + result.stderr)
        checks.append({'name': label, 'exitCode': result.returncode})
        update.require(result.returncode == 0, f'Upgrade check failed: {label}; see retained log')
        return result.stdout.strip()

    def select(implementation, expected_version, label):
        prefix = Path(command(label + '-prefix', [brew, '--prefix']))
        chosen = Path(command(label + '-selected-prefix', [brew, '--prefix', f'openprose/tap/prose-{implementation}']))
        update.require((prefix / 'bin/prose').resolve() == (chosen / 'bin/prose').resolve(), 'Upgrade changed the selected implementation')
        banner = command(label + '-version', [str(prefix / 'bin/prose'), '--version'])
        update.require(banner == f'prose {expected_version} ({implementation})', 'Selected executable has an unexpected version')

    prefix = Path(command('initial-prefix', [brew, '--prefix']))
    existing = command('initial-installations', [brew, 'list', '--formula', '--versions'])
    update.require(not any(line.split()[0].split('/')[-1] in NAMES for line in existing.splitlines() if line.split()), 'Upgrade rehearsal refuses existing Prose kegs')
    update.require(not (prefix / 'bin/prose').exists() and not (prefix / 'bin/prose').is_symlink(), 'Upgrade rehearsal refuses an existing prose command')
    try:
        for selected in ('bun', 'rust'):
            for name in NAMES:
                (root / 'Formula' / f'{name}.rb').write_text(base['formulas'][name])
            command(selected + '-install-base-bun', [brew, 'install', '--build-from-source', 'openprose/tap/prose-bun'])
            command(selected + '-unlink-base-bun', [brew, 'unlink', 'openprose/tap/prose-bun'])
            command(selected + '-install-base-rust', [brew, 'install', '--build-from-source', 'openprose/tap/prose-rust'])
            if selected == 'bun':
                command(selected + '-unlink-base-rust', [brew, 'unlink', 'openprose/tap/prose-rust'])
                command(selected + '-link-base-bun', [brew, 'link', 'openprose/tap/prose-bun'])
            select(selected, base['version'], selected + '-before')
            for name in NAMES:
                (root / 'Formula' / f'{name}.rb').write_text(candidate['formulas'][name])
            # Homebrew upgrades an unlinked formula by attempting to link it.
            # Vacate the shared command, upgrade the inactive keg first, then
            # restore the user's selected implementation without overwriting.
            other = 'rust' if selected == 'bun' else 'bun'
            command(selected + '-unlink-selected-before-upgrade', [brew, 'unlink', f'openprose/tap/prose-{selected}'])
            command(selected + '-upgrade-inactive', [brew, 'upgrade', f'openprose/tap/prose-{other}'])
            command(selected + '-test-upgraded-inactive', [brew, 'test', f'openprose/tap/prose-{other}'])
            command(selected + '-unlink-upgraded-inactive', [brew, 'unlink', f'openprose/tap/prose-{other}'])
            command(selected + '-upgrade-selected', [brew, 'upgrade', f'openprose/tap/prose-{selected}'])
            command(selected + '-restore-selected-link', [brew, 'link', f'openprose/tap/prose-{selected}'])
            command(selected + '-test-upgraded-selected', [brew, 'test', f'openprose/tap/prose-{selected}'])
            for name in NAMES:
                path = Path(command(selected + '-prefix-' + name, [brew, '--prefix', 'openprose/tap/' + name]))
                implementation = name.split('-')[1]
                banner = command(selected + '-version-' + name, [str(path / 'bin/prose'), '--version'])
                update.require(banner == f'prose {candidate["version"]} ({implementation})', 'An implementation did not upgrade')
            select(selected, candidate['version'], selected + '-after')
            command(selected + '-uninstall', [brew, 'uninstall', *['openprose/tap/' + name for name in NAMES]])
            remaining = command(selected + '-remaining', [brew, 'list', '--formula', '--versions'])
            update.require(not any(line.split()[0].split('/')[-1] in NAMES for line in remaining.splitlines() if line.split()), 'Upgrade rehearsal packages did not uninstall')
    finally:
        try:
            # Initial admission established that these kegs are owned by this check.
            for name in NAMES:
                result = runner([brew, 'uninstall', 'openprose/tap/' + name], env=env, capture_output=True, text=True, timeout=180)
                (output / f'cleanup-{name}.log').write_text(result.stdout + result.stderr)
        finally:
            for name, text in original.items():
                (root / 'Formula' / f'{name}.rb').write_text(text)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--base')
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--brew', default='brew')
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    base_commit = args.base or git(args.root, 'rev-parse', 'refs/remotes/origin/main')
    candidate = revision(args.root, args.candidate)
    base = revision(args.root, base_commit, allow_bootstrap=True)
    status = admission(base['version'] if base else None, candidate['version'])
    receipt = {'schema': 'openprose.homebrew-upgrade/1', 'status': status, 'baseCommit': base_commit,
               'candidateCommit': args.candidate, 'baseVersion': base['version'] if base else None,
               'candidateVersion': candidate['version'], 'modelCalls': 0, 'checks': []}
    try:
        if status == 'qualified-upgrade-required':
            receipt['checks'] = exercise(args.root, base, candidate, args.brew, args.output)
            receipt['status'] = 'passed-qualified-upgrade-both-selections'
    except Exception:
        receipt['status'] = 'failed-qualified-upgrade'
        raise
    finally:
        (args.output / 'upgrade.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt))


if __name__ == '__main__':
    main()
