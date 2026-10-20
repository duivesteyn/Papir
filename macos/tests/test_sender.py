"""Exercise the real Swift sender against an isolated, simulated engine."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class SenderTests(unittest.TestCase):
    def test_preflight_gates_upload_and_retry_preserves_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = pathlib.Path(directory)
            engine = folder / 'engine'
            engine.write_text('''#!/usr/bin/python3
import json, pathlib, sys
folder = pathlib.Path(__file__).parent
with (folder / 'calls').open('a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:] == ['--desktop']:
    request = json.load(sys.stdin)
    assert request['action'] == 'preflight'
    mode = (folder / 'mode').read_text()
    print(json.dumps({'ok': mode != 'fail', 'signed_in': mode != 'missing', 'error': 'Connection failed'}))
    sys.exit(1 if mode == 'fail' else 0)
''')
            engine.chmod(0o700)
            source = (ROOT / 'macos/Sources/PapirApp.swift').read_text().split('@main struct PapirApp: App')[0]
            source += r'''
@main struct SenderChecks {
    @MainActor static func main() async throws {
        let folder = URL(fileURLWithPath: CommandLine.arguments[1])
        let suite = "PapirSenderTests-" + UUID().uuidString
        let defaults = UserDefaults.standard
        defaults.addSuite(named: suite)
        defer { defaults.removePersistentDomain(forName: suite); defaults.removeSuite(named: suite) }
        let settings = Data(#"{"accountName":"Test","author":"Saved Writer","destination":"library"}"#.utf8)
        UserDefaults(suiteName: suite)!.set(settings, forKey: "Papir.settingsCache")
        let sender = Sender()
        precondition(sender.signedIn && !sender.checkingAccount, "Saved setup must enable Send immediately")
        sender.executable = folder.appendingPathComponent("engine").path
        let file = folder.appendingPathComponent("Document.pdf")
        sender.add([file, file])
        precondition(sender.files.count == 1, "Repeated open events must not duplicate documents")
        func run(_ mode: String) async throws {
            try mode.write(to: folder.appendingPathComponent("mode"), atomically: true, encoding: .utf8)
            sender.send()
            precondition(sender.busy && sender.preflighting)
            for _ in 0..<500 where sender.busy { try await Task.sleep(for: .milliseconds(10)) }
            precondition(!sender.busy && !sender.preflighting, "Send did not finish")
        }
        try await run("fail")
        precondition(sender.files == [file] && sender.sendCompleted == 0 && !sender.failures.isEmpty)
        try await run("success")
        precondition(sender.files.isEmpty && sender.showSuccess && sender.sendCompleted == 1)
        let calls = try String(contentsOf: folder.appendingPathComponent("calls"), encoding: .utf8)
        let expected = "[\"--desktop\"]\n[\"--desktop\"]\n[\"send\", \"" + file.path + "\"]\n"
        precondition(calls == expected, "Uploads must follow a successful preflight and reuse engine defaults")
        sender.add([file])
        try await run("missing")
        precondition(!sender.signedIn && sender.files == [file] && sender.sendCompleted == 0)
        print("Swift sender preflight, failure, retry, defaults, and missing-login checks passed")
    }
}
'''
            swift = folder / 'Checks.swift'
            swift.write_text(source)
            binary = folder / 'Checks'
            subprocess.run(['xcrun', 'swiftc', '-O', '-module-cache-path', str(ROOT / 'macos/build/ModuleCache'), '-parse-as-library', '-swift-version', '5', str(swift), '-o', str(binary)], check=True, capture_output=True, text=True)
            subprocess.run([str(binary), str(folder)], check=True, capture_output=True, text=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
