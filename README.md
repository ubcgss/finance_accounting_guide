# UBC GSS Finance & Accounting Guide - Update Workflow

## What This Repo Is

This repository contains the Jekyll source for the UBC GSS Finance and Accounting Guide site:

- Production URL: `https://ubcgss.github.io/finance_accounting_guide/`
- Deployment: GitHub Actions Pages workflow on push to `main`
- Content location: markdown files under `docs/`

This README is for maintainers updating the website with Codex in VS Code/Positron. It is not published on the website (`README.md` is excluded in `_config.yml`).

## 1) Install Python (macOS)

Check whether Python 3 is already installed:

```bash
python3 --version
```

If needed, install Python with Homebrew:

```bash
brew install python
python3 --version
```

## 2) Authenticate with GitHub CLI

Install GitHub CLI (`gh`) if needed:

```bash
brew install gh
```

Authenticate using the web flow:

```bash
gh auth login
gh auth status
```

## 3) Install Repo Tooling (Git + Ruby/Jekyll)

Install Ruby version management tools:

```bash
brew install rbenv ruby-build
```

Initialize `rbenv` in your shell (zsh):

```bash
echo 'eval "$(rbenv init - zsh)"' >> ~/.zshrc
source ~/.zshrc
```

Install and set Ruby `3.3.0` for this repo:

```bash
rbenv install 3.3.0
rbenv local 3.3.0
ruby --version
```

Install Bundler and project gems:

```bash
gem install bundler
bundle install
```

Note: CI uses Ruby `3.3` in `.github/workflows/pages.yml`, so local Ruby `3.3.x` is the safest match.

## 4) Clone and Open in VS Code/Positron

```bash
git clone https://github.com/ubcgss/finance_accounting_guide.git
cd finance_accounting_guide
```

Open the repo in your editor:

```bash
code .
# or
positron .
```

## 5) Update Content with Codex (VS Code/Positron)

- Ask Codex for exact markdown/doc edits.
- Review the proposed diff before accepting.
- Keep changes scoped to requested files.
- Re-run local checks before committing.

Reusable prompt template:

```text
Update [FILE PATH] with the following changes:
1) [CHANGE 1]
2) [CHANGE 2]
Constraints:
- Keep existing front matter and permalink.
- Preserve section order unless requested.
- Keep wording concise and policy-consistent.
After editing, summarize the exact diff and run relevant checks.
```

## 6) Preview Locally

Run the local site:

```bash
bundle exec jekyll serve
```

Open:

- `http://127.0.0.1:4000/finance_accounting_guide/`

Optional production-style build check:

```bash
bundle exec jekyll build
```

## 7) Commit and Push (Direct to main)

```bash
git pull --rebase origin main
git add [changed files]
git commit -m "Describe your update"
git push origin main
```

## 8) Confirm Deployment

- The workflow in `.github/workflows/pages.yml` runs on every push to `main`.
- In GitHub, check the Actions tab for successful `Deploy Jekyll site to Pages`.
- Confirm the update on:
  - `https://ubcgss.github.io/finance_accounting_guide/`

## Troubleshooting

- `bundler: command not found: jekyll`
  - Run `bundle install` in repo root, then retry `bundle exec jekyll serve`.
- Ruby version mismatch (Jekyll needs Ruby `>= 2.7`)
  - Use `rbenv local 3.3.0`, then run `bundle install` again.
- `gh auth` not logged in
  - Re-run `gh auth login` and confirm with `gh auth status`.
- Merge/rebase conflict on pull
  - Resolve conflicts in changed files, then continue with `git rebase --continue`.
