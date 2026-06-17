# AGENTS.md — AI Native Development Guide

## 1. Repository Shape

This directory is a local-only archive / multi-project workspace. It is not a
Git synchronization target. Treat directory boundaries as important. Do not
assume a change in one project should affect another project.

Key directories:

- `knowledge/helipei-official/`: static official site and Aliyun OSS deploy target.
- `knowledge/helipei-official/tools-src/`: primary React / Vite / TypeScript tools source.
- `knowledge/helipei-official/tools/`: generated frontend build output. Do not edit by hand.
- `scraper/集思未来/`: local experimental crawler workspace. It is ignored by the root
  repository and is not part of root-repo delivery.
- `helipei-official/*workshop/`, `*workshop/`, `temp_*`, and directories that contain
  their own `.git/`: independent or temporary work areas unless explicitly scoped by
  the user.

## 2. Safety Rules

- Do not read, print, copy, summarize, or commit values from `.env`, `.env.*`,
  tokens, cookies, private keys, passwords, or production credentials.
- If a suspicious secret is found, report only the file path, variable/key type,
  and risk level. Do not output the value.
- Do not run deploy commands, destructive Git commands, force pushes, bulk deletes,
  or history rewrites unless the user explicitly authorizes the exact action.
- Do not stage, commit, push, merge, or rebase unless explicitly requested.
- Do not treat this directory as a deliverable Git workspace. By default, avoid
  Git synchronization actions for this folder, including staging, committing,
  pushing, pulling, rebasing, or merging.
- Before changing files, inspect repository state with:

```bash
pwd
git status --short --branch || true
git rev-parse --show-toplevel || true
```

## 3. Default Commands

Run commands from the repository root unless noted.

```bash
just doctor
just check-helipei-tools
just secret-scan
```

Command meanings:

- `just doctor`: show repo root, Git status, Docker context, and common tool versions.
- `just check-helipei-tools`: run the TypeScript / Vite quality gate for
  `knowledge/helipei-official/tools-src`.
- `just secret-scan`: run gitleaks with redacted output. This requires `gitleaks`
  to be installed locally.
- `just list-boundaries`: print the project boundary summary from this guide.

## 4. Ignored and Generated Paths

The root `.gitignore` intentionally ignores:

- `.env`, `.env.*`, while allowing `.env.example`
- `.agents/`, `.trae/`
- `dist/`, `build/`, `.cache/`, `node_modules/`
- `output/`, `output_*/`, and nested output directories
- `knowledge/helipei-official/tools/`
- `scraper/集思未来/`
- `temp_*/`

Do not re-add ignored build output unless the user explicitly changes the delivery
model.

## 5. Quality and Delivery Expectations

- For React/Vite tools work, run `just check-helipei-tools`.
- For static site deploy code, review `.github/workflows/deploy-helipei-official-oss.yml`
  and `knowledge/helipei-official/deploy_aliyun.py`; do not deploy without explicit
  authorization.
- For local crawler work under `scraper/集思未来/`, use that subproject's own guide and
  commands. It is outside root Git delivery by default.
- Keep generated artifacts out of source review unless they are explicitly requested.
