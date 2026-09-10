# Working on this repository

These rules apply to anyone — human or agent — **editing this repository**. They are not
instructions for using the skill on your own projects, where your code is your own.

## This repository is public

`github.com/SionVerhoef/twincat-st` is world-readable, mirrored by anyone who clones it, and
installed as a submodule into other people's projects. Assume every commit is permanent and
already read by a stranger.

## Treat every line of real project code as if it were under NDA

Structured Text comes from real machines belonging to real customers. Handle all of it as
confidential by default — not only what someone explicitly marked as such.

**Never commit anything that identifies a customer, a site, a machine or a controller.**
That includes, in files *and* in commit messages, changelog entries, eval transcripts and
issue text:

- **Customer, site or end-user names**, machine numbers, serial numbers, project codes —
  including inside POU names, variable names, comments and file paths
- **IP addresses, AMS NetIDs, credentials, licence keys** in comments, GVLs or config
- **Process recipes, setpoints, cycle times, tuning parameters** — commercially sensitive
- **Safety logic tied to one installation** — interlock chains, override paths, alarm IDs
  that describe a specific plant

## Anonymise by substitution, not by deletion

The point is to remove identity while keeping the teaching value. Renaming a customer to
`Customer_A` and a machine to `Line1` costs nothing and preserves every structural signal
that matters — how the FB is shaped, how faults propagate, how state is sequenced.

**Names are stand-ins; structure is real.** The reason to ship real code is that it shows how
working code is actually organised, and that survives renaming intact. If a pattern only makes
sense with the original names in place, describe the pattern in prose instead.

Naming a *product* is fine and often necessary: "TwinCAT 4024", "AX8000", "TcUnit" describe
things anyone can buy or download. Naming *whose* machine it is, is not.

## Everything here must apply to everybody

This is a general-purpose skill, and its users work in shops that do not share one house
style. Every rule, convention and example must make sense to a reader with no connection to
the project it came from.

`examples/` deliberately carries three projects using three different naming conventions,
because **the project you are editing wins** — see `references/naming-conventions.md`. Keep it
that way. Do not promote one employer's internal standard to the only correct answer, and do
not write a rule that is really a preference without saying so.

## What you may use, and what you may not

**Research is not redistribution.** Read any source you lawfully can — PLCopen specs, Beckhoff
InfoSys, vendor sample projects. Copyright protects expression, not facts, rules, procedures or
APIs. So state that PLCopen N5 forbids a local name shadowing a global one; do not paste the
guideline's own paragraph explaining why, or a close paraphrase of it. That is what makes
`references/plcopen-rules.md` both legal and specific.

Before reproducing any source material here, check that material's own licence:

- **Permissive** (MIT, 0BSD, BSD-2, Apache-2) — may ship. Copy the upstream `LICENSE` into the
  folder and add an `ATTRIBUTIONS.md` row in the same commit.
- **Copyleft** (GPL/LGPL) — do not vendor; it would relicense this whole skill. Ask first.
- **Proprietary / all rights reserved** (InfoSys, blogs, forums) — research source only. Cite
  and link; reproduce no passages, tables, diagrams or screenshots.
- **Specs and standards** (PLCopen, IEC, OMAC) — the technical rule can be stated independently;
  the document's own text, tables, diagrams and examples still cannot. Rule identifiers and
  severities are facts about a published standard and may be cited as such.

Read the licence from the upstream `LICENSE` file, never a GitHub badge — `NOASSERTION` across
Beckhoff's GitHub estate generally resolves to Zero-Clause BSD. A citation is not permission.
Copyright clearance is not permission to scrape either — check a site's terms before automated
fetching. Spec PDFs, sample archives and other research copies stay on your machine and are
never committed here. `ATTRIBUTIONS.md` is the authority and carries the full table.

## Before adding any real code

`examples/README.md` carries the redaction checklist and the rules for a `house/` folder. Read
it first. Two gates, both hard:

1. **Licence** — see *What you may use* above. Files ship inside the skill, so they must
   be redistributable, and provenance goes into `ATTRIBUTIONS.md` in the same commit.
2. **Redaction** — as above. Your own house code needs no licence file, but still needs this.

## If something private has already been committed

**Stop and tell the maintainer.** Do not quietly delete it in a follow-up commit: on a public
repo the old blob stays reachable in history and on every clone and fork. Removing it needs a
history rewrite and a force-push, which is a decision for the maintainer, not for an agent.
