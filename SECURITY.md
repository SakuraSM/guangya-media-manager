# Security Policy

## Supported version

Security fixes are applied to the latest commit on `main`.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting or open a draft security advisory. Do not include cloud-drive tokens, API keys, passwords, private filenames, full cloud paths, database exports, or screenshots containing personal data in a public issue.

Include the affected version, a minimal reproduction with redacted data, the expected impact, and any suggested remediation. Please allow reasonable time for triage before public disclosure.

## Deployment boundary

This project is designed for a single-user NAS and binds to loopback by default. Do not expose the API directly to the Internet. Use unique high-entropy values for `ADMIN_PASSWORD` and `SESSION_SECRET`, keep `.env` out of source control, enable TLS at a trusted reverse proxy, and rotate credentials if they may have appeared in logs or Git history.
