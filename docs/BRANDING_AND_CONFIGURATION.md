# Branding and organization configuration

The repository is white-label. Company identity, assistant identity, email access, and website knowledge sources are runtime configuration—not Python, JavaScript, or HTML constants.

## Branding variables

Set these values in the local `.env` file:

```dotenv
ORGANIZATION_NAME="Your Organization"
ASSISTANT_NAME="OpenSource AI Workspace"
ORGANIZATION_INITIAL="O"
ORGANIZATION_ALIASES="your organization,company abbreviation"
APP_NAME="OpenSource AI Workspace"
ALLOWED_EMAIL_DOMAIN=company.example
SESSION_COOKIE_NAME=ai_workspace_session
```

- `ORGANIZATION_NAME` is used in organization-aware prompts, greetings, and overview detection.
- `ASSISTANT_NAME` is the employee-facing product name.
- `ORGANIZATION_INITIAL` is the one-character mark used by the browser interface.
- `ORGANIZATION_ALIASES` lists names employees may use for the organization.
- `APP_NAME` is the API and process display name. It can match `ASSISTANT_NAME`.
- `ALLOWED_EMAIL_DOMAIN` controls the prototype login domain.
- `SESSION_COOKIE_NAME` prevents cookie collisions when installations share a host.

The browser obtains only safe display values from `/api/session`. Secrets and model-server settings are never included in that response.

## Knowledge-source variables

Approved public websites are configured as JSON:

```dotenv
KNOWLEDGE_SOURCES_JSON=[{"title":"Company overview","url":"https://www.company.example/about"}]
```

An empty list is the safe default. The ingestion script derives its host allowlist from this exact configuration and rejects hosts that are not listed.

Internal knowledge should be uploaded through the application and assigned to the correct team. Do not put document contents, credentials, or employee information into `.env`.

## Rebranding checklist

1. Copy `.env.example` to `.env`.
2. Set every branding and email-domain value.
3. Add only approved website sources.
4. Check the login page, sidebar, assistant avatar, greeting, prompt examples, and browser title.
5. Test an organization-overview question using every configured alias.
6. Replace example golden questions with organization-approved evaluation cases.
7. Generate new screenshots; do not reuse screenshots from another installation.

Ordinary rebranding should not require a source-code edit. A company name added directly to Python, JavaScript, HTML, tests, or documentation is a white-label regression.

