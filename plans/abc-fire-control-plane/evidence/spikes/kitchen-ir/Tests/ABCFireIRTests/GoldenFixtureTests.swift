import XCTest
@testable import ABCFireIR

/// Offline fixtures lifted from `evidence/golden-dialogues-t2b.md` into package
/// `Fixtures/` (T-4 next-step #2). No model spend.
final class GoldenFixtureTests: XCTestCase {
    private struct FixtureOption: Decodable {
        let id: String
        let label: String
        let rationale: String
    }

    private struct FixturePick: Decodable {
        let optionId: String
        let riderText: String?
    }

    private struct GoldenFixture: Decodable {
        let id: String
        let roughIntent: String
        let mode: ClarifyMode
        let restate: String
        let options: [FixtureOption]
        let pick: FixturePick?
        let expectDistinct: Bool
        let minJaccardDistance: Double
    }

    func testNicoleMenuFixtureDistinctAndChoose() throws {
        let fx = try loadFixture("d-nicole-menu")
        XCTAssertEqual(fx.id, "D-Nicole")
        let labels = fx.options.map { "\($0.label) \($0.rationale)" }
        XCTAssertTrue(
            Distinctness.allPairsDistinct(labels: labels, minDistance: fx.minJaccardDistance),
            "Nicole menu golden must be mutually distinct"
        )

        let store = SessionStore.create(roughIntent: fx.roughIntent)
        let opts = fx.options.map {
            BeliefOption(id: $0.id, label: $0.label, rationale: $0.rationale)
        }
        try store.appendNode(BeliefNode(prompt: fx.restate, mode: fx.mode, options: opts))
        let pick = try XCTUnwrap(fx.pick)
        let chosen = try store.choose(optionId: pick.optionId, riderText: pick.riderText)
        XCTAssertEqual(chosen.id, "A")
        XCTAssertEqual(chosen.riderText, "keep the tone friendly not salesy")
        XCTAssertEqual(store.stack.constraints, ["keep the tone friendly not salesy"])
        XCTAssertEqual(store.stack.status, .ready)
    }

    func testCarLeoFixtureDistinctAndChoose() throws {
        let fx = try loadFixture("d-carleo-freeform")
        XCTAssertEqual(fx.id, "D-CarLeo")
        let labels = fx.options.map { "\($0.label) \($0.rationale)" }
        XCTAssertTrue(
            Distinctness.allPairsDistinct(labels: labels, minDistance: fx.minJaccardDistance),
            "Car-Leo golden must be mutually distinct"
        )

        let store = SessionStore.create(roughIntent: fx.roughIntent)
        let opts = fx.options.map {
            BeliefOption(id: $0.id, label: $0.label, rationale: $0.rationale)
        }
        try store.appendNode(BeliefNode(prompt: fx.restate, mode: fx.mode, options: opts))
        let pick = try XCTUnwrap(fx.pick)
        let chosen = try store.choose(optionId: pick.optionId, riderText: pick.riderText)
        XCTAssertEqual(chosen.id, "B")
        XCTAssertNil(chosen.riderText)
        XCTAssertTrue(store.stack.constraints.isEmpty)
        XCTAssertEqual(store.stack.status, .ready)
    }

    func testSynonymFailNegativeControl() throws {
        let fx = try loadFixture("synonym-fail")
        XCTAssertFalse(fx.expectDistinct)
        let labels = fx.options.map { "\($0.label) \($0.rationale)" }
        XCTAssertFalse(
            Distinctness.allPairsDistinct(labels: labels, minDistance: fx.minJaccardDistance),
            "Synonym spam fixture must fail distinctness"
        )
    }

    // MARK: - load

    private func loadFixture(_ name: String) throws -> GoldenFixture {
        let url = fixturesDir().appendingPathComponent("\(name).json")
        let data = try Data(contentsOf: url)
        return try JSONDecoder().decode(GoldenFixture.self, from: data)
    }

    private func fixturesDir() -> URL {
        // Tests/ABCFireIRTests/<file> → package root Fixtures/
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Fixtures")
    }
}
