import XCTest
import BenchmarkAppDDP

/// The bench app's headless run as an XCTest, for Developer Device Platform (`gcloud beta device-run
/// sessions submit xctest`, driven by ios/ddp/run_ddp_ios_lm.py). Before the test the lab pushes the
/// model into Documents/models/litert-lm/<org>__<repo>/ and Documents/yardstick_args.json, the words
/// the attached iPhone's driver gives the app (e.g. ["--yardstick-autorun", "--runtime", "litert-lm",
/// "--model-id", "litert-community/Qwen3-1.7B", "--task", "short-chat", "--runs", "4",
/// "--litert-backend", "gpu"]); after it, it pulls Documents/results/ and Documents/out/. The test
/// runs the app's own headless path once, in this process (DDPHarness.runFromDocuments): run 1 cold,
/// runs 2...N warm, one record per run, as one launch of the app on the attached iPhone. It fails
/// when the run did not start, ended with a code other than 0, or added fewer records than runs.
/// No executionTimeAllowance: the lab's --xctest-timeout is the limit.
final class DDPBenchmarkTests: XCTestCase {
    @MainActor
    func testHeadlessRun() async {
        let outcome = await DDPHarness.runFromDocuments()
        if let failure = outcome.failure {
            XCTFail(failure)
            return
        }
        XCTAssertEqual(outcome.code, 0,
                       "the headless run ended with \(outcome.code.map { String($0) } ?? "no code"); see Documents/out/console.txt")
        let records = outcome.newFiles.filter { $0.hasSuffix(".json") }
        XCTAssertGreaterThanOrEqual(records.count, outcome.runs,
                                    "\(outcome.runs) runs added \(records.count) records: \(outcome.newFiles)")
    }
}
