import Foundation

public enum ClarifyMode: String, Codable, Sendable {
    case menu, freeform, hybrid
}

public enum ChoiceStatus: String, Codable, Sendable {
    case offered, chosen, discarded, rider
}

public enum SessionStatus: String, Codable, Sendable {
    case clarifying, ready, fired, aborted
}

public enum BlastTier: String, Codable, Sendable {
    case readOnly = "read-only"
    case draftOnly = "draft-only"
    case mutate
    case externalSend = "external-send"
    case money
}

public struct BeliefOption: Codable, Equatable, Sendable, Identifiable {
    public var id: String
    public var label: String
    public var rationale: String
    public var status: ChoiceStatus
    public var riderText: String?

    public init(
        id: String,
        label: String,
        rationale: String,
        status: ChoiceStatus = .offered,
        riderText: String? = nil
    ) {
        self.id = id
        self.label = label
        self.rationale = rationale
        self.status = status
        self.riderText = riderText
    }
}

public struct BeliefNode: Codable, Equatable, Sendable, Identifiable {
    public var id: String { turnId }
    public var turnId: String
    public var prompt: String
    public var mode: ClarifyMode
    public var latencyBudgetMs: Int
    public var latencyActualMs: Int?
    public var options: [BeliefOption]
    public var selected: BeliefOption?
    public var considered: [BeliefOption]
    public var discarded: [BeliefOption]

    public init(
        turnId: String = UUID().uuidString,
        prompt: String,
        mode: ClarifyMode,
        latencyBudgetMs: Int = 2500,
        latencyActualMs: Int? = nil,
        options: [BeliefOption],
        selected: BeliefOption? = nil,
        considered: [BeliefOption] = [],
        discarded: [BeliefOption] = []
    ) {
        self.turnId = turnId
        self.prompt = prompt
        self.mode = mode
        self.latencyBudgetMs = latencyBudgetMs
        self.latencyActualMs = latencyActualMs
        self.options = options
        self.selected = selected
        self.considered = considered.isEmpty ? options : considered
        self.discarded = discarded
    }
}

public struct ChoicePathStack: Codable, Equatable, Sendable {
    public var sessionId: String
    public var roughIntent: String
    public var status: SessionStatus
    public var nodes: [BeliefNode]
    public var constraints: [String]
    public var firePacketId: String?

    public init(
        sessionId: String = UUID().uuidString,
        roughIntent: String,
        status: SessionStatus = .clarifying,
        nodes: [BeliefNode] = [],
        constraints: [String] = [],
        firePacketId: String? = nil
    ) {
        self.sessionId = sessionId
        self.roughIntent = roughIntent
        self.status = status
        self.nodes = nodes
        self.constraints = constraints
        self.firePacketId = firePacketId
    }

    public var isMutable: Bool {
        status == .clarifying || status == .ready
    }
}

public struct FirePacket: Codable, Equatable, Sendable {
    public var packetId: String
    public var sessionId: String
    public var roughIntent: String
    public var nodes: [BeliefNode]
    public var constraints: [String]
    public var blastTier: BlastTier
    public var confirmWordHash: String
    public var sealedAt: Date

    public init(
        packetId: String = UUID().uuidString,
        sessionId: String,
        roughIntent: String,
        nodes: [BeliefNode],
        constraints: [String],
        blastTier: BlastTier,
        confirmWordHash: String,
        sealedAt: Date = Date()
    ) {
        self.packetId = packetId
        self.sessionId = sessionId
        self.roughIntent = roughIntent
        self.nodes = nodes
        self.constraints = constraints
        self.blastTier = blastTier
        self.confirmWordHash = confirmWordHash
        self.sealedAt = sealedAt
    }
}
