import Foundation
import Vision
import AppKit
// usage: ocr <png>...
// prints, per recognised observation:
//   L <tab> x0,top,x1,bottom <tab> line text
//   W <tab> x0,top,x1,bottom <tab> word        (one per whitespace-separated word of that line)
// Coordinates are normalised to the image: origin top-left, x right, y down, range 0..1.
// Word boxes come from VNRecognizedText.boundingBox(for:); if Vision gives none, the line box is used.
func fmt(_ r: CGRect) -> String {
    return String(format: "%.4f,%.4f,%.4f,%.4f", r.minX, 1 - r.maxY, r.maxX, 1 - r.minY)
}
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("LOAD_FAIL\t\(path)"); continue }
    let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(1).first else { continue }
        let s = c.string
        print("L\t\(fmt(o.boundingBox))\t\(s)")
        var idx = s.startIndex
        while idx < s.endIndex {
            while idx < s.endIndex && s[idx].isWhitespace { idx = s.index(after: idx) }
            if idx >= s.endIndex { break }
            var end = idx
            while end < s.endIndex && !s[end].isWhitespace { end = s.index(after: end) }
            let word = String(s[idx..<end])
            var box = o.boundingBox
            if let b = try? c.boundingBox(for: idx..<end) { box = b.boundingBox }
            print("W\t\(fmt(box))\t\(word)")
            idx = end
        }
    }
}
