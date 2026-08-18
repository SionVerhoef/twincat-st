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

## Before adding any real code

`examples/README.md` carries the redaction checklist and the rules for a `house/` folder. Read
it first. Two gates, both hard:

1. **Licence** — files ship inside the skill, so they must be redistributable. Copyleft or
   vendor-sample code relicenses or contaminates the whole repo. Record provenance in
   `ATTRIBUTIONS.md`, read from the upstream `LICENSE` file rather than a badge.
2. **Redaction** — as above. Your own house code needs no licence file, but still needs this.

## If something private has already been committed

**Stop and tell the maintainer.** Do not quietly delete it in a follow-up commit: on a public
repo the old blob stays reachable in history and on every clone and fork. Removing it needs a
history rewrite and a force-push, which is a decision for the maintainer, not for an agent.
