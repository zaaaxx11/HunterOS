#!/bin/bash
# backup_restore.sh — Hermes config backup & restore helper
# Usage: ./backup_restore.sh [backup|restore <backup_file>]

set -euo pipefail

CONFIG_PATH="$HOME/.hermes/config.yaml"
BACKUP_DIR="$HOME/.hermes/backups"

mkdir -p "$BACKUP_DIR"

backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/config.yaml.$timestamp"
    cp "$CONFIG_PATH" "$backup_file"
    echo "✅ Backed up to: $backup_file"
    
    # Keep only last 10 backups
    ls -t "$BACKUP_DIR"/config.yaml.* | tail -n +11 | xargs -r rm
    echo "🧹 Old backups cleaned (kept last 10)"
}

restore() {
    local backup_file="$1"
    if [[ ! -f "$backup_file" ]]; then
        echo "❌ Backup file not found: $backup_file"
        echo "Available backups:"
        ls -la "$BACKUP_DIR"/config.yaml.* 2>/dev/null || echo "  (none)"
        exit 1
    fi
    
    echo "🔄 Restoring from: $backup_file"
    cp "$backup_file" "$CONFIG_PATH"
    echo "✅ Restored. Run 'hermes config check' then restart Hermes."
}

case "${1:-}" in
    backup)
        backup
        ;;
    restore)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 restore <backup_file>"
            echo "Available backups:"
            ls -la "$BACKUP_DIR"/config.yaml.* 2>/dev/null || echo "  (none)"
            exit 1
        fi
        restore "$2"
        ;;
    list)
        ls -la "$BACKUP_DIR"/config.yaml.* 2>/dev/null || echo "No backups found"
        ;;
    *)
        echo "Usage: $0 {backup|restore <file>|list}"
        exit 1
        ;;
esac