// swift-tools-version: 5.9
// Bare conversation create/delete loop for LiteRT-LM #3446 (round r2, step 6).
import PackageDescription

let package = Package(
  name: "bareloop",
  platforms: [.macOS(.v14)],
  dependencies: [
    .package(path: "/Users/USER/code/edge-llm-bench-wt-retest0171/ios/BenchmarkApp/Vendored/LiteRT-LM")
  ],
  targets: [
    .executableTarget(
      name: "bareloop",
      dependencies: [.product(name: "LiteRTLM", package: "LiteRT-LM")]
    )
  ]
)
