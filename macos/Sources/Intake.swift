// Intake — papir:// URLs from the browser, Shortcuts, Raycast or the CLI.
//
// Off unless the user opts in with ~/Library/Application Support/Papir/intake.json:
//     {"enabled": true}
// Nothing personal lives in this file; titles and destinations come from the
// normal Papir configuration at send time.

import Foundation
import Security

enum Intake {

    struct Config: Codable {
        var enabled: Bool?
        var inbox: String?
        var token: String?
    }

    enum Kind { case remote(URL), local(URL) }

    struct Payload {
        let kind: Kind
        let title: String?
        let author: String?
    }

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    // MARK: - Locations

    static var supportDirectory: URL {
        // PAPIR_HOME keeps tests and dry runs out of the real library.
        if let override = ProcessInfo.processInfo.environment["PAPIR_HOME"], !override.isEmpty {
            return URL(fileURLWithPath: (override as NSString).expandingTildeInPath, isDirectory: true)
        }
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("Papir", isDirectory: true)
    }

    static var configURL: URL { supportDirectory.appendingPathComponent("intake.json") }

    static func loadConfig() -> Config {
        guard let data = try? Data(contentsOf: configURL),
              let config = try? JSONDecoder().decode(Config.self, from: data) else { return Config() }
        return config
    }

    static var isEnabled: Bool { loadConfig().enabled == true }

    /// The receiver's bearer token. Created on first enable, reused after that.
    @discardableResult
    static func ensureToken() -> String {
        var config = loadConfig()
        if let token = config.token, !token.isEmpty { return token }
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        let token = bytes.map { String(format: "%02x", $0) }.joined()
        config.token = token
        save(config)
        return token
    }

    static func setEnabled(_ enabled: Bool) {
        var config = loadConfig()
        config.enabled = enabled
        save(config)
    }

    static func save(_ config: Config) {
        do {
            try FileManager.default.createDirectory(at: supportDirectory, withIntermediateDirectories: true,
                                                    attributes: [.posixPermissions: 0o700])
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(config).write(to: configURL, options: .atomic)
            try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: configURL.path)
        } catch {
            // A read-only support directory leaves intake disabled, which is the safe outcome.
        }
    }

    static var inboxDirectory: URL {
        if let path = loadConfig().inbox, !path.isEmpty {
            return URL(fileURLWithPath: (path as NSString).expandingTildeInPath, isDirectory: true)
        }
        return supportDirectory.appendingPathComponent("Inbox", isDirectory: true)
    }

    // MARK: - Parsing

    static func parse(_ url: URL) -> Payload? {
        guard url.scheme?.lowercased() == "papir" else { return nil }
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let title = items.first { $0.name == "title" }?.value.flatMap { $0.isEmpty ? nil : $0 }
        let author = items.first { $0.name == "author" }?.value.flatMap { $0.isEmpty ? nil : $0 }

        if let value = items.first(where: { $0.name == "file" })?.value, !value.isEmpty {
            return Payload(kind: .local(URL(fileURLWithPath: value)), title: title, author: author)
        }
        if let value = items.first(where: { $0.name == "url" })?.value,
           let remote = URL(string: value), let scheme = remote.scheme?.lowercased(),
           scheme == "https" || scheme == "http" {
            return Payload(kind: .remote(remote), title: title, author: author ?? siteName(for: remote))
        }
        return nil
    }

    /// The site a document came from, as the author tag: reporting.t1.com.au -> t1.com.au
    /// A shared report should carry its publisher, not your own name.
    static func siteName(for remote: URL) -> String? {
        guard var host = remote.host?.lowercased(), !host.isEmpty else { return nil }
        if host.hasPrefix("www.") { host = String(host.dropFirst(4)) }
        let labels = host.split(separator: ".").map(String.init)
        guard labels.count >= 2 else { return host }

        // An IP is not a site: keep it as-is rather than inventing a domain.
        if labels.count == 4, labels.allSatisfy({ !$0.isEmpty && $0.allSatisfy(\.isNumber) }) {
            return host
        }
        if host.hasPrefix("[") { return host }

        let twoLevel = Set(["com.au", "net.au", "org.au", "edu.au", "gov.au", "asn.au",
                            "co.uk", "org.uk", "ac.uk", "gov.uk",
                            "co.nz", "co.jp", "ne.jp", "com.br", "co.za", "com.sg", "co.in"])
        let lastTwo = labels.suffix(2).joined(separator: ".")
        if twoLevel.contains(lastTwo), labels.count >= 3 {
            return labels.suffix(3).joined(separator: ".")
        }
        return lastTwo
    }

    // MARK: - Fetching

    static let supportedExtensions: Set<String> = [
        "pdf", "epub", "doc", "docx", "rtf", "txt", "htm", "html", "mobi", "azw", "jpg", "jpeg", "png", "gif", "bmp",
    ]

    /// Save a remote document into the inbox and return the local file URL.
    static func fetch(_ remote: URL) async throws -> URL {
        var request = URLRequest(url: remote)
        request.timeoutInterval = 60
        request.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Papir", forHTTPHeaderField: "User-Agent")

        let (data, response) = try await URLSession.shared.data(for: request)
        if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
            throw Failure(message: "The server returned \(http.statusCode). The link may need a sign-in.")
        }
        if data.count > 200 * 1024 * 1024 {
            throw Failure(message: "That document is larger than the 200 MB Send to Kindle limit.")
        }

        if isWebPage(data) {
            throw Failure(message: "That link returned a web page, not a document. It probably needs a sign-in.")
        }

        let name = filename(for: remote, contentType: (response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Type"), data: data)
        let folder = inboxDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let destination = folder.appendingPathComponent(name)
        try data.write(to: destination, options: .atomic)
        return destination
    }

    /// A PDF-named URL that serves HTML is almost always a sign-in wall.
    static func isWebPage(_ data: Data) -> Bool {
        if data.starts(with: Array("%PDF".utf8)) { return false }
        guard let head = String(data: data.prefix(512), encoding: .utf8)?.lowercased() else { return false }
        return head.contains("<html") || head.contains("<!doctype html")
    }

    /// Keep the URL's own name so `papir send` derives a sensible title from it,
    /// but never trust the remote to name a file: no separators, no dotfiles.
    static func filename(for remote: URL, contentType: String?, data: Data) -> String {
        let raw = remote.lastPathComponent.removingPercentEncoding ?? ""
        var stem = raw.isEmpty ? "" : (raw as NSString).deletingPathExtension
        stem = stem.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        stem = stem.replacingOccurrences(of: "\u{0}", with: "")
        if stem.hasPrefix(".") { stem = String(stem.dropFirst()) }
        if stem.count > 120 { stem = String(stem.prefix(120)) }

        var ext = (raw as NSString).pathExtension.lowercased()
        if ext.isEmpty || !supportedExtensions.contains(ext) {
            if data.starts(with: Array("%PDF".utf8)) { ext = "pdf" }
            else if contentType?.contains("pdf") == true { ext = "pdf" }
            else if contentType?.contains("epub") == true { ext = "epub" }
            else { ext = "pdf" }
        }
        return (stem.isEmpty ? "Document" : stem) + "." + ext
    }
}
