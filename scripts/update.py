"""Prepare a reviewed tap update from the public guarded RC pointer; never publish."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request

BASE = 'https://pkg.prose.md/'
POINTER = BASE + 'cli/channels/rc.json'
PLATFORMS = ('darwin-arm64', 'darwin-x64', 'linux-arm64-gnu', 'linux-x64-gnu')
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-rc\.([1-9][0-9]*)\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
SOURCE = re.compile(r'[0-9a-f]{40}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version_key(value):
    require(isinstance(value, str) and len(value) < 100, 'Invalid RC version')
    match = VERSION.fullmatch(value)
    require(match is not None and match[1] == '0', 'Only explicit 0.x RC releases are supported')
    return tuple(int(x) for x in match.groups())


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(url):
    require(url.startswith(BASE + 'cli/'), 'Unsupported fetch URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'OpenProse-homebrew-update/1'})
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.geturl() == url, 'Unexpected download redirect')
        raw = response.read(2_000_001)
    require(len(raw) <= 2_000_000, 'Release metadata exceeds bound')
    return raw


def qualified_archives(manifest, version):
    require(isinstance(manifest, dict) and manifest.get('schema') == 'openprose.cli-distribution/1', 'Unsupported manifest')
    require(manifest.get('version') == version, 'Manifest version mismatch')
    require(isinstance(manifest.get('source'), str) and SOURCE.fullmatch(manifest['source']), 'Invalid runtime source')
    qualification = manifest.get('qualification')
    require(isinstance(qualification, dict) and qualification.get('status') == 'kernel-smoke-qualified', 'Release is not qualified')
    evidence = qualification.get('evidence')
    require(isinstance(evidence, str) and re.fullmatch(r'https://github\.com/openprose/openprose-expedition/tree/[0-9a-f]{40}/[A-Za-z0-9._/-]+', evidence), 'Invalid qualification evidence URL')
    items = manifest.get('artifacts')
    require(isinstance(items, list) and len(items) <= 200, 'Invalid artifact inventory')
    selected = {}
    names = set()
    for item in items:
        require(isinstance(item, dict), 'Invalid artifact')
        name = item.get('name')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name), 'Unsafe artifact name')
        require(name not in names, 'Duplicate artifact name')
        names.add(name)
        require(isinstance(item.get('sha256'), str) and DIGEST.fullmatch(item['sha256']), 'Invalid artifact digest')
        require(type(item.get('size')) is int and 0 < item['size'] <= 1_000_000_000, 'Invalid artifact size')
        if item.get('kind') != 'standalone':
            continue
        implementation, platform = item.get('implementation'), item.get('platform')
        require(implementation in ('bun', 'rust') and platform in PLATFORMS, 'Unsupported standalone archive')
        require(name == f'openprose-prose-cli-{implementation}-{version}-{platform}.tar.gz', 'Unexpected archive identity')
        key = implementation, platform
        require(key not in selected, 'Duplicate implementation/platform')
        selected[key] = item
    require(set(selected) == {(i, p) for i in ('bun', 'rust') for p in PLATFORMS}, 'All eight qualified archives are required')
    return selected


def prepare(root, pointer_raw, manifest_raw):
    """Validate everything before writing any update; return its portable outcome."""
    pointer = decode(pointer_raw)
    require(isinstance(pointer, dict) and set(pointer) == {'schema', 'version', 'manifest', 'sha256'}, 'Invalid channel pointer')
    require(pointer['schema'] == 'openprose.cli-channel/1', 'Unsupported channel pointer')
    version = pointer['version']
    candidate_key = version_key(version)
    require(pointer['manifest'] == f'cli/releases/{version}/manifest.json', 'Unsafe manifest path')
    require(isinstance(pointer['sha256'], str) and DIGEST.fullmatch(pointer['sha256']), 'Invalid manifest digest')
    require(sha256(manifest_raw) == pointer['sha256'], 'Manifest digest mismatch')
    manifest = decode(manifest_raw)
    archives = qualified_archives(manifest, version)
    formula_text = {}
    current_versions = set()
    for implementation in ('bun', 'rust'):
        name = f'prose-{implementation}.rb'
        text = (root / 'Formula' / name).read_text()
        versions = re.findall(r'^  version "([^"]+)"$', text, re.MULTILINE)
        require(len(versions) == 1, 'Formula needs exactly one version')
        version_key(versions[0])
        current_versions.add(versions[0])
        formula_text[implementation] = text
    require(len(current_versions) == 1, 'Current formulas select different versions')
    current_version = current_versions.pop()
    current = decode((root / 'records' / f'{current_version}-inputs.json').read_bytes())
    require(current.get('version') == current_version and current.get('channel') == 'rc', 'Invalid current release inputs')
    require(isinstance(current.get('manifestSha256'), str) and DIGEST.fullmatch(current['manifestSha256']), 'Missing current immutable manifest identity')
    expected = current.get('formulas')
    require(isinstance(expected, list) and len(expected) == 2, 'Invalid current formula inventory')
    expected = {x['file']: x['sha256'] for x in expected}
    require(set(expected) == {'prose-bun.rb', 'prose-rust.rb'}, 'Unexpected current formulas')
    for implementation, text in formula_text.items():
        require(sha256(text.encode()) == expected[f'prose-{implementation}.rb'], 'Current formula hash mismatch; review local edits')
    require(candidate_key >= version_key(current_version), 'RC pointer would downgrade this tap')
    if version == current_version:
        require(pointer['sha256'] == current['manifestSha256'], 'Existing release manifest changed')
        require(current.get('runtimeSource') == manifest['source'] and current.get('qualification') == manifest['qualification'], 'Current release qualification metadata mismatch')
        recorded_archives = current.get('archives')
        require(isinstance(recorded_archives, list) and len(recorded_archives) == 8, 'Current archive inventory mismatch')
        require(sorted(json.dumps(x, sort_keys=True) for x in recorded_archives) == sorted(json.dumps(x, sort_keys=True) for x in archives.values()), 'Current archive identities mismatch')
        require(current.get('archiveBase') == BASE + f'cli/releases/{version}/' and current.get('manifestUrl') == BASE + pointer['manifest'], 'Current release URL mismatch')
        return {'changed': False, 'version': version}

    prepared = {}
    for implementation, text in formula_text.items():
        text = text.replace(f'  version "{current_version}"', f'  version "{version}"', 1)
        banner = f'prose {current_version} ({implementation})'
        require(text.count(banner) == 1, 'Unexpected formula version assertion')
        text = text.replace(banner, f'prose {version} ({implementation})')
        pattern = r'      url "([^"]+)"\n      sha256 "([0-9a-f]{64})"'
        matches = list(re.finditer(pattern, text))
        require(len(matches) == 4, 'Expected exactly four archive selections')
        seen = set()
        def replace(match):
            old_url = match[1]
            prefix = BASE + f'cli/releases/{current_version}/openprose-prose-cli-{implementation}-{current_version}-'
            require(old_url.startswith(prefix) and old_url.endswith('.tar.gz'), 'Current formula URL is unexpected')
            platform = old_url[len(prefix):-len('.tar.gz')]
            require(platform in PLATFORMS and platform not in seen, 'Current formula platform is unexpected')
            seen.add(platform)
            item = archives[implementation, platform]
            return f'      url "{BASE}cli/releases/{version}/{item["name"]}"\n      sha256 "{item["sha256"]}"'
        text = re.sub(pattern, replace, text)
        require(seen == set(PLATFORMS), 'Incomplete current formula platforms')
        prepared[f'prose-{implementation}.rb'] = text
    readme_path = root / 'README.md'
    readme = readme_path.read_text()
    selection = f'currently select `{current_version}`'
    require(readme.count(selection) == 1, 'README selected release is ambiguous')
    readme = readme.replace(selection, f'currently select `{version}`')
    readme = readme.replace(f'records/{current_version}-inputs.json', f'records/{version}-inputs.json')
    record = {
        'schema': 'openprose.homebrew-release-inputs/1', 'version': version,
        'runtimeSource': manifest['source'], 'channel': 'rc',
        'manifestUrl': BASE + pointer['manifest'], 'manifestSha256': pointer['sha256'],
        'qualification': manifest['qualification'], 'archiveBase': BASE + f'cli/releases/{version}/',
        'archives': [archives[i, p] for i in ('bun', 'rust') for p in PLATFORMS],
        'formulas': [{'file': name, 'sha256': sha256(text.encode())} for name, text in sorted(prepared.items())],
    }
    record_path = root / 'records' / f'{version}-inputs.json'
    manifest_path = root / 'records' / f'{version}-manifest.json'
    require(not record_path.exists() and not manifest_path.exists(), 'Existing release record must not be overwritten')
    for name, text in prepared.items():
        (root / 'Formula' / name).write_text(text)
    readme_path.write_text(readme)
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    manifest_path.write_bytes(manifest_raw)
    return {'changed': True, 'version': version, 'manifestSha256': pointer['sha256']}


def check_current(root, pointer_raw, manifest_raw):
    """Check the selected public release without modifying the supplied checkout."""
    with tempfile.TemporaryDirectory(prefix='homebrew-current-') as directory:
        scratch = Path(directory)
        bun = root / 'Formula/prose-bun.rb'
        require(bun.is_file() and not bun.is_symlink(), 'Unexpected formula file')
        versions = re.findall(r'^  version "([^"]+)"$', bun.read_text(), re.MULTILINE)
        require(len(versions) == 1, 'Formula needs exactly one version')
        version_key(versions[0])
        paths = ['Formula/prose-bun.rb', 'Formula/prose-rust.rb', 'README.md',
                 f'records/{versions[0]}-inputs.json']
        for relative in paths:
            source = root / relative
            require(source.is_file() and not source.is_symlink(), 'Unexpected current input file')
            target = scratch / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        result = prepare(scratch, pointer_raw, manifest_raw)
        require(not result['changed'], 'This checkout does not select the current guarded RC release')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-current', action='store_true', help='Check selected public release without changing checkout files')
    args = parser.parse_args()
    pointer_raw = fetch(POINTER)
    pointer = decode(pointer_raw)
    version_key(pointer.get('version'))
    require(pointer.get('manifest') == f'cli/releases/{pointer["version"]}/manifest.json', 'Unsafe manifest path')
    operation = check_current if args.check_current else prepare
    result = operation(args.root, pointer_raw, fetch(BASE + pointer['manifest']))
    if args.output:
        args.output.write_text(json.dumps(result) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
