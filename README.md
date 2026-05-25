# Kodrix IDE Marketplace & Binaries

This repository hosts all the registry data, metadata, and releases for the **Kodrix IDE** marketplace extensions and tool runtimes (like Node.js).

## Repository Contents

* `versions.json`: Registry mapping Node.js versions to their ABI-specific binary download URLs.
* `extensions.json`: Registry listing all marketplace extensions, descriptions, icons, and download URLs.
* `binaries.json`: Registry for system compiler updates and active binary tools.

## Releases

All large binary assets (such as Node.js compiler zips and extension packages) are uploaded as assets under GitHub Releases in this repository. This keeps the main application repository clean and avoids GitHub's 100MB file limit.
