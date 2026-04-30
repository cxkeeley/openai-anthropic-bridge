#!/bin/bash
# install.sh — Claude Scaffolding Toolkit Installer
#
# Creates symlinks from ~/.claude/ to this repo.
# Run from the repo root: ./install.sh
#
# Creates:
#   ~/.claude/skills   → skills/
#   ~/.claude/rules    → rules/
#   ~/.claude/bin      → bin/
#   ~/.claude/CLAUDE.md → CLAUDE.md
#   ~/.claude/settings.json ← COPIED (not symlinked, Claude Code writes to it)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "=== Claude Scaffolding Toolkit Installer ==="
echo "Repo: $REPO_DIR"
echo "Target: $CLAUDE_DIR"
echo ""

# Create ~/.claude if it doesn't exist
mkdir -p "$CLAUDE_DIR"

# Function to create or update a symlink
link() {
    local src="$1"
    local dst="$2"
    if [ -L "$dst" ]; then
        echo "  Updating symlink: $dst"
        rm "$dst"
    elif [ -e "$dst" ]; then
        echo "  Backing up existing: $dst → $dst.bak"
        mv "$dst" "$dst.bak"
    fi
    ln -s "$src" "$dst"
    echo "  Linked: $dst → $src"
}

# Symlink skills, rules, bin
link "$REPO_DIR/skills"  "$CLAUDE_DIR/skills"
link "$REPO_DIR/rules"   "$CLAUDE_DIR/rules"
link "$REPO_DIR/bin"     "$CLAUDE_DIR/bin"

# Symlink CLAUDE.md
link "$REPO_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"

# COPY settings.json (Claude Code writes to it during sessions)
if [ -f "$CLAUDE_DIR/settings.json" ]; then
    echo "  Backing up existing settings: $CLAUDE_DIR/settings.json → $CLAUDE_DIR/settings.json.bak"
    cp "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/settings.json.bak"
fi
cp "$REPO_DIR/settings.json" "$CLAUDE_DIR/settings.json"
echo "  Copied: $CLAUDE_DIR/settings.json"

# Make all bin scripts executable
chmod +x "$REPO_DIR/bin/"*
echo "  Made bin scripts executable"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Restart Claude Code to pick up the new settings"
echo "  2. For each new project, copy the project template:"
echo "       cp $REPO_DIR/project-template/CLAUDE.md /path/to/project/CLAUDE.md"
echo "  3. Fill in the project-specific sections in that CLAUDE.md"
echo ""
