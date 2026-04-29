#!/usr/bin/env zsh
# scripts/first-time-setup.sh — Chorus host bootstrap.
#
# Idempotent and non-interactive. Installs `just`, `uv`, Python 3.14, and
# `prek`, then syncs the project, copies `.env.example` to `.env` if needed,
# and registers git hooks. Reports any missing host tools (docker, gh) but
# does not attempt to install them — those decisions belong to the operator.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h}"
cd "$REPO_ROOT"

echo "=== Chorus — first-time setup ==="
echo ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

have() { command -v "$1" >/dev/null 2>&1 }

# Pick the right package manager when one is available.
detect_pm() {
    if [[ "$OSTYPE" == darwin* ]] && have brew; then
        echo brew
    elif have pacman; then
        echo pacman
    elif have apt-get; then
        echo apt
    else
        echo none
    fi
}

PM="$(detect_pm)"

# ---------------------------------------------------------------------------
# just
# ---------------------------------------------------------------------------

if have just; then
    echo "[OK] just: $(just --version)"
else
    echo "[..] Installing just..."
    if have cargo; then
        cargo install just
    else
        case "$PM" in
            brew)   brew install just ;;
            apt)    sudo apt-get update && sudo apt-get install -y just ;;
            pacman) sudo pacman -S --noconfirm just ;;
            *)
                curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
                    | bash -s -- --to "$HOME/.local/bin"
                export PATH="$HOME/.local/bin:$PATH"
                ;;
        esac
    fi
    echo "[OK] just installed: $(just --version)"
fi

# ---------------------------------------------------------------------------
# uv
# ---------------------------------------------------------------------------

if have uv; then
    echo "[OK] uv: $(uv --version)"
else
    echo "[..] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    [[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"
    export PATH="$HOME/.local/bin:$PATH"
    echo "[OK] uv installed: $(uv --version)"
fi

# ---------------------------------------------------------------------------
# Python 3.14 (pyproject.toml requires-python = >=3.14)
# ---------------------------------------------------------------------------

if uv python find 3.14 >/dev/null 2>&1; then
    echo "[OK] Python 3.14: $(uv python find 3.14)"
else
    echo "[..] Installing Python 3.14 via uv..."
    uv python install 3.14
    echo "[OK] Python 3.14 installed"
fi

# ---------------------------------------------------------------------------
# prek (pre-commit-compatible Rust hook runner)
# ---------------------------------------------------------------------------

if have prek; then
    echo "[OK] prek: $(prek --version 2>/dev/null || echo present)"
else
    echo "[..] Installing prek..."
    if have cargo; then
        cargo install prek
    else
        uv tool install prek
    fi
    echo "[OK] prek installed"
fi

# ---------------------------------------------------------------------------
# Sync project
# ---------------------------------------------------------------------------

if [[ -f "pyproject.toml" ]]; then
    echo "[..] Syncing project (uv sync --all-extras)..."
    uv sync --all-extras
    echo "[OK] Project synced"
fi

# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------

if [[ -f ".env" ]]; then
    echo "[OK] .env exists"
elif [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "[OK] .env created from .env.example"
fi

# ---------------------------------------------------------------------------
# Register git hooks
# ---------------------------------------------------------------------------

if [[ -d ".git" ]] && have prek; then
    echo "[..] Registering git hooks via prek..."
    prek install >/dev/null
    echo "[OK] git hooks registered"
fi

# ---------------------------------------------------------------------------
# Verify host-managed tools (do not install)
# ---------------------------------------------------------------------------

MISSING=()
have docker || MISSING+=("docker")
docker compose version >/dev/null 2>&1 || MISSING+=("docker compose v2 plugin")
have git || MISSING+=("git")
have gh || MISSING+=("gh (GitHub CLI)")

if (( ${#MISSING[@]} > 0 )); then
    echo ""
    echo "[!!] Missing host tools (install via your package manager):"
    for tool in "${MISSING[@]}"; do
        echo "      - $tool"
    done
fi

echo ""
echo "Done. Run 'just up' to start the local stack."
