#!/bin/sh
# Manage who can sign in to the Finndex editor (https://travelwithfinn.uk/admin/).
#
#   ./deploy/editors.sh add <name>      # asks you to type their password twice
#   ./deploy/editors.sh temp <name>     # makes a random password and prints it
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
  temp)
    [ -n "${2:-}" ] || { echo "usage: $0 temp <name>"; exit 1; }
    PW=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
    # Sent over stdin so it never shows up in a process list on the server.
    printf '%s\n' "$PW" | ssh -i "$KEY" "$HOST" "sudo htpasswd -iB $FILE '$2'" 2>/dev/null
    echo "Login for $2"
    echo "  username: $2"
    echo "  password: $PW"
    echo "Change it later with: $0 add $2" ;;
  remove)
    [ -n "${2:-}" ] || { echo "usage: $0 remove <name>"; exit 1; }
    ssh -i "$KEY" "$HOST" "sudo htpasswd -D $FILE '$2'" ;;
  list)
    ssh -i "$KEY" "$HOST" "sudo cut -d: -f1 $FILE" ;;
  *)
    sed -n '2,7p' "$0"; exit 1 ;;
esac
