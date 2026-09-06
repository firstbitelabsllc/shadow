#!/bin/sh
# Install the optional Plan-B delivery runtime entries for the current user.
#
# Copies the two confined entrypoints into ~/.shadow/runtime/huddle-delivery/
# (or $SHADOW_HOME/runtime/huddle-delivery/) with owner-only permissions, and
# creates the sibling contacts directory. Refuses a symlinked runtime target.
# Capabilities are armed per use (ten-minute TTL) and are never installed by
# this script; see README.md for the closed contract.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
shadow_home=${SHADOW_HOME:-"$HOME/.shadow"}
runtime="$shadow_home/runtime/huddle-delivery"
contacts="$shadow_home/contacts"
if [ -L "$runtime" ] || [ -L "$shadow_home/runtime" ]; then
    echo "refusing symlinked runtime location" >&2
    exit 1
fi
mkdir -p -m 700 "$runtime" "$contacts"
for name in shadow-huddle-deliver-event.py shadow-contact-register.py; do
    tmp="$runtime/$name.installing.$$"
    cp "$repo/distribution/huddle-delivery/$name" "$tmp"
    chmod 600 "$tmp"
    mv -f "$tmp" "$runtime/$name"
done
echo "installed delivery entrypoints in $runtime"
