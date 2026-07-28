# Security Policy

## Reporting a vulnerability

Please do not report vulnerabilities through public GitHub issues, discussions or pull requests.

Use GitHub's private vulnerability reporting from the repository **Security** tab, or email [app.support@company.example](mailto:app.support@company.example). Include the affected version, reproduction steps, impact and any suggested mitigation. The maintainers will acknowledge the report and coordinate disclosure after a fix is available.

Report vulnerabilities in third-party packages to the relevant package maintainer as well.

## Supported versions

| Version | Supported |
|---|---|
| Latest `main` release | Yes |
| Older commits and forks | No |

## Prototype warning

This repository is an exploratory reference implementation, not a production-secure employee platform.

- Authentication is a demonstration email-domain check, not SSO or 2FA.
- External actions are simulated.
- Service controls are disabled by default and intended only for a private Linux deployment.
- The application binds to localhost by default.
- Production use requires approved identity, HTTPS, CSRF protection, rate limits, monitoring, retention rules and a security review.

## Secret and data handling

- Never commit `.env`, credentials, private keys or authentication tokens.
- Never commit `data/`, conversations, audit events, employee profiles, uploaded documents, logs or model files.
- Use `.env.example` only as a configuration template and replace every secret placeholder.
- Keep department checks in place before retrieval or conversation access.
- Treat retrieved documents as untrusted input that cannot override system rules.

## External actions

Real connectors must add explicit authorization, least-privilege credentials, confirmation, idempotency, target validation, immutable audit evidence, retries, timeouts and a kill switch before execution is enabled.

![the configured assistant access and safety boundaries](docs/assets/access-boundaries.svg)
