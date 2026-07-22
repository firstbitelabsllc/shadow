import Foundation

public enum SessionStoreError: Error, Equatable {
    case immutableSession
    case optionNotFound
    case emptyOptions
    case tooManyOptions
    case alreadyFired
}

/// In-memory session + optional disk resume for the Kitchen spike.
public final class SessionStore: @unchecked Sendable {
    public private(set) var stack: ChoicePathStack
    private let fileURL: URL?

    public init(stack: ChoicePathStack, fileURL: URL? = nil) {
        self.stack = stack
        self.fileURL = fileURL
    }

    public static func create(roughIntent: String, fileURL: URL? = nil) -> SessionStore {
        SessionStore(stack: ChoicePathStack(roughIntent: roughIntent), fileURL: fileURL)
    }

    public static func load(from url: URL) throws -> SessionStore {
        let data = try Data(contentsOf: url)
        let stack = try JSONDecoder().decode(ChoicePathStack.self, from: data)
        return SessionStore(stack: stack, fileURL: url)
    }

    public func appendNode(_ node: BeliefNode) throws {
        guard stack.isMutable else { throw SessionStoreError.immutableSession }
        guard (2...3).contains(node.options.count) || node.mode == .freeform else {
            throw SessionStoreError.tooManyOptions
        }
        if node.options.isEmpty { throw SessionStoreError.emptyOptions }
        stack.nodes.append(node)
    }

    /// Pick an option and attach rider to the *chosen* option (not a 4th peer).
    @discardableResult
    public func choose(optionId: String, riderText: String? = nil) throws -> BeliefOption {
        guard stack.isMutable else { throw SessionStoreError.immutableSession }
        guard !stack.nodes.isEmpty else { throw SessionStoreError.optionNotFound }
        var node = stack.nodes[stack.nodes.count - 1]
        guard let idx = node.options.firstIndex(where: { $0.id == optionId }) else {
            throw SessionStoreError.optionNotFound
        }
        var chosen = node.options[idx]
        chosen.status = .chosen
        if let rider = riderText?.trimmingCharacters(in: .whitespacesAndNewlines), !rider.isEmpty {
            chosen.riderText = rider
            stack.constraints.append(rider)
        }
        for i in node.options.indices where i != idx {
            if node.options[i].status == .offered {
                node.options[i].status = .discarded
            }
        }
        node.options[idx] = chosen
        node.selected = chosen
        node.discarded = node.options.filter { $0.status == .discarded }
        stack.nodes[stack.nodes.count - 1] = node
        stack.status = .ready
        return chosen
    }

    public func discardLastNode() throws {
        guard stack.isMutable else { throw SessionStoreError.immutableSession }
        guard !stack.nodes.isEmpty else { return }
        _ = stack.nodes.popLast()
        stack.status = stack.nodes.isEmpty ? .clarifying : .ready
    }

    public func markFired(packetId: String) throws {
        guard stack.status != .fired else { throw SessionStoreError.alreadyFired }
        stack.status = .fired
        stack.firePacketId = packetId
    }

    public func markAborted() {
        stack.status = .aborted
        stack.firePacketId = nil
    }

    public func save() throws {
        guard let fileURL else { return }
        let data = try JSONEncoder().encode(stack)
        try data.write(to: fileURL, options: .atomic)
    }
}

public enum Distinctness {
    /// Token Jaccard distance; higher = more distinct. Golden rule: labels must not be near-synonyms.
    public static func jaccardDistance(_ a: String, _ b: String) -> Double {
        let ta = tokens(a)
        let tb = tokens(b)
        if ta.isEmpty && tb.isEmpty { return 0 }
        let inter = ta.intersection(tb).count
        let union = ta.union(tb).count
        guard union > 0 else { return 0 }
        return 1.0 - (Double(inter) / Double(union))
    }

    public static func allPairsDistinct(labels: [String], minDistance: Double = 0.5) -> Bool {
        guard labels.count >= 2 else { return true }
        for i in 0..<labels.count {
            for j in (i + 1)..<labels.count {
                if jaccardDistance(labels[i], labels[j]) < minDistance { return false }
            }
        }
        return true
    }

    private static func tokens(_ s: String) -> Set<String> {
        Set(
            s.lowercased()
                .split { !$0.isLetter && !$0.isNumber }
                .map(String.init)
                .filter { $0.count > 1 }
        )
    }
}
