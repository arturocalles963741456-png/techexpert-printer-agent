import Foundation
import Combine

enum ConnectionState: Equatable {
    case disconnected
    case connecting
    case connected

    var label: String {
        switch self {
        case .disconnected: return "Desconectado"
        case .connecting: return "Conectando…"
        case .connected: return "Conectado ✅"
        }
    }
}

@MainActor
class PrinterManager: ObservableObject {
    @Published var state: ConnectionState = .disconnected
    @Published var logs: [LogEntry] = []
    @Published var token: String = ""

    private var process: Process?
    private var stdinPipe: Pipe?
    private var stdoutPipe: Pipe?
    private var isShuttingDown = false

    struct LogEntry: Identifiable, Equatable {
        let id = UUID()
        let message: String
        let timestamp: Date
        let level: LogLevel

        init(_ message: String, level: LogLevel = .info) {
            self.message = message
            self.timestamp = Date()
            self.level = level
        }
    }

    enum LogLevel: Equatable {
        case info, success, error, debug, command
    }

    // MARK: - Agent binary path

    private var agentBinaryPath: String {
        if let bundlePath = Bundle.main.path(forResource: "agent-macos-x64", ofType: nil) {
            return bundlePath
        }
        // Fallback: look beside the app
        let appPath = Bundle.main.bundlePath
        let parent = (appPath as NSString).deletingLastPathComponent
        let siblings = [
            (parent as NSString).appendingPathComponent("agent-macos-x64"),
            (parent as NSString).appendingPathComponent("agent")
        ]
        for p in siblings {
            if FileManager.default.isExecutableFile(atPath: p) { return p }
        }
        return "agent-macos-x64"
    }

    // MARK: - Actions

    func connect() {
        guard !token.trimmingCharacters(in: .whitespaces).isEmpty else {
            addLog("Token vacío — introduce un token válido", level: .error)
            return
        }

        // Save token
        var config = ConfigManager.shared.load()
        config.token = token
        ConfigManager.shared.save(config)

        disconnect()
        state = .connecting
        addLog("🔑 Token guardado: \(token.prefix(16))…", level: .info)

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.launchProcess()
        }
    }

    func disconnect() {
        isShuttingDown = true
        if let proc = process, proc.isRunning {
            proc.terminate()
            proc.waitUntilExit()
        }
        process = nil
        stdinPipe = nil
        stdoutPipe = nil
        isShuttingDown = false

        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.state = .disconnected
            self.addLog("❌ Desconectado", level: .error)
        }
    }

    func testPrint() {
        sendCommand(["command": "print_ticket", "text": "🧾 TEST TICKET\nTechExpert TPV\n\nImpresora configurada correctamente\nFecha: \(dateString())"])
    }

    func openDrawer() {
        sendCommand(["command": "open_drawer"])
    }

    func requestStatus() {
        sendCommand(["command": "status"])
    }

    // MARK: - Subprocess

    private func launchProcess() {
        let path = agentBinaryPath

        guard FileManager.default.isExecutableFile(atPath: path) else {
            DispatchQueue.main.async { [weak self] in
                self?.state = .disconnected
                self?.addLog("❌ Binario no encontrado: \(path)", level: .error)
                self?.addLog("   Copia el archivo 'agent-macos-x64' junto a la app", level: .error)
            }
            return
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: path)
        proc.currentDirectoryURL = URL(fileURLWithPath: (path as NSString).deletingLastPathComponent)

        let stdin = Pipe()
        let stdout = Pipe()
        proc.standardInput = stdin
        proc.standardOutput = stdout

        proc.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, !self.isShuttingDown else { return }
                self.state = .disconnected
                self.addLog("⚠️ Proceso del agente terminado", level: .error)
            }
        }

        do {
            try proc.run()
            self.process = proc
            self.stdinPipe = stdin
            self.stdoutPipe = stdout

            DispatchQueue.main.async { [weak self] in
                self?.addLog("🚀 Agente iniciado", level: .info)
            }

            // Read stdout
            let handle = stdout.fileHandleForReading
            handle.readabilityHandler = { [weak self] handle in
                let data = handle.availableData
                guard !data.isEmpty, let output = String(data: data, encoding: .utf8) else { return }
                DispatchQueue.main.async {
                    self?.parseOutput(output)
                }
            }

        } catch {
            DispatchQueue.main.async { [weak self] in
                self?.state = .disconnected
                self?.addLog("❌ Error al iniciar agente: \(error.localizedDescription)", level: .error)
            }
        }
    }

    private func parseOutput(_ output: String) {
        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }

            // Check for JSON results from our commands
            if trimmed.hasPrefix("{"), let data = trimmed.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               json["type"] as? String == "stdin_result" {
                handleStdinResult(json)
                continue
            }

            // Parse agent output for connection status
            if trimmed.contains("✅ Authenticated") || trimmed.contains("auth_ok") {
                DispatchQueue.main.async { [weak self] in
                    self?.state = .connected
                    self?.addLog("✅ Autenticado en el servidor", level: .success)
                }
            } else if trimmed.contains("✅ Connected") {
                DispatchQueue.main.async { [weak self] in
                    self?.addLog("🔌 Conectado al túnel WebSocket", level: .success)
                }
            } else if trimmed.contains("❌") || trimmed.contains("failed") || trimmed.contains("Error") {
                DispatchQueue.main.async { [weak self] in
                    self?.addLog("⚠️ \(trimmed)", level: .error)
                }
            } else if trimmed.contains("🔐") {
                DispatchQueue.main.async { [weak self] in
                    self?.addLog(trimmed, level: .success)
                }
            } else if trimmed.contains("No token") || trimmed.contains("⚠️") {
                DispatchQueue.main.async { [weak self] in
                    self?.addLog(trimmed, level: .error)
                }
            } else if trimmed.count > 3 && !trimmed.hasPrefix("[") && !trimmed.hasPrefix("╔") && !trimmed.hasPrefix("║") && !trimmed.hasPrefix("╚") {
                // Other non-trivial output
                DispatchQueue.main.async { [weak self] in
                    self?.addLog("📡 \(trimmed)", level: .debug)
                }
            }
        }
    }

    private func handleStdinResult(_ json: [String: Any]) {
        let command = json["command"] as? String ?? "unknown"
        let ok = json["ok"] as? Bool ?? false
        let error = json["error"] as? String

        DispatchQueue.main.async { [weak self] in
            switch command {
            case "print_ticket":
                if ok { self?.addLog("✅ Ticket impreso correctamente", level: .success) }
                else { self?.addLog("❌ Error ticket: \(error ?? "desconocido")", level: .error) }
            case "open_drawer":
                if ok { self?.addLog("💰 Cajón abierto", level: .success) }
                else { self?.addLog("❌ Error cajón: \(error ?? "desconocido")", level: .error) }
            case "status":
                if let connected = json["connected"] as? Bool {
                    self?.state = connected ? .connected : .disconnected
                    self?.addLog(connected ? "✅ Agente conectado" : "❌ Agente desconectado", level: connected ? .success : .error)
                }
            default:
                break
            }
        }
    }

    // MARK: - Send command via stdin

    private func sendCommand(_ cmd: [String: Any]) {
        guard let proc = process, proc.isRunning,
              let data = try? JSONSerialization.data(withJSONObject: cmd),
              let jsonStr = String(data: data, encoding: .utf8) else {
            addLog("❌ Agente no iniciado — conéctate primero", level: .error)
            return
        }

        DispatchQueue.main.async { [weak self] in
            let cmdName = cmd["command"] as? String ?? "?"
            self?.addLog("▶️ Enviando: \(cmdName)", level: .command)
        }

        stdinPipe?.fileHandleForWriting.write((jsonStr + "\n").data(using: .utf8)!)
    }

    // MARK: - Logging

    private func addLog(_ message: String, level: LogLevel = .info) {
        DispatchQueue.main.async { [weak self] in
            self?.logs.append(LogEntry(message, level: level))
            if self?.logs.count ?? 0 > 500 {
                self?.logs.removeFirst(self!.logs.count - 500)
            }
        }
    }

    private func dateString() -> String {
        let f = DateFormatter()
        f.dateFormat = "dd/MM/yyyy HH:mm"
        return f.string(from: Date())
    }
}
