import SwiftUI
#if canImport(Darwin)
import Darwin   // exit()
#endif

/// The lab build of the bench app (ios/BenchmarkApp/project-ddp.yml): the app's headless path with
/// the LiteRT-LM runtime only, for Developer Device Platform, which runs iOS as XCTest. Under the
/// XCTest (Tests/DDP) the screen waits and the test drives DDPHarness; launched with
/// `--yardstick-autorun …` (devicectl, as the attached iPhone's driver launches the app) it runs that
/// spec through the same harness, then exits with its code, as the app does.
@main
struct DDPApp: App {
    private let autoRun = HeadlessAutoRun.specFromLaunchArgs()

    var body: some Scene {
        WindowGroup {
            DDPRunView(spec: autoRun)
        }
    }
}

/// One screen of YARDSTICK_* lines.
struct DDPRunView: View {
    let spec: HeadlessAutoRun.Spec?
    @State private var lines: [String] = []
    @State private var started = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                    Text(line).font(.system(.footnote, design: .monospaced))
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
        }
        .task {
            guard !started else { return }
            started = true
            guard let spec else {
                lines.append("BenchmarkAppDDP: waiting for the XCTest (Tests/DDP) or a --yardstick-autorun launch")
                DDPHarness.screen = { lines.append($0) }
                return
            }
            let outcome = await DDPHarness.run(spec: spec, show: { lines.append($0) })
            // As HeadlessRunnerView.finish: give stdout and the record writes a moment, then exit.
            try? await Task.sleep(nanoseconds: 600_000_000)
            exit(outcome.code ?? 2)
        }
    }
}
