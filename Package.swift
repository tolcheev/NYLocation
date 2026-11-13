// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "NYLocation",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "NYLocation"),
    ]
)
