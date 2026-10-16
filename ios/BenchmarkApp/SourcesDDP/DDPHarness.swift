import Foundation
#if canImport(UIKit)
import UIKit
#endif
#if canImport(Darwin)
import Darwin   // pipe(), dup2(), fflush(), stdout
#endif

/// What one lab run did, for the XCTest's verdict (Tests/DDP/DDPBenchmarkTests.swift).
public struct DDPOutcome: Sendable {
    /// The headless run's exit code (the app's codes, plus `DDPHarness.modelMissingCode`);
    /// nil when the run did not start.
    public let code: Int32?
    /// Why the run did not start (no arguments file, a malformed one); nil when it ran.
    public let failure: String?
    /// `--runs` of the arguments: the records the run should have added.
    public let runs: Int
    /// The files this run added to Documents/results/ (also listed in Documents/out/records.txt).
    public let newFiles: [String]
}

/// The lab build's entry (ios/BenchmarkApp/project-ddp.yml). Developer Device Platform runs iOS as
/// XCTest: before the test the lab pushes the model into the app's model directory and
/// Documents/yardstick_args.json, a JSON array of the words the attached iPhone's driver
/// (scripts/bench_matrix_iphone.sh) gives the app after `--`; after it, the lab pulls
/// Documents/results/ and Documents/out/. One call runs the app's own headless path
/// (`HeadlessAutoRun.specFromLaunchArgs` -> `HeadlessRun.runAll`) once, in this process, and writes
/// Documents/out/console.txt (this process's stdout and stderr while it ran), thermal_gate.txt (the
/// wait before run 1), records.txt (the files the run added to Documents/results/) and
/// yardstick.done (the exit code).
public enum DDPHarness {
    /// Documents/<argsFile>: the run's arguments.
    public static let argsFile = "yardstick_args.json"
    /// The exit code when the model file is not where the app reads it: the lab never downloads.
    public static let modelMissingCode: Int32 = 8
    /// The idle screen's line sink (DDPApp), so a run the XCTest drives shows its lines too.
    @MainActor static var screen: ((String) -> Void)?
    /// The runtimes of finished runs, kept the way AppSession keeps the app's until `exit`: no
    /// engine is torn down inside the test.
    @MainActor private static var kept: [any LLMRuntime] = []

    static var documents: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    /// The XCTest's call: the run of Documents/yardstick_args.json.
    @MainActor
    public static func runFromDocuments() async -> DDPOutcome {
        let argsURL = documents.appendingPathComponent(argsFile)
        guard let data = FileManager.default.contents(atPath: argsURL.path) else {
            let home = URL(fileURLWithPath: NSHomeDirectory())
            return DDPOutcome(code: nil, failure: "no \(argsURL.path); Documents holds [\(listing(documents))], "
                              + "the container \(home.path) holds [\(listing(home))]", runs: 0, newFiles: [])
        }
        guard let args = (try? JSONSerialization.jsonObject(with: data)) as? [String], !args.isEmpty else {
            return DDPOutcome(code: nil, failure: "\(argsURL.path) is not a non-empty JSON array of strings",
                              runs: 0, newFiles: [])
        }
        guard args.contains("--yardstick-autorun") else {
            return DDPOutcome(code: nil, failure: "\(argsURL.path) has no --yardstick-autorun: \(args)",
                              runs: 0, newFiles: [])
        }
        let out = freshOutDirectory()
        // specFromLaunchArgs prints the YARDSTICK_METAL_DEVICE / _NOTE lines: the console starts first.
        let tee = ConsoleTee(path: out.appendingPathComponent("console.txt").path)
        guard let spec = HeadlessAutoRun.specFromLaunchArgs(["BenchmarkAppDDP"] + args) else {
            tee.stop()
            return DDPOutcome(code: nil, failure: "HeadlessAutoRun.specFromLaunchArgs read no spec from \(args)",
                              runs: 0, newFiles: [])
        }
        return await run(spec: spec, out: out, tee: tee, show: nil)
    }

    /// The app's own launch with `--yardstick-autorun …` (DDPApp): the same run and the same files.
    @MainActor
    static func run(spec: HeadlessAutoRun.Spec, show: @escaping @MainActor (String) -> Void) async -> DDPOutcome {
        let out = freshOutDirectory()
        let tee = ConsoleTee(path: out.appendingPathComponent("console.txt").path)
        return await run(spec: spec, out: out, tee: tee, show: show)
    }

    @MainActor
    private static func run(spec: HeadlessAutoRun.Spec, out: URL, tee: ConsoleTee,
                            show: (@MainActor (String) -> Void)?) async -> DDPOutcome {
        #if canImport(UIKit)
        UIApplication.shared.isIdleTimerDisabled = true   // as HeadlessRunnerView: no lock mid-run
        #endif
        let log: @MainActor (String) -> Void = { line in
            print(line)
            fflush(stdout)
            show?(line)
            screen?(line)
        }
        let code: Int32
        var added: [String] = []
        if spec.runtime != .mediaPipe {
            // The lab build links LiteRT-LM only; the app's line for a runtime it cannot run.
            log("YARDSTICK_FATAL runtime=\(spec.runtime.rawValue) not_available")
            code = 2
        } else if let missing = missingModelFile(modelId: spec.modelId) {
            log("YARDSTICK_FATAL model_file_missing path=\(missing) (pushed by the lab; nothing is downloaded)")
            code = modelMissingCode
        } else {
            let runtime = MediaPipeRuntime(backend: MediaPipeRuntime.launchBackend)
            kept.append(runtime)
            let gate = await waitForNominalThermal(maxSeconds: 600, pollSeconds: 30, log: log)
            write("waited_s=\(gate.waited)\nstate=\(gate.state)\ntimed_out=\(gate.timedOut ? 1 : 0)\n",
                  to: out.appendingPathComponent("thermal_gate.txt"))
            let before = resultFiles()
            let ended = ExitCode()
            await HeadlessRun(spec: spec, runtime: runtime, log: log, finish: { ended.value = $0 }).runAll()
            code = ended.value ?? -1
            added = resultFiles().subtracting(before).sorted()
        }
        write(added.map { $0 + "\n" }.joined(), to: out.appendingPathComponent("records.txt"))
        tee.stop()
        write("\(code)\n", to: out.appendingPathComponent("yardstick.done"))
        return DDPOutcome(code: code, failure: nil, runs: spec.runs, newFiles: added)
    }

    /// Waits before run 1 until the unit's thermal state is nominal, as the Android lab wrapper does
    /// (android/ddp/ddp_cell.sh gate_thermal): the state read every `pollSeconds`, for at most
    /// `maxSeconds`; a wait that runs out is noted and the run goes on. The lab picks the unit, so a
    /// unit that is still warm cools here, inside the --xctest-timeout. Fixed values of the lab build.
    @MainActor
    private static func waitForNominalThermal(maxSeconds: Int, pollSeconds: Int,
                                              log: @MainActor (String) -> Void) async
        -> (waited: Int, state: String, timedOut: Bool) {
        let start = Date()
        var state = ProcessInfo.processInfo.thermalState
        if state != .nominal {
            log("YARDSTICK_NOTE thermal_gate state=\(ThermalMonitor.describe(state)) waiting max_s=\(maxSeconds) poll_s=\(pollSeconds)")
        }
        var timedOut = false
        while state != .nominal {
            let elapsed = Int(Date().timeIntervalSince(start))
            if elapsed >= maxSeconds {
                timedOut = true
                break
            }
            let pause = UInt64(min(pollSeconds, maxSeconds - elapsed))
            // a cancelled sleep must not turn the wait into a busy loop: stop waiting, run
            guard (try? await Task.sleep(nanoseconds: pause * 1_000_000_000)) != nil else { break }
            state = ProcessInfo.processInfo.thermalState
        }
        let waited = Int(Date().timeIntervalSince(start).rounded())
        let described = ThermalMonitor.describe(state)
        log("YARDSTICK_NOTE thermal_gate waited_s=\(waited) state=\(described)" + (timedOut ? " timed_out=1" : ""))
        return (waited, described, timedOut)
    }

    /// Documents/out/, emptied: nothing from an earlier run may pass as this run's output.
    private static func freshOutDirectory() -> URL {
        let out = documents.appendingPathComponent("out", isDirectory: true)
        try? FileManager.default.removeItem(at: out)
        try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
        return out
    }

    /// nil when the catalog model's file is where MediaPipeRuntime reads it
    /// (HFDownloader.modelDirectory + primaryFile), or when the id is not in the catalog (the run
    /// reports that itself); else that path, relative to the container. A file pushed flat into
    /// Documents/ is moved there first.
    private static func missingModelFile(modelId: String) -> String? {
        guard let model = ModelCatalog.liteRTLM.first(where: { $0.id == modelId }) else { return nil }
        let dir = HFDownloader.modelDirectory(runtime: .mediaPipe, hfRepoId: model.hfRepoId)
        let fm = FileManager.default
        if model.primaryFile.isEmpty {
            let present = ((try? fm.contentsOfDirectory(atPath: dir.path)) ?? []).contains { !$0.hasPrefix(".") }
            return present ? nil : relative(dir)
        }
        let file = dir.appendingPathComponent(model.primaryFile)
        let flat = documents.appendingPathComponent(model.primaryFile)
        if !fm.fileExists(atPath: file.path), fm.fileExists(atPath: flat.path) {
            try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
            try? fm.moveItem(at: flat, to: file)
        }
        return fm.fileExists(atPath: file.path) ? nil : relative(file)
    }

    private static func relative(_ url: URL) -> String {
        let home = NSHomeDirectory()
        return url.path.hasPrefix(home + "/") ? String(url.path.dropFirst(home.count + 1)) : url.path
    }

    private static func resultFiles() -> Set<String> {
        let dir = ResultStore.shared.resultsDirectory
        return Set(((try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []).filter { !$0.hasPrefix(".") })
    }

    private static func listing(_ dir: URL) -> String {
        ((try? FileManager.default.contentsOfDirectory(atPath: dir.path))?.sorted() ?? ["(unreadable)"])
            .joined(separator: ", ")
    }

    private static func write(_ text: String, to url: URL) {
        try? Data(text.utf8).write(to: url, options: .atomic)
    }
}

/// The exit code a run's `finish` hands over (HeadlessRun.finish), kept instead of exiting.
@MainActor
private final class ExitCode {
    var value: Int32?
}

/// Mirrors this process's stdout and stderr (fd 1 and 2, one pipe, so their lines keep their order)
/// into a file until `stop()`, still passing every byte to the original stdout.
final class ConsoleTee: @unchecked Sendable {
    private var readEnd: Int32 = -1
    private var saved: (out: Int32, err: Int32) = (-1, -1)
    private var file: Int32 = -1
    private let drained = DispatchSemaphore(value: 0)

    init(path: String) {
        fflush(stdout)
        fflush(stderr)
        var ends: [Int32] = [-1, -1]
        file = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, 0o644)
        guard file >= 0, pipe(&ends) == 0 else { return }
        readEnd = ends[0]
        saved = (dup(STDOUT_FILENO), dup(STDERR_FILENO))
        dup2(ends[1], STDOUT_FILENO)
        dup2(ends[1], STDERR_FILENO)
        close(ends[1])
        let (source, sink, echo, drained) = (readEnd, file, saved.out, drained)
        Thread.detachNewThread {
            var buffer = [UInt8](repeating: 0, count: 16_384)
            while true {
                let n = buffer.withUnsafeMutableBytes { read(source, $0.baseAddress, $0.count) }
                if n < 0 && errno == EINTR { continue }
                if n <= 0 { break }
                buffer.withUnsafeBytes { bytes in
                    var done = 0
                    while done < n {
                        let w = write(sink, bytes.baseAddress! + done, n - done)
                        if w < 0 && errno == EINTR { continue }
                        if w <= 0 { break }
                        done += w
                    }
                    _ = write(echo, bytes.baseAddress, n)
                }
            }
            drained.signal()
        }
    }

    /// Restores fd 1 and 2 (closing the pipe's last write ends), waits until every byte written
    /// before is in the file, and closes it.
    func stop() {
        guard readEnd >= 0 else {
            if file >= 0 { close(file); file = -1 }
            return
        }
        fflush(stdout)
        fflush(stderr)
        dup2(saved.out, STDOUT_FILENO)
        dup2(saved.err, STDERR_FILENO)
        drained.wait()
        close(readEnd)
        close(saved.out)
        close(saved.err)
        close(file)
        readEnd = -1
        file = -1
    }
}
