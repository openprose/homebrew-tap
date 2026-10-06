# Tap documentation review — October 5, 2026

The intended reader is a new CLI user choosing an implementation and installing
through Homebrew. The user selected formula names `prose-bun` and `prose-rust`,
with both implementations providing `prose`. No neutral formula or default
implementation is selected. Prerelease status appears in the version and
installation caveats. Earlier unpublished formula names with an RC suffix were
rejected during naming review and are not published installation identities.

The README and formulas were prepared by a coding agent. Review checked that
installation, explicit unlink/link switching, retained-keg execution, upgrades
and uninstall use ordinary Homebrew commands without automatic overwrite,
forced links or post-install effects. The public README links maintained public
CLI status and local tap receipts; it does not require access to the private
distribution repository. Formula URLs and hashes select immutable published
RC2 archives. `records/0.15.0-rc.2-local-install.json` retains executable checks
and their scope; cross-platform CI provides additional installation evidence.

RC2 is a prerelease behind current CLI main and macOS signing is pending.
Installation checks do not qualify a program or waive the separate unresolved
cleanup observation. A real version-to-version upgrade awaits a subsequent
qualified release; same-version commands are not evidence of an upgrade.
