import XCTest
@testable import ABCFireIR

final class SessionStoreTests: XCTestCase {
    func testRiderAttachesToChosenNotPeer() throws {
        let store = SessionStore.create(roughIntent: "help with dinner")
        let opts = [
            BeliefOption(id: "A", label: "Use fridge inventory", rationale: "inventory-first"),
            BeliefOption(id: "B", label: "Order takeout", rationale: "delegate cook"),
            BeliefOption(id: "C", label: "Cook 20-min recipe", rationale: "simple cook"),
        ]
        try store.appendNode(BeliefNode(prompt: "What kind of help?", mode: .menu, options: opts))
        let chosen = try store.choose(optionId: "A", riderText: "no dairy")
        XCTAssertEqual(chosen.status, .chosen)
        XCTAssertEqual(chosen.riderText, "no dairy")
        XCTAssertEqual(store.stack.constraints, ["no dairy"])
        XCTAssertEqual(store.stack.nodes.last?.options.count, 3)
        XCTAssertNil(store.stack.nodes.last?.options.first(where: { $0.id == "rider" }))
        XCTAssertEqual(store.stack.nodes.last?.options.filter { $0.status == .discarded }.count, 2)
    }

    func testDiskResumeRestoresSession() throws {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("kitchen-ir-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: url) }
        let store = SessionStore.create(roughIntent: "ship StrongYes this week", fileURL: url)
        try store.appendNode(
            BeliefNode(
                prompt: "What outcome?",
                mode: .menu,
                options: [
                    BeliefOption(id: "A", label: "Fix crash", rationale: "debug"),
                    BeliefOption(id: "B", label: "Ship polish", rationale: "ui"),
                    BeliefOption(id: "C", label: "New feature", rationale: "feat"),
                ]
            )
        )
        _ = try store.choose(optionId: "B", riderText: "empty-state only")
        try store.save()
        let sessionId = store.stack.sessionId

        let reloaded = try SessionStore.load(from: url)
        XCTAssertEqual(reloaded.stack.sessionId, sessionId)
        XCTAssertEqual(reloaded.stack.constraints, ["empty-state only"])
        XCTAssertEqual(reloaded.stack.nodes.count, 1)
        XCTAssertEqual(reloaded.stack.nodes[0].selected?.id, "B")
    }

    func testDistinctnessRejectsSynonymSpam() {
        // Near-synonym spam shares core tokens (help + dinner) → low Jaccard distance.
        let bad = ["help dinner tonight", "help dinner now", "help dinner please"]
        XCTAssertFalse(Distinctness.allPairsDistinct(labels: bad, minDistance: 0.55))
        let good = ["Use fridge inventory", "Order takeout budget", "Cook 20-min recipe"]
        XCTAssertTrue(Distinctness.allPairsDistinct(labels: good, minDistance: 0.55))
    }

    func testDiscardLastNodeEditable() throws {
        let store = SessionStore.create(roughIntent: "x")
        try store.appendNode(
            BeliefNode(
                prompt: "p",
                mode: .menu,
                options: [
                    BeliefOption(id: "A", label: "Alpha path one", rationale: "a"),
                    BeliefOption(id: "B", label: "Beta path two", rationale: "b"),
                ]
            )
        )
        try store.discardLastNode()
        XCTAssertTrue(store.stack.nodes.isEmpty)
    }
}
