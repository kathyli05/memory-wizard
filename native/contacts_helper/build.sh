#!/bin/sh
set -eu

# Interactive shells and Python environments sometimes export compiler search
# paths that load duplicate Apple module maps. The helper needs only the selected
# Apple toolchain, so discard those overrides.
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH
unset SDKROOT SWIFT_INCLUDE_PATHS TOOLCHAINS

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP="$ROOT/.build/MemoryWizardContacts.app"
MACOS="$APP/Contents/MacOS"
CLANG=$(/usr/bin/xcrun --find clang)
SDK=$(/usr/bin/xcrun --sdk macosx --show-sdk-path)
MODULE_CACHE="$ROOT/.build/clang-module-cache"

mkdir -p "$MACOS"
mkdir -p "$MODULE_CACHE"
cp "$ROOT/Info.plist" "$APP/Contents/Info.plist"
CLANG_MODULE_CACHE_PATH="$MODULE_CACHE" \
"$CLANG" \
    -fobjc-arc \
    -fblocks \
    -fmodules-cache-path="$MODULE_CACHE" \
    -isysroot "$SDK" \
    "$ROOT/main.m" \
    -framework Foundation \
    -framework Contacts \
    -Wl,-sectcreate,__TEXT,__info_plist,"$ROOT/Info.plist" \
    -o "$MACOS/MemoryWizardContacts"
/usr/bin/codesign --force --sign - "$APP"
