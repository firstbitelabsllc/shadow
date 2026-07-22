import XCTest
import ABCFireIR
@testable import ABCFireGate

final class FireGateTests: XCTestCase {
    func makeReadyStack() throws -> ChoicePathStack {
        let store = SessionStore.create(roughIntent: "kitchen dogfood")
        try store.appendNode(
            BeliefNode(
                prompt: "Outcome?",
                mode: .menu,
                options: [
                    BeliefOption(id: "A", label: "Draft only packet", rationale: "safe"),
                    BeliefOption(id: "B", label: "Mutate worktree", rationale: "code"),
                    BeliefOption(id: "C", label: "External send", rationale: "msg"),
                ]
            )
        )
        _ = try store.choose(optionId: "A", riderText: "StrongYes week")
        return store.stack
    }

    func testDryRunRequiredBeforeHighBlastSeal() throws {
        var stack = try makeReadyStack()
        let gate = FireGate(confirmWord: "IGNITE")
        XCTAssertThrowsError(
            try gate.seal(stack: &stack, blastTier: .mutate, confirmWord: "IGNITE")
        ) { err in
            XCTAssertEqual(err as? FireGateError, .dryRunRequired)
        }
        let dry = try gate.presentDryRun(stack: stack, blastTier: .mutate)
        XCTAssertTrue(dry.packetPreviewJSON.contains("kitchen dogfood"))
        let packet = try gate.seal(stack: &stack, blastTier: .mutate, confirmWord: "IGNITE")
        XCTAssertEqual(stack.status, .fired)
        XCTAssertEqual(packet.sessionId, stack.sessionId)
        XCTAssertTrue(gate.invokeExecutorStub())
        XCTAssertEqual(gate.executorInvocations, 1)
    }

    func testWrongConfirmWordRejects() throws {
        var stack = try makeReadyStack()
        let gate = FireGate(confirmWord: "IGNITE")
        _ = try gate.presentDryRun(stack: stack, blastTier: .draftOnly)
        XCTAssertThrowsError(
            try gate.seal(stack: &stack, blastTier: .draftOnly, confirmWord: "FIRE")
        ) { err in
            XCTAssertEqual(err as? FireGateError, .wrongConfirmWord)
        }
        XCTAssertNil(gate.sealedPacket)
        XCTAssertFalse(gate.invokeExecutorStub())
    }

    func testAbortAfterDryRunNoPacketNoExecutor() throws {
        var stack = try makeReadyStack()
        let gate = FireGate(confirmWord: "IGNITE")
        _ = try gate.presentDryRun(stack: stack, blastTier: .mutate)
        gate.abort(stack: &stack)
        XCTAssertEqual(stack.status, .aborted)
        XCTAssertNil(gate.sealedPacket)
        XCTAssertNil(stack.firePacketId)
        XCTAssertFalse(gate.invokeExecutorStub())
        XCTAssertEqual(gate.executorInvocations, 0)
    }

    func testG3SealWritesImmutablePacketFields() throws {
        var stack = try makeReadyStack()
        let gate = FireGate(confirmWord: "IGNITE")
        _ = try gate.presentDryRun(stack: stack, blastTier: .draftOnly)
        let packet = try gate.seal(stack: &stack, blastTier: .draftOnly, confirmWord: "IGNITE")
        XCTAssertEqual(packet.constraints, ["StrongYes week"])
        XCTAssertEqual(packet.blastTier, .draftOnly)
        XCTAssertEqual(packet.confirmWordHash, FireGate.hash("IGNITE"))
        XCTAssertEqual(stack.firePacketId, packet.packetId)
    }
}
