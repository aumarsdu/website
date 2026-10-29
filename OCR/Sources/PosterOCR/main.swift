import CoreGraphics
import Foundation
import ImageIO
import Vision

struct Options {
    var input: String?
    var out: String = "data/output/apple_vision"
    var languages: [String] = ["zh-Hans", "en-US"]
    var level: VNRequestTextRecognitionLevel = .accurate
    var recursive: Bool = false
    var minConfidence: Float = 0.0
    var plainTextDir: String = "data/output/plain_text"
    var help: Bool = false
}

struct Candidate: Codable {
    let text: String
    let confidence: Float
}

struct BoundingBox: Codable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct OCRBlock: Codable {
    let text: String
    let confidence: Float
    let boundingBox: BoundingBox
    let candidates: [Candidate]
}

struct OCRRecord: Codable {
    let file: String
    let engine: String
    let languages: [String]
    let plainText: String
    let blocks: [OCRBlock]
    let confidenceAvg: Float
    let needsReview: Bool

    enum CodingKeys: String, CodingKey {
        case file
        case engine
        case languages
        case plainText = "plain_text"
        case blocks
        case confidenceAvg = "confidence_avg"
        case needsReview = "needs_review"
    }
}

enum CLIError: Error, CustomStringConvertible {
    case missingValue(String)
    case unknownArgument(String)
    case invalidLevel(String)
    case invalidConfidence(String)
    case missingInput

    var description: String {
        switch self {
        case .missingValue(let arg):
            return "\(arg) requires a value"
        case .unknownArgument(let arg):
            return "Unknown argument: \(arg)"
        case .invalidLevel(let value):
            return "Invalid --level: \(value). Use accurate or fast."
        case .invalidConfidence(let value):
            return "Invalid --min-confidence: \(value)"
        case .missingInput:
            return "--input is required"
        }
    }
}

let supportedExtensions: Set<String> = ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "heic", "webp"]

func printHelp() {
    print("""
    poster-ocr - macOS local poster OCR powered by Apple Vision

    Usage:
      poster-ocr --input <path> [options]

    Options:
      --input <path>              Required. Image file or directory.
      --out <dir>                 Default: data/output/apple_vision
      --langs <list>              Default: zh-Hans,en-US
      --level <accurate|fast>     Default: accurate
      --recursive                 Recursively scan input directory
      --min-confidence <float>    Default: 0.0
      --plain-text-dir <dir>      Default: data/output/plain_text
      --help                      Show this help
    """)
}

func parseArguments(_ args: [String]) throws -> Options {
    var options = Options()
    var index = 1

    func requireValue(_ name: String) throws -> String {
        guard index + 1 < args.count else {
            throw CLIError.missingValue(name)
        }
        index += 1
        return args[index]
    }

    while index < args.count {
        let arg = args[index]
        switch arg {
        case "--help", "-h":
            options.help = true
        case "--input":
            options.input = try requireValue(arg)
        case "--out":
            options.out = try requireValue(arg)
        case "--langs":
            let value = try requireValue(arg)
            options.languages = value.split(separator: ",").map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        case "--level":
            let value = try requireValue(arg)
            if value == "accurate" {
                options.level = .accurate
            } else if value == "fast" {
                options.level = .fast
            } else {
                throw CLIError.invalidLevel(value)
            }
        case "--recursive":
            options.recursive = true
        case "--min-confidence":
            let value = try requireValue(arg)
            guard let confidence = Float(value) else {
                throw CLIError.invalidConfidence(value)
            }
            options.minConfidence = confidence
        case "--plain-text-dir":
            options.plainTextDir = try requireValue(arg)
        default:
            throw CLIError.unknownArgument(arg)
        }
        index += 1
    }

    if !options.help && options.input == nil {
        throw CLIError.missingInput
    }

    return options
}

func stderr(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func isImageFile(_ url: URL) -> Bool {
    supportedExtensions.contains(url.pathExtension.lowercased())
}

func collectImageFiles(input: URL, recursive: Bool) throws -> [URL] {
    let fm = FileManager.default
    var isDirectory: ObjCBool = false
    guard fm.fileExists(atPath: input.path, isDirectory: &isDirectory) else {
        throw NSError(domain: "PosterOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Input path does not exist: \(input.path)"])
    }

    if !isDirectory.boolValue {
        return isImageFile(input) ? [input] : []
    }

    if recursive {
        guard let enumerator = fm.enumerator(at: input, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles]) else {
            return []
        }
        return enumerator.compactMap { item in
            guard let url = item as? URL else { return nil }
            return isImageFile(url) ? url : nil
        }.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
    }

    return try fm.contentsOfDirectory(at: input, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles])
        .filter(isImageFile)
        .sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
}

func ensureDirectory(_ path: String) throws {
    try FileManager.default.createDirectory(atPath: path, withIntermediateDirectories: true)
}

func csvEscape(_ value: String) -> String {
    let escaped = value.replacingOccurrences(of: "\"", with: "\"\"")
    if escaped.contains(",") || escaped.contains("\"") || escaped.contains("\n") || escaped.contains("\r") {
        return "\"\(escaped)\""
    }
    return escaped
}

func appendLine(_ line: String, to url: URL) throws {
    let data = Data((line + "\n").utf8)
    if FileManager.default.fileExists(atPath: url.path) {
        let handle = try FileHandle(forWritingTo: url)
        try handle.seekToEnd()
        try handle.write(contentsOf: data)
        try handle.close()
    } else {
        try data.write(to: url)
    }
}

func safeFileStem(for url: URL) -> String {
    let stem = url.deletingPathExtension().lastPathComponent
    let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ .").union(.letters).union(.decimalDigits)
    let scalars = stem.unicodeScalars.map { allowed.contains($0) ? Character($0) : "_" }
    let safe = String(scalars).trimmingCharacters(in: .whitespacesAndNewlines)
    return safe.isEmpty ? "image" : safe
}

func loadCGImage(_ url: URL) -> CGImage? {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else {
        return nil
    }
    return CGImageSourceCreateImageAtIndex(source, 0, nil)
}

func recognize(url: URL, options: Options) throws -> OCRRecord {
    guard let image = loadCGImage(url) else {
        throw NSError(domain: "PosterOCR", code: 2, userInfo: [NSLocalizedDescriptionKey: "ImageIO could not load image. If this is WebP, current macOS ImageIO may not support it."])
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = options.level
    request.recognitionLanguages = options.languages
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    let blocks = observations.compactMap { observation -> OCRBlock? in
        let candidates = observation.topCandidates(3).map {
            Candidate(text: $0.string, confidence: $0.confidence)
        }
        guard let best = candidates.first else {
            return nil
        }
        guard best.confidence >= options.minConfidence else {
            return nil
        }
        let rect = observation.boundingBox
        return OCRBlock(
            text: best.text,
            confidence: best.confidence,
            boundingBox: BoundingBox(
                x: rect.origin.x,
                y: rect.origin.y,
                width: rect.width,
                height: rect.height
            ),
            candidates: candidates
        )
    }.sorted { left, right in
        let leftTop = 1.0 - left.boundingBox.y - left.boundingBox.height
        let rightTop = 1.0 - right.boundingBox.y - right.boundingBox.height
        if abs(leftTop - rightTop) > 0.025 {
            return leftTop < rightTop
        }
        return left.boundingBox.x < right.boundingBox.x
    }

    let plainText = blocks.map(\.text).joined(separator: "\n")
    let confidenceAvg = blocks.isEmpty ? 0.0 : blocks.map(\.confidence).reduce(0, +) / Float(blocks.count)
    let needsReview = confidenceAvg < 0.70 || blocks.isEmpty

    return OCRRecord(
        file: url.path,
        engine: "apple_vision",
        languages: options.languages,
        plainText: plainText,
        blocks: blocks,
        confidenceAvg: confidenceAvg,
        needsReview: needsReview
    )
}

func writePlainText(record: OCRRecord, imageURL: URL, dir: String) throws {
    let stem = safeFileStem(for: imageURL)
    let url = URL(fileURLWithPath: dir).appendingPathComponent("\(stem).md")
    let confidence = String(format: "%.3f", record.confidenceAvg)
    let blockLines = record.blocks.map { block in
        "- [\(String(format: "%.2f", block.confidence))] \(block.text)"
    }.joined(separator: "\n")
    let content = """
    # \(imageURL.lastPathComponent)

    engine: apple_vision
    confidence_avg: \(confidence)
    needs_review: \(record.needsReview ? "true" : "false")

    ## OCR Text

    \(record.plainText)

    ## Blocks

    \(blockLines)
    """
    try Data((content + "\n").utf8).write(to: url)
}

func run() throws {
    let options = try parseArguments(CommandLine.arguments)
    if options.help {
        printHelp()
        return
    }

    guard let input = options.input else {
        throw CLIError.missingInput
    }

    try ensureDirectory(options.out)
    try ensureDirectory(options.plainTextDir)

    let outURL = URL(fileURLWithPath: options.out)
    let jsonlURL = outURL.appendingPathComponent("results.jsonl")
    let csvURL = outURL.appendingPathComponent("results.csv")
    try? FileManager.default.removeItem(at: jsonlURL)
    try? FileManager.default.removeItem(at: csvURL)

    let csvHeader = ["file", "engine", "languages", "plain_text", "confidence_avg", "needs_review", "block_count"].joined(separator: ",")
    try appendLine(csvHeader, to: csvURL)

    let imageFiles = try collectImageFiles(input: URL(fileURLWithPath: input), recursive: options.recursive)
    if imageFiles.isEmpty {
        stderr("[WARN] No supported image files found in \(input)")
        return
    }

    let encoder = JSONEncoder()
    encoder.outputFormatting = [.withoutEscapingSlashes]

    for (index, imageURL) in imageFiles.enumerated() {
        print("[\(index + 1)/\(imageFiles.count)] Processing \(imageURL.lastPathComponent)")
        do {
            let record = try recognize(url: imageURL, options: options)
            let jsonData = try encoder.encode(record)
            guard let jsonLine = String(data: jsonData, encoding: .utf8) else {
                throw NSError(domain: "PosterOCR", code: 3, userInfo: [NSLocalizedDescriptionKey: "Could not encode JSON"])
            }
            try appendLine(jsonLine, to: jsonlURL)

            let csvLine = [
                record.file,
                record.engine,
                record.languages.joined(separator: "|"),
                record.plainText,
                String(format: "%.4f", record.confidenceAvg),
                record.needsReview ? "true" : "false",
                String(record.blocks.count)
            ].map(csvEscape).joined(separator: ",")
            try appendLine(csvLine, to: csvURL)
            try writePlainText(record: record, imageURL: imageURL, dir: options.plainTextDir)

            if record.blocks.isEmpty {
                print("[WARN] \(imageURL.lastPathComponent) no text found")
            } else {
                print("[OK] \(imageURL.lastPathComponent) blocks=\(record.blocks.count) confidence_avg=\(String(format: "%.2f", record.confidenceAvg))")
            }
        } catch {
            stderr("[ERROR] \(imageURL.lastPathComponent) \(error.localizedDescription)")
        }
    }
}

do {
    try run()
} catch {
    stderr("[ERROR] \(error)")
    printHelp()
    exit(1)
}
