import SwiftUI
import AppKit
import UniformTypeIdentifiers

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    static weak var sender: Sender?
    func application(_ sender: NSApplication, open urls: [URL]) {
        Self.sender?.add(urls)
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
    @Published private var loadingDevices = false
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
        checkingAccount = true
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
            if signedIn && (destinationsRefreshedAt.map { Date().timeIntervalSince($0) >= 86400 } ?? true) {
                await refreshDevices()
            }
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
        }
        lastDestinationName = UserDefaults.standard.string(forKey: destinationNameKey) ?? ""
        if let data = UserDefaults.standard.data(forKey: destinationCacheKey),
           let cache = try? JSONDecoder().decode(DestinationCache.self, from: data) {
            devices = cache.devices; defaultTarget = cache.defaultTarget
            cachedAccountName = cache.accountName; destinationsRefreshedAt = cache.refreshedAt
            rememberDestinationName()
        }
    }

    func add(_ urls: [URL]) {
        guard !busy else { return }
        showSuccess = false
        status = "Ready when you are"
        for url in urls where url.isFileURL && !files.contains(url) { files.append(url) }
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
        guard !checkingAccount, !busy, !authBusy, signedIn, !files.isEmpty else { return }
        guard FileManager.default.isExecutableFile(atPath: executable) else {
            status = "Choose your installed papir CLI in Settings first."
            return
        }
        showSuccess = false
        failures = []
        busy = true
        let pending = files
        Task {
            for file in pending {
                status = "Sending \(file.lastPathComponent)…"
                var args = ["send", file.path]
                if pending.count == 1 && !title.isEmpty { args += ["--title", title] }
                if !author.isEmpty { args += ["--author", author] }
                if !target.isEmpty { args += ["--to", target] }
                if convert { args.append("--convert") }
                do {
                    let result = try await run(args)
                    if result.0 { files.removeAll { $0 == file } }
                    else { failures.append(SendResult(name: file.lastPathComponent, success: false, message: result.1)) }
                } catch {
                    failures.append(SendResult(name: file.lastPathComponent, success: false, message: error.localizedDescription))
                }
            }
            busy = false
            showSuccess = failures.isEmpty
            status = files.isEmpty ? "Accepted by service · Device delivery pending" : "Some documents need attention. Review the errors and retry."
        }
    }
    private func run(_ arguments: [String], captureOutput: Bool = false, input: Data? = nil) async throws -> (Bool, String) {
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
        window?.toolbar = nil
        window?.appearance = NSAppearance(named: .darkAqua)
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
                Image(systemName: "doc").font(.title2)
                Text("Papir").font(.title2.weight(.semibold))
                Spacer()
                SettingsLink { Image(systemName: "slider.horizontal.3") }.help("Settings")
            }
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
                if sender.showSuccess {
                    SendSuccessView()
                        .transition(.opacity)
                } else {
                VStack(spacing: 10) {
                Image(systemName: "doc.on.doc").font(.system(size: 30)).foregroundStyle(ivory.opacity(0.72))
                Text("A little less screen time.").font(.headline)
                Text("Drop something good to read.").foregroundStyle(ivory.opacity(0.72))
                Button("Choose Documents…", action: sender.chooseFiles)
            }.frame(maxWidth: .infinity).padding(24)
                .background(hovering ? ivory.opacity(0.12) : .clear)
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(ivory.opacity(0.3), style: StrokeStyle(lineWidth: 1, dash: [5])))
                }
            }
            .animation(.easeInOut(duration: 0.25), value: sender.showSuccess)
                .onDrop(of: [UTType.fileURL.identifier], isTargeted: $hovering) { providers in
                    for provider in providers {
                        _ = provider.loadObject(ofClass: URL.self) { url, _ in
                            if let url { Task { @MainActor in sender.add([url]) } }
                        }
                    }
                    return true
                }
            if sender.checkingAccount {
                if !sender.hasCachedDestination { ProgressView().controlSize(.small) }
            } else if !sender.signedIn {
                SignInView().environmentObject(sender)
            }
            if !sender.files.isEmpty && sender.signedIn {
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
                        HStack { if sender.busy { ProgressView().controlSize(.small) }; Text(sender.busy ? "Sending…" : "Send \(sender.files.count == 1 ? "document" : "documents")") }.frame(maxWidth: .infinity)
                    }.buttonStyle(.borderedProminent).tint(ivory).foregroundStyle(green)
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
        }.padding(24).frame(width: 390).foregroundStyle(ivory).disabled(sender.busy)
            .onOpenURL { sender.add([$0]) }
            .task { await sender.bootstrap() }
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
                SuccessTick().trim(from: 0, to: appeared ? 1 : 0)
                    .stroke(successGreen, style: StrokeStyle(lineWidth: 5, lineCap: .round, lineJoin: .round))
            }
            .frame(width: 64, height: 64)
            .scaleEffect(appeared || reduceMotion ? 1 : 0.8)
            Text("Success").font(.title3.weight(.semibold))
            Text("Accepted by service · Device delivery pending")
                .font(.caption).foregroundStyle(PapirTheme.ivory.opacity(0.72))
            Button("Send more documents…", action: sender.chooseFiles)
        }
        .frame(maxWidth: .infinity).padding(24)
        .accessibilityElement(children: .contain)
        .onAppear {
            withAnimation(reduceMotion ? nil : .easeOut(duration: 0.45)) { appeared = true }
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
    var body: some View {
        ScrollView {
        Form {
            if sender.showsAccountSettings {
                LabeledContent("Account", value: sender.accountName.isEmpty ? "Connected" : sender.accountName)
                TextField("Default author", text: $sender.defaultAuthor)
                Picker("Default destination", selection: $sender.defaultDestination) {
                    Text("All devices").tag("all")
                    Text("Kindle library only").tag("library")
                    ForEach(sender.availableDevices, id: \.serial) { device in Text(device.name ?? device.serial).tag(device.serial) }
                    if !["all", "library"].contains(sender.defaultDestination) && !sender.availableDevices.contains(where: { $0.serial == sender.defaultDestination }) {
                        Text("Saved device (refresh to load name)").tag(sender.defaultDestination)
                    }
                }
                HStack {
                    Button("Save Defaults") { Task { await sender.saveDefaults() } }
                    Button("Refresh Devices") { Task { await sender.refreshDevices() } }
                }.disabled(sender.checkingAccount || sender.authBusy || sender.busy)
                Text("These defaults are shared with the Python CLI.").font(.caption).foregroundStyle(.secondary)
                Button("Sign Out…") { confirmSignOut = true }.disabled(sender.checkingAccount || sender.busy || sender.authBusy)
            } else if sender.checkingAccount {
                ProgressView().controlSize(.small)
            } else { SignInView().environmentObject(sender) }
            if sender.signedIn && !sender.authError.isEmpty { Text(sender.authError).foregroundStyle(.red).font(.caption) }
            Divider()
            Text(sender.usesBundledEngine ? "Python engine included · No separate installation required" : "Using an external engine")
                .font(.caption).foregroundStyle(.secondary)
            DisclosureGroup("Advanced") {
                Text(sender.executable).font(.caption).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                Button("Choose external engine…", action: sender.chooseCLI).disabled(sender.checkingAccount || sender.busy || sender.authBusy)
                Button("Use bundled engine") { sender.executable = sender.bundledExecutable; Task { await sender.bootstrap() } }
                    .disabled(sender.checkingAccount || sender.busy || sender.authBusy)
                TextField("Destination override for this session", text: $sender.target)
                Text("Leave empty to use your saved default.").font(.caption).foregroundStyle(.secondary)
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .frame(width: 440, height: 420)
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
                Text("Papir").font(.title.weight(.semibold))
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
        ScrollView {
            ContentView()
                .fixedSize(horizontal: false, vertical: true)
                .background {
                    GeometryReader { geometry in
                        Color.clear.preference(key: ContentHeightKey.self, value: geometry.size.height)
                    }
                }
        }
        .frame(width: 390, height: min(contentHeight, maximumHeight))
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
        }
    }
}
