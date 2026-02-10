# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jekyll-based GitHub Pages site serving as the UBC GSS Finance and Accounting Guide. Deployed at `https://ubcgss.github.io/finance_accounting_guide/`.

## Build and Development

```bash
# Install dependencies
bundle install

# Run local dev server
bundle exec jekyll serve

# Build for production
bundle exec jekyll build
```

The site deploys automatically via GitHub Actions (`.github/workflows/pages.yml`) on push to `main`.

## Architecture

- **Theme**: [just-the-docs](https://github.com/just-the-docs/just-the-docs) v0.12.0
- **Content**: All pages are Markdown files under `docs/`, organized by topic
- **Navigation**: Controlled via YAML front matter (`nav_order`, `parent`, `has_children`)
- **Images**: Stored in `assets/images/`
- **Config**: `_config.yml` at repo root

## Adding New Pages

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

Child pages use:
```yaml
---
title: Page Title
layout: default
parent: Section Name
nav_order: N
---
```

## Content Sources

This guide draws from:
- GSS Bylaws (key sections: 8.5.6 FO duties, 11.x fiscal year/budget)
- GSS House-Finance Policy (HFC responsibilities, authorization procedures)
- Accounting and Procedures manual (Appendix I)
- `ubcgss/transition_guide` repo (operational how-tos)

## Domain Context

- **Fiscal year**: June 1 — May 31. Quarters: Q1 Jun-Aug, Q2 Sep-Nov, Q3 Dec-Feb, Q4 Mar-May
- **Key roles**: Financial Officer (FO), General Manager (GM), House-Finance Committee (HFC)
- **External bookkeeper**: Bickert Management Inc.
- **Software**: Zoho Expense, Zoho Vault, Zoho Books, Plooto, Vancity, Scotiabank, CRA My Business Account

## Callout Syntax

Use just-the-docs callouts in content:
```markdown
{: .important }
> This is an important note.

{: .tip }
> This is a helpful tip.

{: .deadline }
> This has a specific deadline.
```
