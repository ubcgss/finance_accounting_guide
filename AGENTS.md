# AGENTS.md

This file provides guidance to Codex and other AI agents when working with code or content in this repository.

Keep `AGENTS.md` and `CLAUDE.md` synchronized when changing project conventions, architecture notes, build commands, or deployment steps.

## Project type

**Development** - Jekyll-based GitHub Pages documentation site.

This repository contains the UBC Graduate Student Society (GSS) Finance and Accounting Guide, an internal operations guide for standardized finance, bookkeeping, reporting, payroll, and transition procedures.

Production URL: `https://ubcgss.github.io/finance_accounting_guide/`

## Working rules

- Run commands from the repo root.
- Keep changes scoped to the requested content, config, or workflow files.
- Prefer editing existing Markdown pages over adding new pages unless the information is clearly a new topic.
- Preserve existing YAML front matter fields unless the navigation, permalink, or layout intentionally changes.
- Use concise, policy-consistent language suitable for GSS staff and officers.
- Do not commit generated Jekyll output from `_site/`.
- Do not revert unrelated local changes.
- After content or site changes, suggest the standard GitHub workflow: `git add`, `git commit`, `git pull --rebase origin main`, `git push origin main`.

## Commands

**Install dependencies:**
```bash
bundle install
```

**Run local development server:**
```bash
bundle exec jekyll serve
```

Preview locally at `http://127.0.0.1:4000/finance_accounting_guide/`.

**Build for production:**
```bash
bundle exec jekyll build
```

## Architecture

- **Site generator:** Jekyll
- **Theme:** `just-the-docs` v0.12.0
- **Config:** `_config.yml`
- **Content:** Markdown pages under `docs/`, plus the homepage at `index.md`
- **Navigation:** YAML front matter using `nav_order`, `parent`, `has_children`, and `permalink`
- **Images and files:** `assets/images/` and `assets/docs/`
- **Deployment:** GitHub Actions workflow at `.github/workflows/pages.yml`, triggered on pushes to `main`

## Adding or Updating Pages

Parent pages use this front matter pattern:
```yaml
---
title: Section Name
layout: default
nav_order: N
has_children: true
permalink: /section-name/
---
```

Child pages use this front matter pattern:
```yaml
---
title: Page Title
layout: default
parent: Section Name
nav_order: N
---
```

When adding pages:
- Choose a stable permalink for parent pages.
- Match the naming and structure used by neighboring pages.
- Keep navigation order predictable and avoid duplicate `nav_order` values within the same section when possible.
- Place reusable documents in `assets/docs/` and screenshots or instructional images in `assets/images/`.

## Content Sources

This guide draws from:
- GSS Bylaws, especially Financial Officer duties and fiscal year or budget provisions
- GSS House-Finance Policy
- Accounting and Procedures manual, including Appendix I
- Operational guidance from the `ubcgss/transition_guide` repository
- Current GSS finance team practices, when provided by the user

## Domain Context

- **Fiscal year:** June 1 to May 31
- **Quarters:** Q1 Jun-Aug, Q2 Sep-Nov, Q3 Dec-Feb, Q4 Mar-May
- **Key roles:** Financial Officer (FO), General Manager (GM), House-Finance Committee (HFC)
- **External bookkeeper:** Bickert Management Inc.
- **Software and services:** Zoho Expense, Zoho Vault, Zoho Books, Plooto, Vancity, Scotiabank, CRA My Business Account

## Callout Syntax

Use `just-the-docs` callouts in content:
```markdown
{: .important }
> This is an important note.

{: .tip }
> This is a helpful tip.

{: .note }
> This is a general note.

{: .deadline }
> This has a specific deadline.
```

Callout colors are configured in `_config.yml`.

## Completion Criteria

For content-only changes:
- Review affected Markdown pages for clear headings, correct links, and preserved front matter.
- Run `bundle exec jekyll build` when dependencies are installed or when navigation, links, config, assets, or multiple pages changed.

For config, theme, asset, or workflow changes:
- Run `bundle exec jekyll build`.
- Check that deployment assumptions still match `.github/workflows/pages.yml`.

Report changed files, validation run, and any known gaps.
