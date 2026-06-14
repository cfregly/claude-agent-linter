# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Use GitHub's private reporting: on the repository's **Security** tab, choose
**Report a vulnerability**. If that is unavailable, contact the maintainer
through [github.com/cfregly](https://github.com/cfregly).

Include the version or commit, what you found, and a minimal way to reproduce
it. Expect an acknowledgement within a few days.

## Scope

These tools are deterministic linters and demos. They read the files and specs
you point them at. They do not transmit your content anywhere on their own.
Where a tool can call the Anthropic API (an optional judge or a live example),
it does so only when you supply a key and ask for it. Keep keys in a local
`.env` that git ignores, and never commit one.
