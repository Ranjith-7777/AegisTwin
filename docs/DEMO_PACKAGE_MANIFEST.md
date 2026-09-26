# Demo Package Manifest

Run `scripts\demo\create_demo_package.ps1`. The ZIP includes Git-tracked source, lock/configuration files, launchers, documentation, migrations, static source assets, benchmark reports, and synthetic catalogues.

It excludes Git metadata, dependencies, virtual environments, builds, caches, databases, logs, recordings, local environment files, secrets, and model artifacts. `-IncludeModelArtifacts` explicitly adds isolated synthetic artifacts when size and licensing permit.

Every archive contains `DEMO_PACKAGE_MANIFEST.json` with UTC build time, Git commit, file count, model inclusion, and simulation-only status, plus `SHA256SUMS.txt`.
