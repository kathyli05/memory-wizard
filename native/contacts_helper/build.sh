#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$ROOT/.build/MemoryWizardContacts.app"
MACOS="$APP/Contents/MacOS"

mkdir -p "$MACOS"
mkdir -p "$ROOT/.build/module-cache"
cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
CLANG_MODULE_CACHE_PATH="$ROOT/.build/module-cache" \
SWIFT_MODULECACHE_PATH="$ROOT/.build/module-cache" \
/usr/bin/swiftc \
    "$ROOT/main.swift" \
    -framework Contacts \
    -Xlinker -sectcreate \
    -Xlinker __TEXT \
    -Xlinker __info_plist \
    -Xlinker "$ROOT/Info.plist" \
    -o "$MACOS/MemoryWizardContacts"
/usr/bin/codesign --force --sign - "$APP"
