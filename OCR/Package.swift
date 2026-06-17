// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "PosterOCR",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "poster-ocr", targets: ["PosterOCR"])
    ],
    targets: [
        .executableTarget(
            name: "PosterOCR",
            path: "Sources/PosterOCR"
        )
    ]
)
