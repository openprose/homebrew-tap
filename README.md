# OpenProse Homebrew tap

Install either implementation of the Prose CLI from verified, prebuilt releases.
Both provide the command `prose`; choose which implementation to install.
No Bun or Rust compiler is required. A supported agent harness and its separate
authentication are required to execute programs.

For Bun:

```sh
brew install openprose/tap/prose-bun
prose --version
```

For Rust:

```sh
brew install openprose/tap/prose-rust
prose --version
```

There is no default `openprose/tap/prose` formula or alias yet. Both formulas
currently select `0.15.0-rc.2`. They support macOS and glibc Linux on ARM64 and
x86-64. Linux requires glibc 2.34 or newer. These are prereleases; the macOS
executables are not Developer ID signed or notarized.

## Switch implementations

Only one implementation can provide Homebrew's linked `prose` command at a time.
To switch from Bun to Rust, unlink Bun before installing Rust:

```sh
brew unlink openprose/tap/prose-bun
brew install openprose/tap/prose-rust
```

If Rust is already installed, use `brew link openprose/tap/prose-rust` instead.
To switch back:

```sh
brew unlink openprose/tap/prose-rust
brew link openprose/tap/prose-bun
prose --version
```

Unlinking retains the installed implementation. You can run either retained
implementation directly, without changing the selected command:

```sh
"$(brew --prefix openprose/tap/prose-bun)/bin/prose" --version
"$(brew --prefix openprose/tap/prose-rust)/bin/prose" --version
```

If npm or another installation already provides `prose`, choose your desired
installation and adjust PATH or unlink that installation explicitly. This tap
does not overwrite another installation's command automatically.

```sh
brew upgrade openprose/tap/prose-bun openprose/tap/prose-rust
brew uninstall prose-bun prose-rust
```

This tap tracks explicitly reviewed releases, including prereleases. Formula
updates retain the implementation selected by the formula name. Each selects
immutable archive URLs and SHA-256 hashes; an update changes the release rather
than rebuilding or overwriting it. The installed executable does not pin a moving
kernel or separately installed harness. Record those selections for repeatable
execution.

The initial RC2 release does not include the newer Prime fix on CLI main. The independently
observed private-build cleanup failure remains unresolved. See the maintained
[release status](https://github.com/openprose/prose-cli/blob/main/docs/cli-release-next.md)
for current runtime boundaries and qualification. Installation tests establish
packaging behavior, not fulfillment of a program.

## Maintaining this tap

Formulae are generated from reviewed release plans in the distribution
repository using `scripts/homebrew_formula.py`. Preserve all four qualified
platforms, exact archives, checksums, implementation banners and unsigned
disclosure. A prerelease version must use the explicit `rc` channel; it does
not require a separate formula name. Do not select an unqualified development
archive or promote a prerelease as stable.

Retained [release inputs](records/0.15.0-rc.2-inputs.json) bind the original
source and archive identities. The [local installation receipt](records/0.15.0-rc.2-local-install.json)
records isolated installation and switching checks for the initial RC2 release. CI tests both implementations
and command selection without provider calls. Future updates require a reviewed
new public release, rendered formula diff and install/test checks before changing
the tap. A future version-to-version upgrade remains to be tested.

The scheduled update workflow checks the public guarded
[RC pointer](https://pkg.prose.md/cli/channels/rc.json) hourly. It verifies the
immutable manifest digest, qualification and all eight archive identities before
preparing an update branch. Current formula hashes must match retained release
inputs; unexpected edits, changed immutable releases and downgrades stop the
update. Original release records remain intact. The bot explicitly starts
four-platform installation checks for the branch. CI also verifies that the
formulas and retained inputs still select the current public RC pointer.
The workflow reports the tested commit, installation run and comparison link.
The release owner creates or reuses a PR, reviews it and merges after checks
pass. A workflow can also be dispatched manually.

The organization disallows GitHub Actions from creating PRs. Branch preparation
and test dispatch use the tap's ordinary workflow token; PR creation uses the
release owner's existing GitHub authentication. No new token or organization
policy change is required. For example, replace the version below with the
reported update version:

```sh
gh pr create --repo openprose/homebrew-tap --base main \
  --head automation/rc-0.15.0-rc.3 --title "Select CLI 0.15.0-rc.3" \
  --body "Select the qualified public RC; review retained inputs and installation checks."
```

Homebrew updates follow a qualified release's public pointer; publishing across
npm, downloads and this tap is not one atomic transaction. CLI release CI tests
candidate archive installation before publication. This tap tests the public
archive installation and command switching before admitting a formula update.
No extra publication token or automatic merge is used by the tap workflow.
