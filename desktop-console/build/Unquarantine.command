#!/bin/bash
set -e
APP_NAME="Agentic Control Console.app"
TARGET="/Applications/$APP_NAME"

if [ ! -d "$TARGET" ]; then
  echo "Move '$APP_NAME' into /Applications first, then re-run this script."
  exit 1
fi

echo "Removing Gatekeeper quarantine from $TARGET"
xattr -dr com.apple.quarantine "$TARGET"
echo "Done. Opening app..."
open "$TARGET"
