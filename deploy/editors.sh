#!/bin/sh
# Manage who can sign in to the Finndex editor (https://travelwithfinn.uk/admin/).
#
#   ./deploy/editors.sh add <name>      # asks you to type their password twice
#   ./deploy/editors.sh remove <name>
#   ./deploy/editors.sh list
set -eu

HOST=ubuntu@158.178.152.42
KEY="$HOME/Documents/key/ssh-key-2026-02-10.key"
FILE=/etc/nginx/finndex-editors

case "${1:-}" in
  add)
    [ -n "${2:-}" ] || { echo "usage: $0 add <name>"; exit 1; }
    ssh -t -i "$KEY" "$HOST" "sudo htpasswd -B $FILE '$2'" ;;
  remove)
    [ -n "${2:-}" ] || { echo "usage: $0 remove <name>"; exit 1; }
    ssh -i "$KEY" "$HOST" "sudo htpasswd -D $FILE '$2'" ;;
  list)
    ssh -i "$KEY" "$HOST" "sudo cut -d: -f1 $FILE" ;;
  *)
    sed -n '2,7p' "$0"; exit 1 ;;
esac
