import Foundation
import Vision
import AppKit
// usage: ocr <png>...  prints "file\tline" for every recognized line
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("\(path)\tLOAD_FAIL"); continue }
    let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    for o in (req.results ?? []) { if let c = o.topCandidates(1).first { let b=o.boundingBox; print("\(path)\t\(String(format:"%.3f,%.3f",b.minX,1-b.maxY))\t\(c.string)") } }
}
