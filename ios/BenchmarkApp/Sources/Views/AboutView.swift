import SwiftUI

struct AboutView: View {
    private let device = DeviceSnapshot.capture()

    var body: some View {
        Form {
            Section("This app") {
                Text("iOS On-device LLM Benchmark — measures decode/prefill throughput, memory, and thermal behavior of local LLM runtimes on iPhone.")
                    .font(.callout)
            }

            Section("Device") {
                row("Model", device.modelIdentifier)
                row("OS", "\(device.systemName) \(device.systemVersion)")
                row("CPUs", "\(device.processorCount)")
                row("RAM", "\(device.physicalMemoryMB) MB")
                row("Build", device.buildConfiguration)
                row("Battery", "\(device.batteryState) (\(Int(device.batteryLevel * 100))%)")
                row("Low power mode", device.isLowPowerModeEnabled ? "on" : "off")
                row("Thermal state", device.initialThermalState)
            }

            Section("Pre-flight") {
                if device.isLowPowerModeEnabled {
                    Label("Low Power Mode is on. Throughput will be reduced — disable for comparable numbers.", systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                }
                if device.initialThermalState != "nominal" {
                    Label("Thermal state is \(device.initialThermalState). Let the device cool before running for comparable numbers.", systemImage: "thermometer.high")
                        .foregroundStyle(.orange)
                }
                if device.batteryState == "charging" {
                    Label("Charging — fast chargers heat the device and skew thermals.", systemImage: "bolt")
                        .foregroundStyle(.orange)
                }
                if !device.isLowPowerModeEnabled && device.initialThermalState == "nominal" && device.batteryState != "charging" {
                    Label("Ready to run.", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                }
            }

            Section("Project") {
                Link("README", destination: URL(string: "https://github.com/")!)
                    .disabled(true)
                Text("See the repo's README, DESIGN, and methodology/ docs for the full benchmark contract.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("About")
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundStyle(.secondary)
            Spacer()
            Text(value).font(.system(.body, design: .monospaced))
        }
    }
}
