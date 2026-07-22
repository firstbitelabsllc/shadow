import Foundation
import CryptoKit
import ABCFireIR

public enum FireGateError: Error, Equatable {
    case wrongConfirmWord
    case dryRunRequired
    case sessionNotReady
    case alreadySealed
    case aborted
}

public struct DryRunView: Equatable, Sendable {
    public var blastTier: BlastTier
    public var packetPreviewJSON: String
    public var requiresConfirmWord: Bool
}

/// Pure fire-gate: dry-run before seal, confirm word, abort window.
public final class FireGate: @unchecked Sendable {
    public private(set) var confirmWord: String
    public private(set) var dryRunPresented: Bool = false
    public private(set) var sealedPacket: FirePacket?
    public private(set) var executorInvocations: Int = 0
    public private(set) var aborted: Bool = false

    public init(confirmWord: String = "IGNITE") {
        self.confirmWord = confirmWord
    }

    public var confirmWordHash: String {
        Self.hash(confirmWord)
    }

    public static func hash(_ word: String) -> String {
        let digest = SHA256.hash(data: Data(word.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    public func presentDryRun(stack: ChoicePathStack, blastTier: BlastTier) throws -> DryRunView {
        guard !aborted else { throw FireGateError.aborted }
        guard sealedPacket == nil else { throw FireGateError.alreadySealed }
        guard stack.status == .ready || stack.status == .clarifying else {
            throw FireGateError.sessionNotReady
        }
        let preview = FirePacket(
            sessionId: stack.sessionId,
            roughIntent: stack.roughIntent,
            nodes: stack.nodes,
            constraints: stack.constraints,
            blastTier: blastTier,
            confirmWordHash: confirmWordHash
        )
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        enc.dateEncodingStrategy = .iso8601
        let data = try enc.encode(preview)
        let json = String(data: data, encoding: .utf8) ?? "{}"
        dryRunPresented = true
        let requiresWord = blastTier == .mutate || blastTier == .externalSend || blastTier == .money
        return DryRunView(
            blastTier: blastTier,
            packetPreviewJSON: json,
            requiresConfirmWord: requiresWord || true
        )
    }

    public func seal(
        stack: inout ChoicePathStack,
        blastTier: BlastTier,
        confirmWord attempt: String,
        forceSkipDryRun: Bool = false
    ) throws -> FirePacket {
        guard !aborted else { throw FireGateError.aborted }
        guard sealedPacket == nil else { throw FireGateError.alreadySealed }
        if blastTier != .readOnly && !dryRunPresented && !forceSkipDryRun {
            throw FireGateError.dryRunRequired
        }
        guard attempt == confirmWord else { throw FireGateError.wrongConfirmWord }
        let packet = FirePacket(
            sessionId: stack.sessionId,
            roughIntent: stack.roughIntent,
            nodes: stack.nodes,
            constraints: stack.constraints,
            blastTier: blastTier,
            confirmWordHash: confirmWordHash
        )
        sealedPacket = packet
        stack.status = .fired
        stack.firePacketId = packet.packetId
        return packet
    }

    /// Abort after dry-run, before executor starts — no packet, no executor.
    public func abort(stack: inout ChoicePathStack) {
        aborted = true
        sealedPacket = nil
        stack.status = .aborted
        stack.firePacketId = nil
    }

    /// Executor may only run after seal; counts invocations for G4 proof.
    public func invokeExecutorStub() -> Bool {
        guard sealedPacket != nil, !aborted else { return false }
        executorInvocations += 1
        return true
    }
}
