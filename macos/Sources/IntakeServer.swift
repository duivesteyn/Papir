// IntakeServer — the receiver lives in the app, so enabling the feature in
// Settings is the whole setup. Loopback only, bearer-token only, and it never
// sends anything itself: a request is fetched into the normal review window.

import Foundation
import Network

struct IntakeRequest {
    let method: String
    let path: String
    let headers: [String: String]
    let body: Data

    func header(_ name: String) -> String? { headers[name.lowercased()] }
}

struct IntakeReply {
    let status: Int
    let body: Any
    var contentType: String = "application/json"

    static func ok(_ payload: [String: Any] = [:]) -> IntakeReply {
        var body: [String: Any] = ["ok": true]
        body.merge(payload) { _, new in new }
        return IntakeReply(status: 200, body: body)
    }

    static func error(_ status: Int, _ message: String) -> IntakeReply {
        IntakeReply(status: status, body: ["ok": false, "error": message])
    }
}

final class IntakeServer {
    typealias Handler = (_ url: String, _ title: String?) async -> IntakeReply

    private var listener: NWListener?
    private let queue = DispatchQueue(label: "com.bmd.papir.intake")
    private let token: String
    private let port: UInt16
    private let handle: Handler

    init(token: String, port: UInt16 = 47821, handle: @escaping Handler) {
        self.token = token
        self.port = port
        self.handle = handle
    }

    /// `onState` reports ready/failed; a taken port arrives there as `.failed`
    /// (usually because `papir serve` is already running).
    func start(onState: @escaping (NWListener.State) -> Void) throws {
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true
        parameters.requiredLocalEndpoint = NWEndpoint.hostPort(
            host: "127.0.0.1",
            port: NWEndpoint.Port(rawValue: port) ?? .any
        )
        let listener = try NWListener(using: parameters)
        listener.stateUpdateHandler = onState
        listener.newConnectionHandler = { [weak self] connection in
            self?.accept(connection)
        }
        listener.start(queue: queue)
        self.listener = listener
    }

    func stop() {
        listener?.stateUpdateHandler = nil
        listener?.cancel()
        listener = nil
    }

    // MARK: - Connection handling

    private func accept(_ connection: NWConnection) {
        connection.start(queue: queue)
        read(connection, buffer: Data())
    }

    private func read(_ connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { [weak self] chunk, _, isComplete, error in
            guard let self else { return }
            var buffer = buffer
            if let chunk { buffer.append(chunk) }

            if let (request, _) = Self.parse(buffer) {
                Task {
                    let reply = await self.respond(to: request)
                    self.write(reply, on: connection)
                }
                return
            }
            if error != nil || isComplete || buffer.count > 1_048_576 {
                connection.cancel()
                return
            }
            self.read(connection, buffer: buffer)
        }
    }

    private func respond(to request: IntakeRequest) async -> IntakeReply {
        let path = request.path.split(separator: "?").first.map(String.init) ?? request.path
        if request.method == "OPTIONS" { return IntakeReply(status: 204, body: "") }
        if path == "/pair" {
            return IntakeReply(status: 200, body: Self.pairPage, contentType: "text/html; charset=utf-8")
        }
        guard path == "/health" || path == "/send" else {
            return .error(404, "Unknown path.")
        }
        guard Self.authorised(request, token: token) else {
            return .error(401, "Bad or missing token.")
        }
        if request.method == "GET", path == "/health" {
            return .ok(["service": "papir", "intake_enabled": Intake.isEnabled])
        }
        guard request.method == "POST", path == "/send" else {
            return .error(405, "Use POST /send.")
        }
        guard let object = try? JSONSerialization.jsonObject(with: request.body),
              let payload = object as? [String: Any],
              let raw = payload["url"] as? String else {
            return .error(400, "Expected JSON with a url.")
        }
        do {
            let url = try Self.validated(raw)
            let title = (payload["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
            return await handle(url.absoluteString, title?.isEmpty == true ? nil : title)
        } catch {
            return .error(400, error.localizedDescription)
        }
    }

    private func write(_ reply: IntakeReply, on connection: NWConnection) {
        let payload: Data
        if let text = reply.body as? String {
            payload = Data(text.utf8)
        } else {
            payload = (try? JSONSerialization.data(withJSONObject: reply.body)) ?? Data("{}".utf8)
        }
        var head = "HTTP/1.1 \(reply.status) \(Self.reason(reply.status))\r\n"
        head += "Content-Type: \(reply.contentType)\r\n"
        head += "Content-Length: \(payload.count)\r\n"
        head += "Access-Control-Allow-Origin: *\r\n"
        head += "Access-Control-Allow-Headers: authorization, content-type\r\n"
        head += "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        head += "Connection: close\r\n\r\n"
        var data = Data(head.utf8)
        data.append(payload)
        connection.send(content: data, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }

    // MARK: - Pure helpers (tested without a socket)

    static func authorised(_ request: IntakeRequest, token: String) -> Bool {
        guard let header = request.header("authorization") else { return false }
        let parts = header.split(separator: " ", maxSplits: 1).map(String.init)
        guard parts.count == 2, parts[0].lowercased() == "bearer" else { return false }
        return constantTimeEquals(parts[1].trimmingCharacters(in: .whitespaces), token)
    }

    static func constantTimeEquals(_ a: String, _ b: String) -> Bool {
        let left = Array(a.utf8), right = Array(b.utf8)
        guard left.count == right.count else { return false }
        var difference: UInt8 = 0
        for index in left.indices { difference |= left[index] ^ right[index] }
        return difference == 0
    }

    static func validated(_ raw: String) throws -> URL {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host?.isEmpty == false else {
            throw Intake.Failure(message: "Only http and https links can be sent.")
        }
        return url
    }

    /// Returns the request and how many bytes it used, or nil when incomplete.
    static func parse(_ data: Data) -> (IntakeRequest, Int)? {
        guard let headerEnd = data.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        let headLength = headerEnd.upperBound
        guard let head = String(data: data[..<headerEnd.lowerBound], encoding: .utf8) else { return nil }

        let lines = head.components(separatedBy: "\r\n")
        guard let first = lines.first else { return nil }
        let requestLine = first.split(separator: " ")
        guard requestLine.count >= 2 else { return nil }
        let method = String(requestLine[0])
        let path = String(requestLine[1])

        var headers: [String: String] = [:]
        for line in lines.dropFirst() {
            guard let colon = line.firstIndex(of: ":") else { continue }
            let name = line[..<colon].trimmingCharacters(in: .whitespaces).lowercased()
            let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
            headers[name] = value
        }

        let length = Int(headers["content-length"] ?? "0") ?? 0
        guard data.count >= headLength + length else { return nil }
        let body = data.subdata(in: headLength..<(headLength + length))
        return (IntakeRequest(method: method, path: path, headers: headers, body: body),
                headLength + length)
    }

    /// The pairing page. The token rides in the URL fragment, which browsers
    /// never send to the server, so it stays out of any log.
    static let pairPage = """
    <!doctype html><html><head><meta charset="utf-8"><title>Papir</title>
    <style>
      body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
           background:#123325;color:#F3EADB;font:15px/1.5 -apple-system,sans-serif}
      main{text-align:center;max-width:420px}
      h1{font:600 22px/1.2 Georgia,serif;margin:0 0 8px}
      p{color:rgba(243,234,219,.75);margin:0}
    </style></head>
    <body><main><h1 id="t">Connecting to Papir…</h1>
    <p id="m">Handing this browser the key it needs.</p></main></body></html>
    """

    static func reason(_ status: Int) -> String {
        switch status {
        case 200: return "OK"
        case 202: return "Accepted"
        case 204: return "No Content"
        case 400: return "Bad Request"
        case 401: return "Unauthorized"
        case 404: return "Not Found"
        case 405: return "Method Not Allowed"
        case 409: return "Conflict"
        case 500: return "Internal Server Error"
        default: return "OK"
        }
    }
}
