// On-device OCR via Apple's Vision framework (macOS). Prints one recognized line per output line,
// per image arg. Used by receipts/classify.py to keyword-gate dining vs retail/invoice without
// any cloud call. Compile: swiftc vision_ocr.swift -o /tmp/receipts_vision_ocr
import AppKit
import Foundation
import Vision

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for line in (req.results ?? []).compactMap({ $0.topCandidates(1).first?.string }) {
        print(line)
    }
}
