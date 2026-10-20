import SwiftUI
import AppKit
import UniformTypeIdentifiers

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    static weak var sender: Sender? {
        didSet {
            sender?.add(pendingURLs)
            pendingURLs = []
        }
    }
    private static var pendingURLs: [URL] = []
    func application(_ sender: NSApplication, open urls: [URL]) {
        if let model = Self.sender { model.add(urls) }
        else { Self.pendingURLs.append(contentsOf: urls) }
        sender.activate(ignoringOtherApps: true)
        if let window = sender.windows.first(where: { $0.identifier?.rawValue == "main" }) {
            window.deminiaturize(nil)
            window.makeKeyAndOrderFront(nil)
        }
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard Self.sender?.busy == true || Self.sender?.authBusy == true else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "A send is still in progress"
        alert.informativeText = "Keep Papir open until the service responds to avoid an uncertain delivery result."
        alert.addButton(withTitle: "Keep Papir Open")
        alert.runModal()
        sender.windows.first { $0.identifier?.rawValue == "main" }?.makeKeyAndOrderFront(nil)
        return .terminateCancel
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

struct SendResult: Identifiable {
    let id = UUID()
    let name: String
    let success: Bool
    let message: String
}

@MainActor final class Sender: ObservableObject {
    @Published var files: [URL] = []
    @Published var title = ""
    @Published var author = ""
    @Published var target = ""
    @Published private var devices: [Device] = []
    @Published private var defaultTarget: String?
    @Published private(set) var loadingDevices = false
    @Published private(set) var pendingDrops = 0
    @Published private(set) var sendTotal = 0
    @Published private(set) var sendCompleted = 0
    @Published private(set) var sendingFilename = ""
    @Published private(set) var preflighting = false
    var sendProgressText: String { preflighting ? "Checking authentication…" : "Sending \(min(sendCompleted + 1, sendTotal))/\(sendTotal) \(sendTotal == 1 ? "document" : "documents")" }
    @Published private var deviceError = false
    private var deviceRequest = UUID()

    struct Device: Codable { let serial: String; let name: String? }
    struct Destinations: Decodable {
        let default_target: String?
        let devices: [Device]
    }
    var destinationName: String {
        let serial = target.isEmpty ? defaultTarget : target
        if serial == "library" { return "Kindle library" }
        if serial == "all" { return "All devices" }
        if let serial, let device = devices.first(where: { $0.serial == serial }),
           let name = device.name, !name.isEmpty { return name }
        if target.isEmpty, !lastDestinationName.isEmpty { return lastDestinationName }
        return "Kindle"
    }
    var hasCachedDestination: Bool { !lastDestinationName.isEmpty || destinationsRefreshedAt != nil }
    @Published private var lastDestinationName = ""
    private let destinationNameKey = "Papir.lastDestinationName"
    private func rememberDestinationName() {
        let serial = target.isEmpty ? defaultTarget : target
        let name: String?
        if serial == "library" { name = "Kindle library" }
        else if serial == "all" { name = "All devices" }
        else { name = devices.first(where: { $0.serial == serial })?.name }
        if let name, !name.isEmpty {
            lastDestinationName = name
            UserDefaults.standard.set(name, forKey: destinationNameKey)
        }
    }
    var destinationHint: String {
        deviceError ? "Could not refresh device names. Your CLI destination is still used." : "Send to \(destinationName)"
    }
    private let destinationCacheKey = "Papir.destinationCache"
    private struct DestinationCache: Codable {
        let devices: [Device]
        let defaultTarget: String?
        let accountName: String
        let refreshedAt: Date
    }
    private var cachedAccountName = ""
    private var destinationsRefreshedAt: Date?
    private func clearDestinationCache() {
        UserDefaults.standard.removeObject(forKey: destinationCacheKey)
        UserDefaults.standard.removeObject(forKey: destinationNameKey)
        lastDestinationName = ""
        devices = []; defaultTarget = nil; destinationsRefreshedAt = nil; cachedAccountName = ""
        deviceRequest = UUID(); loadingDevices = false; deviceError = false
    }
    func refreshDevices() async {
        let request = UUID()
        deviceRequest = request
        loadingDevices = true
        deviceError = false
        defer { if deviceRequest == request { loadingDevices = false } }
        do {
            let response = try await run(["--desktop"], captureOutput: true, input: JSONSerialization.data(withJSONObject: ["action": "devices"]))
            guard deviceRequest == request else { return }
            guard response.0 else { deviceError = true; return }
            let data = try JSONDecoder().decode(Destinations.self, from: Data(response.1.utf8))
            devices = data.devices
            defaultTarget = data.default_target
            rememberDestinationName()
            destinationsRefreshedAt = Date()
            cachedAccountName = accountName
            let cache = DestinationCache(devices: devices, defaultTarget: defaultTarget,
                                         accountName: accountName, refreshedAt: Date())
            if let encoded = try? JSONEncoder().encode(cache) {
                UserDefaults.standard.set(encoded, forKey: destinationCacheKey)
            }
        } catch { if deviceRequest == request { deviceError = true } }
    }
    @Published var convert = false
    @Published var busy = false
    @Published var failures: [SendResult] = []
    @Published var showSuccess = false
    @Published var status = "Ready when you are"
    @Published var executable = ""
    @Published var signedIn = false
    @Published var checkingAccount = true
    @Published var accountName = ""
    @Published var defaultAuthor = ""
    @Published var defaultDestination = "all"
    @Published var authBusy = false
    @Published var authError = ""
    @Published var redirect = ""
    @Published var awaitingRedirect = false
    private var verifier = ""
    private var signinURL: URL?

    var bundledExecutable: String {
        Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/papir-engine").path
    }
    var availableDevices: [Device] { devices }
    var usesBundledEngine: Bool { executable == bundledExecutable }

    struct BridgeReply: Decodable {
        let ok: Bool
        let error: String?
        let signed_in: Bool?
        let account_name: String?
        let default_author: String?
        let default_target: String?
        let url: String?
        let verifier: String?
    }
    private func bridge(_ payload: [String: String]) async throws -> BridgeReply {
        let response = try await run(["--desktop"], captureOutput: true,
                                     input: JSONSerialization.data(withJSONObject: payload))
        let reply = try JSONDecoder().decode(BridgeReply.self, from: Data(response.1.utf8))
        guard reply.ok else {
            throw NSError(domain: "Papir", code: 1, userInfo: [NSLocalizedDescriptionKey: reply.error ?? "Could not complete this action."])
        }
        return reply
    }
    private let settingsCacheKey = "Papir.settingsCache"
    private struct SettingsCache: Codable {
        let accountName: String
        let author: String
        let destination: String
    }
    @Published private var hasCachedSettings = false
    var showsAccountSettings: Bool { signedIn || (checkingAccount && hasCachedSettings) }
    private func cacheSettings(_ reply: BridgeReply) {
        guard reply.signed_in == true else {
            UserDefaults.standard.removeObject(forKey: settingsCacheKey)
            hasCachedSettings = false
            return
        }
        let cache = SettingsCache(accountName: reply.account_name ?? "",
                                  author: reply.default_author ?? "",
                                  destination: reply.default_target ?? "all")
        if let data = try? JSONEncoder().encode(cache) {
            UserDefaults.standard.set(data, forKey: settingsCacheKey)
            hasCachedSettings = true
        }
    }
    private func applyAccount(_ reply: BridgeReply) {
        cacheSettings(reply)
        signedIn = reply.signed_in ?? false
        accountName = reply.account_name ?? ""
        defaultAuthor = reply.default_author ?? ""
        defaultDestination = reply.default_target ?? "all"
        if signedIn {
            defaultTarget = defaultDestination
            rememberDestinationName()
        }
    }
    private var checkingAccountInFlight = false
    func bootstrap() async {
        guard !checkingAccountInFlight else { return }
        checkingAccountInFlight = true
        let previousAuthor = defaultAuthor
        let previousDestination = defaultDestination
        let previousAccount = accountName
        checkingAccount = !hasCachedSettings
        defer { checkingAccountInFlight = false }
        defer { checkingAccount = false }
        do {
            let reply = try await bridge(["action": "status"])
            if reply.signed_in == true && !cachedAccountName.isEmpty && cachedAccountName != (reply.account_name ?? "") { clearDestinationCache() }
            let editedAuthor = defaultAuthor != previousAuthor ? defaultAuthor : nil
            let editedDestination = defaultDestination != previousDestination ? defaultDestination : nil
            applyAccount(reply)
            if signedIn && previousAccount == accountName {
                if let editedAuthor { defaultAuthor = editedAuthor }
                if let editedDestination { defaultDestination = editedDestination }
            }
            checkingAccount = false
        } catch { authError = error.localizedDescription }
    }
    func beginSignIn() async {
        guard !authBusy, !signedIn else { return }
        authBusy = true; authError = ""; redirect = ""; verifier = ""
        defer { authBusy = false }
        do {
            let reply = try await bridge(["action": "login_begin"])
            guard let rawURL = reply.url, let url = URL(string: rawURL), let value = reply.verifier else { return }
            verifier = value; signinURL = url; awaitingRedirect = true
            if !NSWorkspace.shared.open(url) { authError = "Could not open your browser. Use Open Browser to try again." }
        } catch { authError = error.localizedDescription }
    }
    func reopenBrowser() { if let url = signinURL { NSWorkspace.shared.open(url) } }
    func finishSignIn() async {
        guard !authBusy, !verifier.isEmpty, !redirect.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        authBusy = true; authError = ""
        defer { authBusy = false }
        do {
            let reply = try await bridge(["action": "login_finish", "redirect": redirect, "verifier": verifier])
            redirect = ""; verifier = ""; signinURL = nil; awaitingRedirect = false
            applyAccount(reply)
            await refreshDevices()
        } catch { authError = error.localizedDescription }
    }
    func cancelSignIn() { redirect = ""; verifier = ""; signinURL = nil; awaitingRedirect = false; authError = "" }
    func saveDefaults() async {
        guard !checkingAccount, !authBusy, signedIn, !busy else { return }
        authBusy = true; authError = ""
        defer { authBusy = false }
        do {
            applyAccount(try await bridge(["action": "defaults", "author": defaultAuthor, "target": defaultDestination]))
            await refreshDevices()
        } catch { authError = error.localizedDescription }
    }
    func signOut() async {
        guard !checkingAccount, !authBusy, !busy else { return }
        authBusy = true; authError = ""
        defer { authBusy = false }
        do {
            applyAccount(try await bridge(["action": "logout"]))
            clearDestinationCache(); target = ""; showSuccess = false; cancelSignIn()
        } catch { authError = error.localizedDescription }
    }

    init() {
        AppDelegate.sender = self
        executable = bundledExecutable
        if let data = UserDefaults.standard.data(forKey: settingsCacheKey),
           let cache = try? JSONDecoder().decode(SettingsCache.self, from: data) {
            accountName = cache.accountName; defaultAuthor = cache.author
            defaultDestination = cache.destination; defaultTarget = cache.destination
            hasCachedSettings = true
            signedIn = true; checkingAccount = false
        }
        lastDestinationName = UserDefaults.standard.string(forKey: destinationNameKey) ?? ""
        if let data = UserDefaults.standard.data(forKey: destinationCacheKey),
           let cache = try? JSONDecoder().decode(DestinationCache.self, from: data) {
            devices = cache.devices; defaultTarget = cache.defaultTarget
            cachedAccountName = cache.accountName; destinationsRefreshedAt = cache.refreshedAt
            rememberDestinationName()
        }
    }

    private struct IntakeBatch {
        var remaining: Int
        var urls: [URL] = []
        var failed = false
    }
    private var intakeOrder: [UUID] = []
    private var intakeBatches: [UUID: IntakeBatch] = [:]

    private func flushIntake() {
        while let id = intakeOrder.first, let batch = intakeBatches[id], batch.remaining == 0 {
            intakeOrder.removeFirst()
            intakeBatches.removeValue(forKey: id)
            showSuccess = false
            status = batch.failed ? "Could not read a dropped document. Try Choose Documents…" : "Ready when you are"
            let sorted = batch.urls.filter { $0.isFileURL }.sorted {
                let comparison = $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent)
                return comparison == .orderedSame ? $0.path < $1.path : comparison == .orderedAscending
            }
            for url in sorted where !files.contains(url) { files.append(url) }
        }
    }
    func add(_ urls: [URL]) {
        guard !busy else { return }
        let id = UUID()
        intakeOrder.append(id)
        intakeBatches[id] = IntakeBatch(remaining: 0, urls: urls)
        flushIntake()
    }
    func acceptDrop(_ providers: [NSItemProvider]) -> Bool {
        guard !busy else { return false }
        let supported = providers.filter { $0.canLoadObject(ofClass: URL.self) }
        guard !supported.isEmpty else { return false }
        let id = UUID()
        intakeOrder.append(id)
        intakeBatches[id] = IntakeBatch(remaining: supported.count)
        pendingDrops += supported.count
        for provider in supported {
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                Task { @MainActor in
                    self.pendingDrops -= 1
                    guard var batch = self.intakeBatches[id] else { return }
                    batch.remaining -= 1
                    if let url { batch.urls.append(url) }
                    else { batch.failed = true }
                    self.intakeBatches[id] = batch
                    self.flushIntake()
                }
            }
        }
        return true
    }
    func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        if panel.runModal() == .OK { add(panel.urls) }
    }
    func chooseCLI() {
        let panel = NSOpenPanel()
        panel.message = "Choose the installed papir Python CLI executable."
        panel.showsHiddenFiles = true
        if panel.runModal() == .OK, let url = panel.url {
            executable = url.path
            Task { await bootstrap() }
        }
    }
    func send() {
        guard !checkingAccount, !busy, !authBusy, pendingDrops == 0, signedIn, !files.isEmpty else { return }
        guard FileManager.default.isExecutableFile(atPath: executable) else {
            status = "Choose your installed papir CLI in Settings first."
            return
        }
        showSuccess = false
        failures = []
        let pending = files
        sendTotal = pending.count
        sendCompleted = 0
        sendingFilename = pending[0].lastPathComponent
        busy = true
        preflighting = true
        status = "Checking authentication…"
        // Capture this batch's options before the first suspension.
        let batchTitle = title, batchAuthor = author, batchTarget = target, batchConvert = convert
        Task {
            defer { preflighting = false; busy = false }
            do {
                let reply = try await bridge(["action": "preflight"])
                applyAccount(reply)
                guard signedIn else {
                    status = "Sign in to send your documents."
                    return
                }
            } catch {
                status = "Authentication check failed. Your documents are ready to retry."
                failures = [SendResult(name: "Before sending", success: false, message: error.localizedDescription)]
                return
            }
            preflighting = false
            for file in pending {
                sendingFilename = file.lastPathComponent
                status = "Sending \(file.lastPathComponent)…"
                var args = ["send", file.path]
                if pending.count == 1 && !batchTitle.isEmpty { args += ["--title", batchTitle] }
                if !batchAuthor.isEmpty { args += ["--author", batchAuthor] }
                if !batchTarget.isEmpty { args += ["--to", batchTarget] }
                if batchConvert { args.append("--convert") }
                do {
                    let result = try await run(args)
                    if result.0 { files.removeAll { $0 == file } }
                    else { failures.append(SendResult(name: file.lastPathComponent, success: false, message: result.1)) }
                } catch {
                    failures.append(SendResult(name: file.lastPathComponent, success: false, message: error.localizedDescription))
                }
                sendCompleted += 1
            }
            showSuccess = failures.isEmpty
            status = files.isEmpty ? "Accepted by service · Device delivery pending" : "Some documents need attention. Review the errors and retry."
        }
    }
    private func run(_ arguments: [String], captureOutput: Bool = false, input: Data? = nil) async throws -> (Bool, String) {
        let engine = executable
        return try await Task.detached(priority: .userInitiated) {
            try await Self.execute(engine, arguments: arguments, captureOutput: captureOutput, input: input)
        }.value
    }
    nonisolated private static func execute(_ executable: String, arguments: [String], captureOutput: Bool, input: Data?) async throws -> (Bool, String) {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let output = directory.appendingPathComponent("stdout")
        let errors = directory.appendingPathComponent("stderr")
        FileManager.default.createFile(atPath: output.path, contents: nil, attributes: [.posixPermissions: 0o600])
        FileManager.default.createFile(atPath: errors.path, contents: nil, attributes: [.posixPermissions: 0o600])
        let stdout = try FileHandle(forWritingTo: output)
        let stderr = try FileHandle(forWritingTo: errors)
        defer {
            try? stdout.close(); try? stderr.close()
            try? FileManager.default.removeItem(at: directory)
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: executable)
        task.arguments = arguments
        let inputPipe = Pipe()
        task.standardInput = input == nil ? FileHandle.nullDevice : inputPipe.fileHandleForReading
        task.standardOutput = stdout
        task.standardError = stderr
        let code: Int32 = try await withCheckedThrowingContinuation { continuation in
            task.terminationHandler = { completed in continuation.resume(returning: completed.terminationStatus) }
            do {
                try task.run()
                if let input {
                    try? inputPipe.fileHandleForWriting.write(contentsOf: input)
                    try? inputPipe.fileHandleForWriting.close()
                }
            } catch { task.terminationHandler = nil; continuation.resume(throwing: error) }
        }
        if code == 0 {
            return (true, captureOutput ? try String(contentsOf: output, encoding: .utf8) : "Accepted by service · Device delivery pending")
        }
        if arguments == ["--desktop"] {
            return (false, (try? String(contentsOf: output, encoding: .utf8)) ?? "")
        }
        let message = (try? String(contentsOf: errors, encoding: .utf8)) ?? ""
        return (false, message.isEmpty ? "papir exited with status \(code)." : String(message.suffix(3000)))
    }
}

enum PapirTheme {
    static let green = Color(red: 18.0 / 255, green: 51.0 / 255, blue: 37.0 / 255)
    static let ivory = Color(red: 243.0 / 255, green: 234.0 / 255, blue: 219.0 / 255)
}

struct PapirWindowStyle: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async { style(view.window) }
        return view
    }
    func updateNSView(_ view: NSView, context: Context) {
        DispatchQueue.main.async { style(view.window) }
    }
    private func style(_ window: NSWindow?) {
        window?.backgroundColor = NSColor(red: 18.0 / 255, green: 51.0 / 255, blue: 37.0 / 255, alpha: 1)
        window?.styleMask.insert(.fullSizeContentView)
        window?.titlebarAppearsTransparent = true
        window?.titleVisibility = .hidden
        window?.titlebarSeparatorStyle = .none
        window?.isMovableByWindowBackground = true
        window?.appearance = NSAppearance(named: .darkAqua)
    }
}

struct PapirSendButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .foregroundStyle(PapirTheme.green)
            .padding(.vertical, 9)
            .background(PapirTheme.ivory.opacity(configuration.isPressed ? 0.82 : 1), in: RoundedRectangle(cornerRadius: 7))
            .opacity(isEnabled ? 1 : 0.65)
    }
}

struct ContentView: View {
    @EnvironmentObject var sender: Sender
    @State private var hovering = false
    private let green = PapirTheme.green
    private let ivory = PapirTheme.ivory
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Image(systemName: "ipad")
                Text(sender.destinationName)
                    .font(.subheadline).lineLimit(1)
                Spacer()
                Button { Task { await sender.refreshDevices() } } label: { Image(systemName: "arrow.clockwise") }
                    .buttonStyle(.plain).help("Refresh device names").disabled(sender.busy)
            }.help(sender.destinationHint).padding(12).frame(maxWidth: .infinity, alignment: .leading)
                .background(ivory.opacity(0.08), in: RoundedRectangle(cornerRadius: 9))
            ZStack {
                if sender.busy {
                    SendProgressView().transition(.opacity)
                } else if sender.showSuccess {
                    SendSuccessView()
                        .transition(.opacity)
                } else {
                VStack(spacing: 10) {
                if sender.pendingDrops > 0 { ProgressView().controlSize(.small).tint(ivory) }
                Image(systemName: "doc.on.doc").font(.system(size: 30)).foregroundStyle(ivory.opacity(0.72))
                Text("A little less screen time.").font(.headline)
                Text("Drop something good to read.").foregroundStyle(ivory.opacity(0.72))
                Button("Choose Documents…", action: sender.chooseFiles)
            }.frame(maxWidth: .infinity).padding(30)
                .background(hovering ? ivory.opacity(0.12) : .clear)
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(ivory.opacity(0.3), style: StrokeStyle(lineWidth: 1, dash: [5])))
                }
            }
            .animation(.easeInOut(duration: 0.25), value: sender.showSuccess)
            .animation(.easeInOut(duration: 0.25), value: sender.busy)
                .onDrop(of: [UTType.fileURL.identifier], isTargeted: $hovering) { providers in
                    sender.acceptDrop(providers)
                }
            if sender.files.isEmpty && (sender.checkingAccount || sender.loadingDevices) {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small).tint(ivory)
                    Text(sender.checkingAccount ? "Checking account…" : "Refreshing devices…").font(.caption)
                }
            }
            if !sender.checkingAccount && !sender.signedIn {
                SignInView().environmentObject(sender)
            }
            if !sender.files.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(sender.files, id: \.self) { file in
                        HStack {
                            Image(systemName: "doc.text")
                            Text(file.lastPathComponent).lineLimit(1).truncationMode(.middle)
                            Spacer()
                            Button { sender.files.removeAll { $0 == file } } label: { Image(systemName: "xmark") }
                                .buttonStyle(.plain).help("Remove document")
                        }
                    }
                    if sender.files.count == 1 { TextField("Title (use filename by default)", text: $sender.title) }
                    TextField("Author (use CLI default)", text: $sender.author)
                    Toggle("Convert PDF to Kindle format", isOn: $sender.convert).font(.subheadline)
                    Button(action: sender.send) {
                        HStack(spacing: 8) {
                            if sender.busy || sender.checkingAccount || sender.pendingDrops > 0 {
                                ProgressView().controlSize(.small).tint(green)
                            }
                            Text(sender.busy ? sender.sendProgressText : sender.checkingAccount ? "Checking account…" : "Send \(sender.files.count == 1 ? "Document" : "Documents")")
                        }.frame(maxWidth: .infinity)
                    }.buttonStyle(PapirSendButtonStyle())
                        .disabled(sender.checkingAccount || !sender.signedIn || sender.authBusy || sender.pendingDrops > 0)
                }.textFieldStyle(.roundedBorder)
            }
            if !sender.failures.isEmpty {
                Text("NEEDS ATTENTION").font(.caption).foregroundStyle(ivory.opacity(0.72))
                ForEach(sender.failures) { result in
                    HStack(alignment: .top) {
                        Image(systemName: result.success ? "checkmark.circle" : "exclamationmark.circle").foregroundStyle(result.success ? ivory : Color(red: 1, green: 0.65, blue: 0.6))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(result.name).lineLimit(1)
                            Text(result.message).font(.caption).foregroundStyle(ivory.opacity(0.72)).textSelection(.enabled)
                        }
                    }
                }
            }
            Divider()
            Text(sender.status).font(.caption).foregroundStyle(ivory.opacity(0.72)).accessibilityLabel(sender.status)
        }.padding(.horizontal, 24).padding(.bottom, 24).padding(.top, 10).frame(width: 380).foregroundStyle(ivory).disabled(sender.busy)
            .onOpenURL { sender.add([$0]) }
            .task { await sender.bootstrap() }
    }
}

struct SendProgressView: View {
    @EnvironmentObject var sender: Sender
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var animating = false

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle().fill(PapirTheme.ivory.opacity(0.08))
                Circle().strokeBorder(PapirTheme.ivory.opacity(0.18), lineWidth: 4)
                Circle().trim(from: 0, to: 0.28)
                    .stroke(PapirTheme.ivory, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .rotationEffect(.degrees(animating && !reduceMotion ? 360 : 0))
                    .animation(reduceMotion ? nil : .linear(duration: 1.2).repeatForever(autoreverses: false), value: animating)
                Image(systemName: "doc.badge.arrow.up")
                    .font(.system(size: 34, weight: .medium))
                    .offset(y: animating && !reduceMotion ? -5 : 5)
                    .animation(reduceMotion ? nil : .easeInOut(duration: 0.65).repeatForever(autoreverses: true), value: animating)
            }
            .frame(width: 84, height: 84)
            .accessibilityHidden(true)
            Text(sender.sendProgressText)
                .font(.title3.weight(.semibold)).monospacedDigit()
            Text(sender.sendingFilename)
                .font(.caption).foregroundStyle(PapirTheme.ivory.opacity(0.72))
                .lineLimit(1).truncationMode(.middle)
            ProgressView(value: Double(sender.sendCompleted), total: Double(max(sender.sendTotal, 1)))
                .tint(PapirTheme.ivory)
                .accessibilityLabel("Documents processed")
                .accessibilityValue("\(sender.sendCompleted) of \(sender.sendTotal)")
            Text("\(sender.sendCompleted) of \(sender.sendTotal) processed")
                .font(.caption).monospacedDigit().foregroundStyle(PapirTheme.ivory.opacity(0.72))
        }
        .frame(maxWidth: .infinity).padding(24)
        .background(PapirTheme.ivory.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))
        .onAppear { animating = true }
    }
}

struct SuccessTick: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.width * 0.22, y: rect.height * 0.52))
        path.addLine(to: CGPoint(x: rect.width * 0.43, y: rect.height * 0.72))
        path.addLine(to: CGPoint(x: rect.width * 0.79, y: rect.height * 0.30))
        return path
    }
}

struct SendSuccessView: View {
    @EnvironmentObject var sender: Sender
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false
    private let successGreen = Color(red: 0.35, green: 0.85, blue: 0.55)

    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                Circle().fill(successGreen.opacity(0.12))
                Circle().strokeBorder(successGreen.opacity(0.3), lineWidth: 1)
                SuccessTick().trim(from: 0, to: appeared || reduceMotion ? 1 : 0)
                    .stroke(successGreen, style: StrokeStyle(lineWidth: 5, lineCap: .round, lineJoin: .round))
                    .animation(reduceMotion ? nil : .easeOut(duration: 0.28), value: appeared)
            }
            .frame(width: 64, height: 64)
            .scaleEffect(appeared || reduceMotion ? 1 : 0.55)
            .animation(reduceMotion ? nil : .spring(response: 0.38, dampingFraction: 0.55), value: appeared)
            Text("Success").font(.title3.weight(.semibold))
            Text("Accepted by service · Device delivery pending")
                .font(.caption).foregroundStyle(PapirTheme.ivory.opacity(0.72))
            Button("Send more documents…", action: sender.chooseFiles)
        }
        .frame(maxWidth: .infinity).padding(24)
        .accessibilityElement(children: .contain)
        .onAppear {
            appeared = true
        }
    }
}

struct SignInView: View {
    @EnvironmentObject var sender: Sender
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if sender.awaitingRedirect {
                Text("Finish signing in").font(.headline)
                Text("After signing in with Amazon, copy the final address from your browser and paste it here. A bare authorization code also works.")
                    .font(.subheadline).fixedSize(horizontal: false, vertical: true)
                SecureField("Final browser URL or code", text: $sender.redirect).textFieldStyle(.roundedBorder)
                HStack {
                    Button("Connect Kindle") { Task { await sender.finishSignIn() } }
                        .disabled(sender.redirect.isEmpty || sender.authBusy)
                    Button("Open Browser", action: sender.reopenBrowser)
                    Button("Cancel", action: sender.cancelSignIn).disabled(sender.authBusy)
                }
            } else {
                Text("Connect your Kindle account").font(.headline)
                Text("Sign in in your browser. No Python or Terminal setup needed.").font(.subheadline)
                Button("Sign in with Amazon") { Task { await sender.beginSignIn() } }.disabled(sender.authBusy)
            }
            if sender.authBusy { ProgressView().controlSize(.small) }
            if !sender.authError.isEmpty { Text(sender.authError).font(.caption).foregroundStyle(.red).textSelection(.enabled) }
        }
    }
}

struct PreferencesView: View {
    @EnvironmentObject var sender: Sender
    @State private var confirmSignOut = false
    private let ivory = PapirTheme.ivory
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("settings")
                    .font(.system(size: 22, weight: .semibold, design: .serif))
                if sender.showsAccountSettings {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Account").foregroundStyle(ivory.opacity(0.72))
                            Spacer()
                            Text(sender.accountName.isEmpty ? "Connected" : sender.accountName)
                                .lineLimit(1).truncationMode(.tail)
                        }.font(.subheadline)
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Default author").font(.caption).foregroundStyle(ivory.opacity(0.72))
                            TextField("Your name", text: $sender.defaultAuthor)
                        }
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Default destination").font(.caption).foregroundStyle(ivory.opacity(0.72))
                            Picker("", selection: $sender.defaultDestination) {
                                Text("All devices").tag("all")
                                Text("Kindle library only").tag("library")
                                ForEach(sender.availableDevices, id: \.serial) { device in Text(device.name ?? device.serial).tag(device.serial) }
                                if !["all", "library"].contains(sender.defaultDestination) && !sender.availableDevices.contains(where: { $0.serial == sender.defaultDestination }) {
                                    Text("Saved device (refresh to load name)").tag(sender.defaultDestination)
                                }
                            }.labelsHidden().frame(maxWidth: .infinity, alignment: .leading)
                        }
                        HStack {
                            Button("Save Defaults") { Task { await sender.saveDefaults() } }
                                .buttonStyle(.plain).fontWeight(.semibold)
                            Button("Refresh Devices") { Task { await sender.refreshDevices() } }
                                .buttonStyle(.plain).foregroundStyle(ivory.opacity(0.72))
                        }.disabled(sender.checkingAccount || sender.authBusy || sender.busy)
                        Text("These defaults are shared with the Python CLI.").font(.caption).foregroundStyle(ivory.opacity(0.72))
                        Button("Sign Out…") { confirmSignOut = true }
                            .buttonStyle(.plain)
                            .foregroundStyle(Color(red: 1, green: 0.65, blue: 0.6))
                            .disabled(sender.checkingAccount || sender.busy || sender.authBusy)
                    }
                } else if sender.checkingAccount {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small).tint(ivory)
                        Text("Checking account…").font(.caption).foregroundStyle(ivory.opacity(0.72))
                    }
                } else { SignInView().environmentObject(sender) }
                if sender.signedIn && !sender.authError.isEmpty {
                    Text(sender.authError).foregroundStyle(Color(red: 1, green: 0.65, blue: 0.6)).font(.caption).textSelection(.enabled)
                }
                VStack(alignment: .leading, spacing: 10) {
                    Text(sender.usesBundledEngine ? "Python engine included · No separate installation required" : "Using an external engine")
                        .font(.caption).foregroundStyle(ivory.opacity(0.72))
                    DisclosureGroup("Advanced") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(sender.executable).font(.caption).textSelection(.enabled)
                                .fixedSize(horizontal: false, vertical: true)
                            HStack {
                                Button("Choose external engine…", action: sender.chooseCLI)
                                Button("Use bundled engine") { sender.executable = sender.bundledExecutable; Task { await sender.bootstrap() } }
                            }.disabled(sender.checkingAccount || sender.busy || sender.authBusy)
                            TextField("Destination override for this session", text: $sender.target)
                            Text("Leave empty to use your saved default.").font(.caption).foregroundStyle(ivory.opacity(0.72))
                        }.padding(.top, 4)
                    }.tint(ivory)
                }
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .frame(width: 440, height: 420)
        .foregroundStyle(ivory)
        .textFieldStyle(.roundedBorder)
        .confirmationDialog("Sign out of Papir? This also signs out the CLI on this Mac.", isPresented: $confirmSignOut) {
            Button("Sign Out", role: .destructive) { Task { await sender.signOut() } }
        }
    }
}

struct AboutView: View {
    private var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
    }
    var body: some View {
        VStack(spacing: 16) {
            if let path = Bundle.main.path(forResource: "Papir", ofType: "icns"), let icon = NSImage(contentsOfFile: path) {
                Image(nsImage: icon).resizable().scaledToFit().frame(width: 80, height: 80)
                    .accessibilityLabel("Papir app icon")
            }
            VStack(spacing: 4) {
                Text("papir").font(.system(size: 30, weight: .semibold, design: .serif))
                Text("Version \(version)").font(.caption).foregroundStyle(PapirTheme.ivory.opacity(0.72))
            }
            Text("Created by Benjamin M. Duivesteyn").font(.headline)
            Text("I created Papir as a lightweight, open-source, unintrusive way to send documents to my Kindle from the command line.")
                .multilineTextAlignment(.center).fixedSize(horizontal: false, vertical: true)
            Text("The native Mac app brings the same Python CLI to a simple, on-demand window.")
                .font(.subheadline).multilineTextAlignment(.center)
                .foregroundStyle(PapirTheme.ivory.opacity(0.72))
            Link("Source code · MIT licence", destination: URL(string: "https://github.com/duivesteyn/papir")!)
                .tint(PapirTheme.ivory)
        }.padding(32).frame(width: 360)
            .foregroundStyle(PapirTheme.ivory)
            .background(PapirTheme.green.ignoresSafeArea())
            .background(PapirWindowStyle())
            .preferredColorScheme(.dark)
    }
}

struct AboutCommands: Commands {
    @Environment(\.openWindow) private var openWindow
    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button("About Papir") { openWindow(id: "about") }
        }
    }
}

private struct ContentHeightKey: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

struct PapirMainView: View {
    @State private var contentHeight: CGFloat = 360
    private var maximumHeight: CGFloat {
        max(360, (NSScreen.main?.visibleFrame.height ?? 800) - 80)
    }
    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                Text("papir")
                    .font(.system(size: 24, weight: .semibold, design: .serif))
                    .frame(maxWidth: .infinity)
                HStack {
                    Spacer()
                    SettingsLink { Image(systemName: "slider.horizontal.3") }.help("Settings")
                        .buttonStyle(.plain)
                }.padding(.trailing, 24)
            }
            .frame(height: 32)
            .offset(y: -28)
            ScrollView {
                ContentView()
                    .fixedSize(horizontal: false, vertical: true)
                    .background {
                        GeometryReader { geometry in
                            Color.clear.preference(key: ContentHeightKey.self, value: geometry.size.height)
                        }
                    }
            }
        }
        .frame(width: 380, height: min(contentHeight + 32, maximumHeight))
        .onPreferenceChange(ContentHeightKey.self) { height in
            if height > 0 { contentHeight = ceil(height) }
        }
        .background(PapirTheme.green.ignoresSafeArea())
        .background(PapirWindowStyle())
        .preferredColorScheme(.dark)
    }
}

@main struct PapirApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var sender = Sender()
    var body: some Scene {
        Window("Papir", id: "main") {
            PapirMainView().environmentObject(sender)
        }.windowStyle(.hiddenTitleBar).windowResizability(.contentSize)
            .commands { AboutCommands(); CommandGroup(after: .newItem) { Button("Open Documents…", action: sender.chooseFiles).keyboardShortcut("o").disabled(sender.busy) } }
        Window("About Papir", id: "about") { AboutView() }
            .windowStyle(.hiddenTitleBar)
            .windowResizability(.contentSize)

        Settings {
            PreferencesView().environmentObject(sender)
                .background(PapirTheme.green.ignoresSafeArea())
                .background(PapirWindowStyle())
                .preferredColorScheme(.dark)
        }.windowStyle(.hiddenTitleBar)
    }
}
