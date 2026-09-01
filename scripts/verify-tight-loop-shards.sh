#!/bin/sh
# Deterministic acceptance proof for xcode-lab ~xl61. Read-only on the lab host.
set -eu

if [ "${1:-}" = "--help" ]; then
  echo "usage: verify-tight-loop-shards.sh"
  exit 0
fi
if [ "$#" -ne 0 ]; then
  echo "usage: verify-tight-loop-shards.sh" >&2
  exit 64
fi

host="leokwan@Leos-MacBook-Pro-5.local"
ssh -o BatchMode=yes -o ConnectTimeout=8 "$host" '/bin/sh -s' <<'LAB'
set -eu
export PATH=/opt/homebrew/bin:/Users/leokwan/bin:/usr/bin:/bin:/usr/sbin:/sbin

repo=/Users/leokwan/lab/resplit-ios-xl61-codex-20260830
xctestrun='/Users/leokwan/lab/xl61-dd/Build/Products/All Unit Tests_iphonesimulator26.5-arm64.xctestrun'
build=/Users/leokwan/lab/xl61-build.xcresult
core=/Users/leokwan/lab/xl61-core-retry.xcresult
receipt=/Users/leokwan/lab/xl61-receipt-retry.xcresult
build_log=/Users/leokwan/lab/xl61-build.log
core_log=${XL61_CORE_LOG:-/Users/leokwan/lab/xl61-core-retry.log}
receipt_log=${XL61_RECEIPT_LOG:-/Users/leokwan/lab/xl61-receipt-retry.log}

test -d "$repo"
test -z "$(git -C "$repo" status --porcelain)"
test "$(git -C "$repo" rev-parse HEAD)" = "$(git -C "$repo" rev-parse origin/main)"
test "$(git -C "$repo" rev-parse HEAD)" = 0b19e1f50ef2e8e2aacd0c2bc7b5d7c2a5b3bf7e
test "$(shasum -a 256 "$xctestrun" | awk '{print $1}')" = 02bef0446eb7acf334fca3e6d903c2844848f542280d387dfbc05f04d8784e16

summary_value() {
  xcrun xcresulttool get test-results summary --path "$1" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$2"
}
assert_summary() {
  bundle=$1 total=$2 passed=$3 failed=$4 skipped=$5
  test "$(summary_value "$bundle" result)" = Passed
  test "$(summary_value "$bundle" totalTestCount)" = "$total"
  test "$(summary_value "$bundle" passedTests)" = "$passed"
  test "$(summary_value "$bundle" failedTests)" = "$failed"
  test "$(summary_value "$bundle" skippedTests)" = "$skipped"
}

assert_summary "$core" 3698 3698 0 0
assert_summary "$receipt" 782 781 0 1
test "$(shasum -a 256 "$build/Info.plist" | awk '{print $1}')" = e0ef2297c62e594c9434bcd7fce0c8abacc615cdba91b307a3d1a876b76bb8f5
test "$(shasum -a 256 "$core/Info.plist" | awk '{print $1}')" = 17771a0070dd6686baa5a963383e095db78f0363c8cb1cd903a2beb02d43570b
test "$(shasum -a 256 "$receipt/Info.plist" | awk '{print $1}')" = a50d9c0690c0916e9a0e3bcbc8a2882bdd47b56bed4ad293776178f686f69df9

grep -F 'xbq: queueing [xl61-build-for-testing] via xcb-lock:' "$build_log" >/dev/null
grep -F 'build-for-testing' "$build_log" >/dev/null
grep -F -- '-derivedDataPath /Users/leokwan/lab/xl61-dd' "$build_log" >/dev/null
grep -F -- "-resultBundlePath $build" "$build_log" >/dev/null
grep -F '** TEST BUILD SUCCEEDED **' "$build_log" >/dev/null
grep -Fx 'real 71.83' "$build_log" >/dev/null
for log in "$core_log" "$receipt_log"; do
  test "$(grep -c CompileSwift "$log" || true)" = 0
done
grep -F 'test-without-building -only-testing:ResplitCoreTests' "$core_log" >/dev/null
grep -F 'test-without-building -only-testing:ReceiptSplitterTests' "$receipt_log" >/dev/null
grep -F "$xctestrun" "$core_log" >/dev/null
grep -F "$xctestrun" "$receipt_log" >/dev/null
grep -F '** TEST EXECUTE SUCCEEDED **' "$core_log" >/dev/null
grep -F '** TEST EXECUTE SUCCEEDED **' "$receipt_log" >/dev/null
grep -Fx 'real 84.89' "$core_log" >/dev/null
grep -Fx 'real 46.94' "$receipt_log" >/dev/null
printf '%s\n' 'XL61_VERIFY_PASS: clean origin/main worktree; one xctestrun; two no-compile passing shards'
LAB
