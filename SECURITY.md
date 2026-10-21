# Security

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/Bratwurst04/Bongo-Cat-Screen/security/advisories/new).
Include the affected version/commit, a small reproduction using synthetic data,
and the expected impact. Do not post Spotify tokens, authorization URLs/codes,
private profiles, diagnostic archives or personal album screenshots in a public
issue. Public Client IDs identify an OAuth app; they are not Client Secrets.

This is a maintained hobby project without a guaranteed response time. Current
development source is the review target. Older release downloads are historical
builds and do not acquire fixes when the source changes; check the
[current review and remaining work](docs/product-committee-2026-10-20.md).

## Current protections and limits

The development companion uses external-browser OAuth with PKCE S256, random
state, a bounded loopback callback and one token owner within the Windows login
session. The existing session-local mutex does not coordinate separate Windows
login sessions that share a profile. Credential-bearing
HTTP requests use fixed Spotify HTTPS origins and reject redirects. Settings and
tokens are replaced through unique temporary files; corrupt settings can recover
from a validated backup. These controls do not protect a compromised Windows
account, malicious firmware or an untrusted modified build.

Spotify access/refresh tokens remain **plaintext** in the local profile. DPAPI or
Windows Credential Manager storage is still pending. Keep that profile and any
backups private; never upload them to GitHub. See [Privacy](PRIVACY.md) for data
flows and removal instructions.

The October 2026 review found no confirmed live credential in the reachable
history and four inspected release packages. It used bounded custom checks and
is not proof that no secret or vulnerability exists. New candidates remain
unsigned; full dependency locking, distribution provenance and enforced branch/
release gates remain work before broader distribution. GitHub dependency alerts
cover its default-branch dependency graph, not every development build.
