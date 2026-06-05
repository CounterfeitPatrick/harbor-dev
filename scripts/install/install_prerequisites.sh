#!/usr/bin/env bash
# harbor host-side prerequisites: uv.
#
# Detects what is already installed and only does what is missing.
# uv is installed for the invoking (non-root) user.
#
# Usage:
#     ./scripts/install/install_prerequisites.sh
#     ./scripts/install/install_prerequisites.sh --skip-uv
#
# Supported distros: Ubuntu 20.04 / 22.04 / 24.04, Debian 11 / 12.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKIP_UV=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [--skip-uv] [-h|--help]

Installs the host-side tool harbor needs:
    1. uv      (no sudo, drives env-generator's setup_uv.sh)

Each step is idempotent — re-running is safe.
After install, log out and back in so the uv PATH takes effect.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --skip-uv)      SKIP_UV=1 ;;
        -h|--help)      usage; exit 0 ;;
        *)              echo "Unknown flag: $arg"; usage; exit 1 ;;
    esac
done

echo "=========================================="
echo "  harbor prerequisites install"
echo "=========================================="
echo ""

# uv (no sudo path; if running under sudo, install for SUDO_USER)
if [ "$SKIP_UV" = 1 ]; then
    echo "(skipping uv per --skip-uv)"
else
    echo "--- uv ---"
    if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
        sudo -u "$SUDO_USER" bash "$SCRIPT_DIR/install_uv.sh"
    else
        bash "$SCRIPT_DIR/install_uv.sh"
    fi
fi
echo ""

echo "=========================================="
echo "  All steps complete"
echo "=========================================="
echo ""
echo "Next:"
echo "  1. Log out and back in so the uv PATH takes effect."
echo "  2. In Claude Code:"
echo "        /plugin marketplace add YufengJin/claude-harbor"
echo "        /plugin install harbor@harbor"
echo "  3. /help  (should list the /harbor commands)"
