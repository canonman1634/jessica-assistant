#!/bin/bash
# PreToolUse hook: blocks Read/Edit/Write on files holding live secrets/credentials.
input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

case "$file_path" in
  */credentials/google_credentials.json|*/credentials/google_token.json|*/.env|*/.env.*)
    echo "Blocked: $file_path contains live credentials." >&2
    exit 2
    ;;
esac

exit 0
