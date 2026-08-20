# Security Policy

## Supported Versions

`pytest-agent-trace` is pre-1.0. Only the latest published release on [PyPI](https://pypi.org/project/pytest-agent-trace/) is supported — please upgrade before reporting an issue.

## Reporting a Vulnerability

Please report security vulnerabilities privately through GitHub's
[Security Advisories](https://github.com/Davsooonowy/pytest-agent-trace/security/advisories/new)
rather than opening a public issue. This lets us investigate and publish a fix
before the details are public.

We'll acknowledge your report and follow up on next steps as soon as we can.
There's no bug bounty program — this is a small open-source project — but
we'll credit you in the advisory unless you'd rather stay anonymous.

## Scope

A couple of things worth knowing about this project's threat model, since
they affect what counts as a security issue here:

- Cassettes recorded from a real agent can contain whatever that agent's
  tools/LLM returned, including secrets, if you don't opt into
  [`Redactor`](README.md#redaction) at record time. That's a usage
  consideration, not a vulnerability in the library itself — see the
  README's Redaction section before committing cassettes recorded against
  real APIs.
- Replay (`LangGraphReplayer`) executes whatever a cassette says the model
  decided to do, including tool calls — don't replay a cassette you don't
  trust the origin of, the same way you wouldn't `pickle.load` untrusted
  data.
