## Description

Describe the change and its user or developer impact.

## Motivation and context

Explain the problem, link the related issue and note alternatives considered.

## Verification

List the automated checks and manual interactions used to validate the change.

- [ ] `ruff check app scripts tests`
- [ ] `python -m pytest -q`
- [ ] JavaScript syntax checks
- [ ] Browser verification when the interface changed

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation
- [ ] Security or configuration

## Safety checklist

- [ ] I branched from and am targeting `dev` unless this is a hotfix.
- [ ] I added or updated tests for behavior changes.
- [ ] I updated relevant documentation.
- [ ] I did not include credentials, internal data, conversations, uploads or model files.
- [ ] Department access is enforced before retrieval.
- [ ] Important external actions still require explicit confirmation.
- [ ] Visible orchestration progress reflects work that actually ran.

## Screenshots

Add before/after images for visual changes when appropriate.
