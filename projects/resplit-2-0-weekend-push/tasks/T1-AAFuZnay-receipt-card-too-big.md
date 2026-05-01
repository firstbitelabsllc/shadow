# T1 — AAFuZnay: Receipt detail card "way too fucking big"

**Status:** [in_progress]
**Priority:** P0 (Saturday parallel-dispatchable)
**Claim:** `claimed_by: claude-opus-4-7-rios-640471` `claimed_at: 2026-05-01T13:01:11Z` — first writer wins; if both fields are empty, claim by editing this line atomically (pull → edit → commit → push) with your agent_id.
**ASC ID:** AAFuZnay
**DerivedData namespace:** `/tmp/resplit-dd-T1-${RANDOM}` (your worktree must export `RESPLIT_DD_PATH` to this; per `/bigapple` build isolation rule)

## Reporter Says

> "way too fucking big make them one row side by side and adjust copy"

## Surface guess

Receipt detail header card OR wrap-up sheet (two stacked tiles needing horizontal flex). Verify by `grep -rn "receiptDetail\|wrapUpSheet\|HeaderCard"` in `ResplitCore/ReceiptDetail/` and inspecting the two largest tiles.

## Investigation

See `.cursor/plans/investigations/asc-AAFuZnay-receipt-card-too-big-2026-05-01.md` (you must create this if missing — sibling agent stubs the file).

## Fix Spec (filled by claimer)

- [ ] Identify the two stacked tiles
- [ ] Convert VStack → HStack (or use `.gridCellColumns(2)` if Grid layout)
- [ ] Adjust copy per reporter intent (likely shorter labels)
- [ ] file:line of the change

## Tests (MT-5 required)

- [ ] XCTest snapshot or `XCTAssertEqual(layout.axis, .horizontal)` regression

## Visual proof

- [ ] BEFORE: `docs/autobot-evidence/2026-05-0X-T1-AAFuZnay/before.jpg`
- [ ] AFTER: `docs/autobot-evidence/2026-05-0X-T1-AAFuZnay/after.jpg`

## Ship gate

- Local build clean (`tuist xcodebuild build -scheme 'Resplit Debug' -derivedDataPath /tmp/resplit-dd-T1-${RANDOM}`)
- MT-5 regression test green
- Visual proof committed
- PR draft → @graphite review → resolve threads → ready → auto-merge

## Cross-references

- Master plan: `~/Development/vidux/projects/resplit-2-0-weekend-push/PLAN.md` row T1
- Multi-platform mega plan: `~/Development/resplit-web/vidux/resplit-2.0-launch/PLAN.md` (PR #541)

## Progress

- 2026-05-01T13:01Z (claude-opus-4-7-rios-640471, iter 1) — claimed T1. Phase A grep on `ReceiptDetailShellView.swift` and `ReceiptDetailShellContent.swift` returned no `VStack|HStack|HeaderCard|MerchantCard|TotalCard` matches — header card layout isn't in those files. Surface candidates remain: `ResplitCore/UI/LiveSplit/WrapUpSheet.swift` (live-split wrap-up, not detail) OR a header view nested inside `ReceiptDetailView.swift` itself OR in a separate `ResplitCore/ReceiptDetail/Receipt Items/` or `Summary/` subfolder. **Next wakeup**: dispatch `/autobot-resplit` to launch the sim, navigate to a Receipt detail screen with reporter's specific case (likely "two stacked merchant + total tiles"), `snapshot_ui` it, identify the two-tile surface visually, then back-trace to the SwiftUI file for the Fix Spec. Scheduled wakeup at ~13:26Z.

- 2026-05-01T13:08Z (claude-opus-4-7-rios-640471, iter 1 cont) — Phase A continued via deeper grep. Identified `ReceiptDetailView.swift` main body structure: VStack(spacing: 0) at line 53 wrapping `bodyView` (lines 200-280) + `footerView`. The bodyView composes `ReceiptParticipantsHeader` (line 235) + conditional `ReceiptScanHeroImage` (line 266) + merchant receipt thumbnail. **Two-tile candidates**: (a) hero photo + participants header stacked vertically — make side-by-side, OR (b) something inside ReceiptParticipantsHeader.swift (separate file at `ResplitCore/ReceiptDetail/Contacts Header/ReceiptParticipantHeader.swift`), OR (c) a different surface (wrap-up sheet, settle-up). **Cannot disambiguate without sim visual.** Per /vidux Principle 5 (no guessing), refusing to ship Fix Spec until sim confirms. Iter 2 wakeup mandate stands: dispatch /autobot-resplit, launch Dev App with mocked-data receipt, snapshot_ui the receipt detail screen, identify the actual two-tile pattern visually, back-trace to file:line, then write Fix Spec.
