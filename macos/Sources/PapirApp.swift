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

    struct Device: Decodable { let serial: String; let name: String? }
    struct Destinations: Decodable {
        let default_target: String?
        let devices: [Device]
    }
    var destinationName: String {
        if !signedIn { return "Sign in to choose your Kindle" }
        let serial = target.isEmpty ? defaultTarget : target
        if serial == "library" { return "Kindle library" }
        if serial == "all" { return "All devices" }
        if let serial {
            if let device = devices.first(where: { $0.serial == serial }), let name = device.name, !name.isEmpty { return name }
            return loadingDevices ? "Loading device…" : "Device: \(serial)"
        }
        if loadingDevices { return "Loading destination…" }
        return deviceError ? "Destination unavailable" : "All devices"
    }
    var destinationHint: String {
        deviceError ? "Could not refresh device names. Your CLI destination is still used." : "Send to \(destinationName)"
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
        } catch { if deviceRequest == request { deviceError = true } }
    }
    @Published var convert = false
    @Published var busy = false
    @Published var results: [SendResult] = []
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
    private func applyAccount(_ reply: BridgeReply) {
        signedIn = reply.signed_in ?? false
        accountName = reply.account_name ?? ""
        defaultAuthor = reply.default_author ?? ""
        defaultDestination = reply.default_target ?? "all"
        defaultTarget = defaultDestination
    }
    func bootstrap() async {
        checkingAccount = true
        defer { checkingAccount = false }
        do {
            let reply = try await bridge(["action": "status"])
            applyAccount(reply)
            if signedIn { await refreshDevices() }
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
        guard !authBusy, signedIn, !busy else { return }
        authBusy = true; authError = ""
        defer { authBusy = false }
        do {
            applyAccount(try await bridge(["action": "defaults", "author": defaultAuthor, "target": defaultDestination]))
            await refreshDevices()
        } catch { authError = error.localizedDescription }
    }
    func signOut() async {
        guard !authBusy, !busy else { return }
        authBusy = true; authError = ""
        defer { authBusy = false }
        do {
            applyAccount(try await bridge(["action": "logout"]))
            devices = []; target = ""; cancelSignIn()
        } catch { authError = error.localizedDescription }
    }

    init() {
        AppDelegate.sender = self
        executable = bundledExecutable
    }

    func add(_ urls: [URL]) {
        guard !busy else { return }
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
        guard !busy, !authBusy, signedIn, !files.isEmpty else { return }
        guard FileManager.default.isExecutableFile(atPath: executable) else {
            status = "Choose your installed papir CLI in Settings first."
            return
        }
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
                    results.insert(SendResult(name: file.lastPathComponent, success: result.0, message: result.1), at: 0)
                    if result.0 { files.removeAll { $0 == file } }
                } catch {
                    results.insert(SendResult(name: file.lastPathComponent, success: false, message: error.localizedDescription), at: 0)
                }
            }
            busy = false
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
        window?.titlebarAppearsTransparent = true
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
            VStack(spacing: 10) {
                Image(systemName: "doc.on.doc").font(.system(size: 30)).foregroundStyle(ivory.opacity(0.72))
                Text("A little less screen time.").font(.headline)
                Text("Drop something good to read.").foregroundStyle(ivory.opacity(0.72))
                Button("Choose Documents…", action: sender.chooseFiles)
            }.frame(maxWidth: .infinity).padding(24)
                .background(hovering ? ivory.opacity(0.12) : .clear)
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(ivory.opacity(0.3), style: StrokeStyle(lineWidth: 1, dash: [5])))
                .onDrop(of: [UTType.fileURL.identifier], isTargeted: $hovering) { providers in
                    for provider in providers {
                        _ = provider.loadObject(ofClass: URL.self) { url, _ in
                            if let url { Task { @MainActor in sender.add([url]) } }
                        }
                    }
                    return true
                }
            if sender.checkingAccount {
                ProgressView("Checking account…")
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
            if !sender.results.isEmpty {
                Text("RECENT SENDS").font(.caption).foregroundStyle(ivory.opacity(0.72))
                ForEach(sender.results.prefix(5)) { result in
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
        Form {
            if sender.signedIn {
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
                }.disabled(sender.authBusy || sender.busy)
                Text("These defaults are shared with the Python CLI.").font(.caption).foregroundStyle(.secondary)
                Button("Sign Out…") { confirmSignOut = true }.disabled(sender.busy || sender.authBusy)
            } else { SignInView().environmentObject(sender) }
            if sender.signedIn && !sender.authError.isEmpty { Text(sender.authError).foregroundStyle(.red).font(.caption) }
            Divider()
            Text(sender.usesBundledEngine ? "Python engine included · No separate installation required" : "Using an external engine")
                .font(.caption).foregroundStyle(.secondary)
            DisclosureGroup("Advanced") {
                Text(sender.executable).font(.caption).textSelection(.enabled)
                Button("Choose external engine…", action: sender.chooseCLI).disabled(sender.busy || sender.authBusy)
                Button("Use bundled engine") { sender.executable = sender.bundledExecutable; Task { await sender.bootstrap() } }
                    .disabled(sender.busy || sender.authBusy)
                TextField("Destination override for this session", text: $sender.target)
                Text("Leave empty to use your saved default.").font(.caption).foregroundStyle(.secondary)
            }
        }.padding(24).frame(width: 440)
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

@main struct PapirApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var sender = Sender()
    var body: some Scene {
        Window("Papir", id: "main") {
            ScrollView { ContentView().environmentObject(sender) }
                .frame(width: 390, height: sender.files.isEmpty && sender.results.isEmpty && sender.signedIn ? 390 : 650)
                .background(PapirTheme.green.ignoresSafeArea())
                .background(PapirWindowStyle())
                .preferredColorScheme(.dark)
        }.windowResizability(.contentSize)
            .commands { AboutCommands(); CommandGroup(after: .newItem) { Button("Open Documents…", action: sender.chooseFiles).keyboardShortcut("o").disabled(sender.busy) } }
        Window("About Papir", id: "about") { AboutView() }
            .windowResizability(.contentSize)

        Settings { PreferencesView().environmentObject(sender) }
    }
}
