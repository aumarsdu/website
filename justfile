set shell := ["bash", "-uc"]

doctor:
    @echo "Repository root: $(git rev-parse --show-toplevel)"
    @echo
    @echo "Git status:"
    @git status --short --branch
    @echo
    @echo "Docker contexts:"
    @docker context ls || true
    @echo
    @echo "Tool versions:"
    @git --version || true
    @just --version || true
    @node --version || true
    @npm --version || true
    @python3 --version || true

check-helipei-tools:
    cd knowledge/helipei-official/tools-src && npm ci && npm run check && npm run lint && npm run build

secret-scan:
    @command -v gitleaks >/dev/null || { echo "gitleaks is not installed. Install it before running secret-scan."; exit 127; }
    gitleaks detect --source . --redact --no-git

list-boundaries:
    @echo "knowledge/helipei-official/          static official site and OSS deploy target"
    @echo "knowledge/helipei-official/tools-src/ React/Vite/TypeScript tools source"
    @echo "knowledge/helipei-official/tools/     generated build output; ignored; do not edit"
    @echo "scraper/集思未来/                       local experimental crawler workspace; ignored"
    @echo "directories with nested .git/          independent work areas unless explicitly scoped"
