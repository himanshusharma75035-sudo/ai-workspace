# Project Context

## Purpose

OpenSource AI Workspace explores how non-technical employees can use AI in a familiar language without selecting models or learning technical prompting. One interface accepts speech or text, coordinates approved AI helpers, uses permitted company knowledge and returns a checked response.

## Intended users

The prototype is designed for a small internal evaluation across business, operations, finance, accounts, customer support, engineering, HR and legal/compliance teams.

## Intended tasks

- Answer questions using approved information.
- Draft and improve emails, documents and other content.
- Help design automations by asking for missing requirements and controls.
- Prepare—but not currently execute—approved external actions.

## Knowledge and personalization

- New users provide their team, role, responsibilities, recurring tasks and goals.
- This information is editable context, not secret model retraining.
- Public and department knowledge are stored separately.
- Access is checked before retrieval.
- Conversation history is scoped to the signed-in user.

## Languages

The interface supports English, Hindi, Hinglish, Bengali, Marathi, Gujarati, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia, Assamese and Urdu selections.

The selection changes interface text, browser speech-recognition locale and answer instructions. Audio is not stored by the application.

## Model roles

The default self-hosted configuration uses:

- `qwen3:0.6b` for lightweight planning.
- `embeddinggemma` for multilingual semantic retrieval.
- `qwen3:4b` for preferred final answers.
- `qwen3:1.7b` as a fallback answer model.

Model names are configuration choices and should be changed only after quality, speed, license and hardware evaluation.

## Access and action policy

- The first prototype user becomes the owner.
- Other users request a team and require owner approval.
- Every team has a separate SQLite knowledge database and upload location.
- External actions require confirmation and remain simulations in this version.

## Authentication direction

The demonstration login is restricted to a configured email domain. It must be replaced with an approved OIDC/SSO flow and production session controls before wider use.
