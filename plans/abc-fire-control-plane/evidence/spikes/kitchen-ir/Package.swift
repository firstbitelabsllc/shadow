// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "KitchenIRSpike",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "ABCFireIR", targets: ["ABCFireIR"]),
        .library(name: "ABCFireGate", targets: ["ABCFireGate"]),
    ],
    targets: [
        .target(name: "ABCFireIR"),
        .target(name: "ABCFireGate", dependencies: ["ABCFireIR"]),
        .testTarget(name: "ABCFireIRTests", dependencies: ["ABCFireIR"]),
        .testTarget(name: "ABCFireGateTests", dependencies: ["ABCFireGate", "ABCFireIR"]),
    ]
)
