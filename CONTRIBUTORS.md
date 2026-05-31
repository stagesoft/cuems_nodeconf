<!--
***
SPDX-FileCopyrightText: 2026 Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->

# Contributing to cuems-nodeconf

Thank you for contributing to `cuems-nodeconf`. This document defines the full
contribution workflow. Follow it precisely — inconsistent processes make review
harder and slow down integration.

**Maintainers:**
- Ion Reguera — [@ibiltari](https://github.com/ibiltari)
- Adrià Masip — [@backenv](https://github.com/backenv)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Development Setup](#2-development-setup)
3. [Contribution Tiers](#3-contribution-tiers)
4. [Branch Naming](#4-branch-naming)
5. [Spec-First Requirement](#5-spec-first-requirement)
6. [TDD Workflow — Non-Negotiable](#6-tdd-workflow--non-negotiable)
7. [Commit Hygiene](#7-commit-hygiene)
8. [Developer Certificate of Origin](#8-developer-certificate-of-origin)
9. [Pull Request Requirements](#9-pull-request-requirements)
10. [Acceptance Criteria](#10-acceptance-criteria)
11. [Review Process](#11-review-process)
12. [Changelog Line](#12-changelog-line)
13. [Dependency Governance](#13-dependency-governance)
14. [License](#14-license)

---

## 1. Prerequisites

You need the following tools installed and working before you write a single line.

| Tool | Minimum version | Purpose |
|---|---|---|
| Python | 3.9 | Runtime language |
| git | 2.30 | Version control |
| Avahi daemon | any current | `avahi-daemon` + `avahi-utils` for integration testing |
| `zeroconf` (Python) | 0.38 | Zeroconf/mDNS library |
| `netifaces` (Python) | 0.11 | Network interface introspection |
| `pytest` | 7.0 | Test runner (aspirational; see §6) |
| `pytest-cov` | 4.0 | Coverage measurement |
| `ruff` | 0.4 | Linter and style checker |

Install the Python dependencies:

```bash
pip install zeroconf netifaces pytest pytest-cov ruff
```

Install the system dependencies (Debian/Ubuntu):

```bash
sudo apt-get install avahi-daemon avahi-utils acpid
```

Verify your environment:

```bash
python3 --version      # 3.9 or later
avahi-daemon --version # any
pytest --version       # 7.x or later
ruff --version         # 0.4 or later
```

---

## 2. Development Setup

```bash
# Clone the standalone repository
git clone https://github.com/stagesoft/cuems-nodeconf.git
cd cuems-nodeconf

# Or, if working within cuems-engine:
git clone --recurse-submodules https://github.com/stagesoft/cuems-engine.git
cd cuems-engine/cuems_nodeconf
```

> **Note on relative imports:** When working on `cuems-nodeconf` in isolation,
> the `from ..ConfigManager import …` and `from ..XmlReaderWriter import …` imports
> in `CuemsNodeConf.py` will fail because the parent package is absent. For unit
> tests, mock or shim these imports using `unittest.mock.patch`.

Verify the module is importable from the repo root (standalone mode — imports that
need the parent package will raise `ImportError`, which is expected):

```bash
python3 -c "from CuemsNode import CuemsNode, CuemsNodeDict; print('OK')"
python3 -c "from CuemsAvahiListener import CuemsAvahiListener; print('OK')"
```

Run the diagnostic utility against a live network to confirm Avahi is reachable:

```bash
python3 AvahiTool.py   # press any key to exit
```

---

## 3. Contribution Tiers

### Tier 1 — Trivial changes

Definition: a single-file change with no behavioural impact.

Examples: typo in a comment, missing full-stop in a log message, adding a docstring
to an existing function.

Process: branch → commit (DCO signed) → PR → one approval → merge.

### Tier 2 — Non-trivial changes

Definition: anything that adds, removes, or modifies observable behaviour — new
classes, changed method signatures, new or modified file paths, changed exit codes,
changed TXT record fields, changed XML schema.

Process: spec → discussion → branch → failing test → implementation → refactor →
PR → two approvals (or one maintainer approval after 5 business days) → merge.

**If your change is Tier 2 and you open a PR without a prior spec, it will be
closed without review.** Open a GitHub Discussion or an Issue first.

---

## 4. Branch Naming

Use the format `<type>/<short-description>`:

| Type | When to use |
|---|---|
| `feat/` | New feature or new behaviour |
| `fix/` | Bug fix |
| `refactor/` | Internal restructuring with no behavioural change |
| `docs/` | Documentation only |
| `chore/` | Maintenance (dependencies, CI, tooling) |
| `test/` | Tests only |

Examples:

```
feat/conf-server-json-schema
fix/update-service-mac-key
docs/readme-architecture
chore/add-ruff-config
```

Branch names must be lowercase, hyphen-separated, and not exceed 60 characters.
All branches target `main`, not `master` or any other branch.

---

## 5. Spec-First Requirement

For every Tier 2 change, open a GitHub Issue or Discussion **before writing code**.
The spec must answer:

1. **What** is changing and why. One paragraph; no implementation detail.
2. **Which files** are touched and what their new behaviour is.
3. **What the observable effect is** — Zeroconf TXT fields, exit codes, file paths,
   XML schema elements, or Python public API changes.
4. **What the acceptance test looks like** — one concrete scenario that proves the
   change works.

The spec is approved when a maintainer posts `spec: approved` on the Issue. Do not
open a PR before that label appears.

---

## 6. TDD Workflow — Non-Negotiable

> The test suite is aspirational: no automated tests exist yet. All Tier 2
> contributions are expected to add tests as part of the change. The workflow below
> describes the target state.

The sequence is **red → green → refactor**, without exception:

1. **Write a failing test** that captures the exact behaviour specified in the Issue.
   Commit it on its own with message `test: add failing test for <thing>`.
2. **Write the minimal implementation** that makes the test pass. Commit it with
   message `feat: implement <thing>`.
3. **Refactor** without breaking the test. Commit it with message `refactor: <what>`.
4. Run the full test suite and confirm it is green:
   ```bash
   pytest --cov=. --cov-report=term-missing
   ```
5. Confirm lint is clean:
   ```bash
   ruff check .
   ```

Coverage must not decrease across the PR. If coverage falls, add more tests before
requesting review.

Because `cuems-nodeconf` relies on a live Avahi daemon for integration behaviour,
tests that touch `CuemsNodeConf`, `CuemsAvahiListener`, or `Zeroconf` must mock all
network I/O. Use `unittest.mock.patch` or `pytest-mock`. Do not write tests that
require a real LAN.

---

## 7. Commit Hygiene

This project uses **Conventional Commits v1.0**
([conventionalcommits.org](https://www.conventionalcommits.org/en/v1.0.0/)).

### Format

```
<type>(<optional scope>): <short description>

[optional body — wrap at 72 characters]

[optional footers]
Signed-off-by: Full Name <email@example.com>
```

### Types

| Type | Use for |
|---|---|
| `feat` | New feature or new observable behaviour |
| `fix` | Bug fix |
| `refactor` | Internal restructuring, no behaviour change |
| `docs` | Documentation only |
| `test` | Tests only |
| `chore` | Maintenance (tooling, CI, dependencies) |
| `perf` | Performance improvement |

### Rules

- The **short description** is 72 characters or fewer, present-tense imperative
  ("add master lock file", not "added" or "adding").
- A **blank line** must separate the subject from the body.
- The **body** explains *why*, not *what* (the diff shows what).
- **Breaking changes** are indicated by a `!` after the type/scope
  (`feat!: change exit code contract`) and a `BREAKING CHANGE:` footer line.
- **One logical change per commit.** Do not bundle unrelated fixes.
- Do not use `--no-verify` to bypass commit hooks.

### Examples

```
fix(listener): use MAC instead of UUID as node dict key in update_service

update_service was calling get_mac() but then keying the nodes dict by
info.properties[b"uuid"], which did not match the key used by add_service.
The result was a KeyError on the first update event.
```

```
feat: add master.lock sentinel file

Operators and shell scripts need a lightweight way to detect the master
role without parsing network_map.xml. A zero-content file at
/etc/cuems/master.lock is created when master exits and removed when
a slave exits.
```

---

## 8. Developer Certificate of Origin

Every commit must carry a **DCO sign-off**.

```
Signed-off-by: Your Name <your.email@example.com>
```

Add it automatically with:

```bash
git commit -s -m "feat: my change"
```

By adding this line you certify that you wrote the change or otherwise have the
right to pass it on under the project's licence, as defined at
[developercertificate.org](https://developercertificate.org).

PRs that contain unsigned commits will be blocked until all commits are signed.
Amend unsigned commits locally with `git commit --amend -s` before pushing.

---

## 9. Pull Request Requirements

Before opening a PR, verify all of the following:

- [ ] All commits are DCO-signed.
- [ ] All commits follow Conventional Commits format.
- [ ] The branch is up to date with `main` (`git rebase origin/main`).
- [ ] `pytest --cov=. --cov-report=term-missing` passes with no regressions.
- [ ] `ruff check .` reports zero issues.
- [ ] Every new source file starts with the SPDX header (see §14).
- [ ] `CHANGELOG.md` contains a new entry (see §12).
- [ ] The PR description includes a link to the Issue/Discussion where the spec
      was approved (Tier 2 only).

### PR description template

```markdown
## What and why

<one paragraph from the spec>

## Changes

- `<file>`: <what changed>

## Testing

- `<test_file>`: <what each new test verifies>

## Checklist

- [ ] DCO sign-off on all commits
- [ ] Tests pass and coverage does not decrease
- [ ] `ruff check .` clean
- [ ] CHANGELOG entry added
- [ ] SPDX header on all new files
- [ ] Spec approved at: <Issue or Discussion URL>
```

---

## 10. Acceptance Criteria

A PR is ready to merge when all of the following are true:

| Gate | Requirement |
|---|---|
| Tests | `pytest` exits with code 0; no test is skipped or xfailed without a documented reason |
| Coverage | Branch and line coverage do not decrease relative to `main` |
| Lint | `ruff check .` reports zero issues |
| DCO | All commits carry `Signed-off-by` |
| Commits | All commits follow Conventional Commits v1.0 |
| SPDX | All new files have the SPDX header |
| CHANGELOG | One entry per logical change, in the correct format (§12) |
| Spec | Tier 2 PRs link to an approved spec |
| Review | At least one approval from a maintainer |

---

## 11. Review Process

- Open the PR against `main` on GitHub.
- Request review from [@ibiltari](https://github.com/ibiltari) or
  [@backenv](https://github.com/backenv).
- Address every review comment before the PR is considered for merge. Do not dismiss
  review comments unilaterally.
- If a review comment asks for a behaviour change, update the spec Issue as well.
- A Tier 1 PR requires one maintainer approval. A Tier 2 PR requires two approvals,
  or one maintainer approval if the PR has been open for five or more business days
  with no second reviewer available.
- Reviewers will use the following labels:
  - `r: approved` — ready to merge.
  - `r: changes requested` — must be addressed before re-review.
  - `r: question` — blocking if the question is about correctness; non-blocking if
    it is informational.
- The author merges after the final approval. Maintainers do not merge on the
  author's behalf unless the author is unavailable for more than 48 hours.

---

## 12. Changelog Line

Every Tier 2 PR (and any Tier 1 PR that fixes a user-visible bug) must add a line to
`CHANGELOG.md` under the `## Unreleased` heading before the PR is opened.

### Format

```markdown
#### Added
- `ClassName.method_name`: short description of what was added and why it matters.

#### Changed
- `ClassName.method_name`: old behaviour → new behaviour.
  Migration: <steps if any>.

#### Fixed
- `ClassName.method_name`: symptom. Root cause: short explanation.

#### Removed
- `ClassName.attribute`: deprecated since <version>. Superseded by <replacement>.
```

Use the exact class and method name as it appears in the source. If the change
touches a system file rather than a Python symbol, use the file path
(e.g. `network_map.xsd: added <port> element`).

---

## 13. Dependency Governance

`cuems-nodeconf` has no build system and no `requirements.txt` or `pyproject.toml`.
Dependencies are managed manually.

**Rules for adding a new dependency:**

1. Open a GitHub Issue proposing the dependency. Describe why it is needed, which
   existing alternative was rejected, and what the transitive dependency footprint is.
2. Prefer packages that are available as Debian packages (`python3-<name>`) so that
   the eventual Debian package build does not require a `pip install` step.
3. The Issue must be approved by a maintainer before the dependency appears in any
   commit.
4. Document the new dependency in the `## Installation → System dependencies` table
   in `README.md` and in `CONTRIBUTORS.md §1`.

**Rules for removing a dependency:**

1. Confirm zero callers in the entire codebase before removing.
2. Note the removal in `CHANGELOG.md` under `#### Removed`.

**Python standard library** is always preferred over third-party packages. If a
feature can be implemented with `socket`, `threading`, `subprocess`, `xml.etree`,
or another stdlib module with comparable effort, prefer it.

---

## 14. License

By contributing to this project you agree that your contributions are licensed under
the **GNU General Public License v3.0 or later** (SPDX: `GPL-3.0-or-later`), the
same licence as the project.

Every new source file you create must start with the following SPDX header:

**Python files (`.py`):**

```python
# SPDX-FileCopyrightText: <year> Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
```

**Markdown files (`.md`):**

```markdown
<!--
***
SPDX-FileCopyrightText: <year> Stagelab Coop SCCL
SPDX-License-Identifier: GPL-3.0-or-later
***
-->
```

**Shell scripts (`.sh`):**

```bash
# SPDX-FileCopyrightText: <year> Stagelab Coop SCCL
# SPDX-License-Identifier: GPL-3.0-or-later
```

**XML / XSD files:**

```xml
<!-- SPDX-FileCopyrightText: <year> Stagelab Coop SCCL -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
```

Replace `<year>` with the year you first created the file. Do not retroactively
change the year on files you are editing but did not create.

If you are contributing a file that is derived from a third-party source with a
different (but compatible) licence, state both the original licence and
`GPL-3.0-or-later` in the header and add a note to the PR description.
