import SwiftUI

struct RunView: View {
    @EnvironmentObject private var session: AppSession
    @State private var selectedTaskID: String = "short-chat"
    @State private var phase: BenchmarkRunner.Phase = .idle
    @State private var partialOutput: String = ""
    @State private var lastResult: BenchmarkResult?
    @State private var lastError: String?
    @State private var runner = BenchmarkRunner()
    @State private var runTask: Task<Void, Never>?

    var body: some View {
        Form {
            Section("Runtime") {
                Picker("Runtime", selection: $session.selectedRuntime) {
                    ForEach(RuntimeKind.allCases) { kind in
                        let rt = session.runtime(for: kind)
                        VStack(alignment: .leading) {
                            Text(kind.displayName)
                            if !rt.isAvailable {
                                Text("framework not added — see runtimes/\(kind.rawValue).md")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .tag(kind)
                    }
                }
                .onChange(of: session.selectedRuntime) { _, _ in
                    session.reconcileSelectedModel()
                }
            }

            Section("Model") {
                let models = session.availableModels()
                if models.isEmpty {
                    Text("This runtime has no models registered yet.")
                        .foregroundStyle(.secondary)
                } else {
                    Picker("Model", selection: $session.selectedModel) {
                        ForEach(models, id: \.id) { model in
                            VStack(alignment: .leading) {
                                Text(model.displayName)
                                Text("\(model.hfRepoId)  •  ~\(Int(model.onDiskSizeMB ?? 0)) MB")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .tag(model)
                        }
                    }
                    .pickerStyle(.navigationLink)
                }
            }

            Section("Task") {
                Picker("Task", selection: $selectedTaskID) {
                    ForEach(BenchmarkTaskCatalog.all, id: \.id) { task in
                        VStack(alignment: .leading) {
                            Text(task.title)
                            Text(task.summary)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .tag(task.id)
                    }
                }
                .pickerStyle(.navigationLink)
            }

            Section("Status") {
                phaseRow
                if case .generating = phase, !partialOutput.isEmpty {
                    Text(partialOutput)
                        .font(.system(.callout, design: .monospaced))
                        .lineLimit(4)
                }
                if let error = lastError {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
            }

            Section {
                Button(action: runBenchmark) {
                    Label(isRunning ? "Cancel" : "Run benchmark",
                          systemImage: isRunning ? "stop.circle.fill" : "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(isRunning ? .red : .accentColor)
                .disabled(!session.runtime(for: session.selectedRuntime).isAvailable && !isRunning)
            }

            if let result = lastResult {
                Section("Last result") {
                    NavigationLink(destination: ResultDetailView(result: result)) {
                        ResultSummaryView(result: result)
                    }
                }
            }
        }
        .navigationTitle("iOS LLM Bench")
        .task {
            session.reconcileSelectedModel()
        }
    }

    private var isRunning: Bool {
        switch phase {
        case .idle, .done, .failed: return false
        default: return true
        }
    }

    @ViewBuilder
    private var phaseRow: some View {
        HStack {
            switch phase {
            case .idle:
                Text("Idle").foregroundStyle(.secondary)
            case .loadingModel(let p):
                VStack(alignment: .leading, spacing: 6) {
                    ProgressView(value: p) {
                        Text("Loading model… \(Int(p * 100))%")
                    }
                    Text("Keep app foregrounded. iOS suspends the download when the screen locks.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            case .generating(let tokens, _):
                ProgressView()
                Text("Generating… \(tokens) tokens")
            case .finalizing:
                ProgressView()
                Text("Finalizing…")
            case .done:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                Text("Done")
            case .failed(let why):
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.red)
                Text(why).lineLimit(2)
            }
        }
    }

    private func runBenchmark() {
        if isRunning {
            runTask?.cancel()
            Task { await runner.cancel() }
            return
        }

        guard let task = BenchmarkTaskCatalog.task(for: selectedTaskID) else { return }
        let runtime = session.runtime(for: session.selectedRuntime)
        let model = session.selectedModel

        lastError = nil
        partialOutput = ""
        phase = .loadingModel(progress: 0)

        runTask = Task {
            let stream = await runner.snapshots()
            let observer = Task {
                for await snapshot in stream {
                    await MainActor.run {
                        self.phase = snapshot.phase
                        if case .generating(_, let preview) = snapshot.phase {
                            self.partialOutput = preview
                        }
                    }
                }
            }
            defer { observer.cancel() }

            do {
                let currentLoaded = await runtime.loadedModelId
                let coldRun = currentLoaded != model.id
                let result = try await runner.run(.init(
                    runtime: runtime, model: model, task: task, coldRun: coldRun
                ))
                await session.record(result)
                await MainActor.run {
                    self.lastResult = result
                }
            } catch is CancellationError {
                await MainActor.run { self.phase = .idle }
            } catch {
                await MainActor.run {
                    self.lastError = error.localizedDescription
                    self.phase = .failed(error.localizedDescription)
                }
            }
        }
    }
}
