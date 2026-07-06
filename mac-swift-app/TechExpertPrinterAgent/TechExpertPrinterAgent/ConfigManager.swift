import Foundation

struct AppConfig: Codable {
    var token: String = ""
    var printerHost: String = "127.0.0.1"
    var printerPort: Int = 9100
    var tunnelURL: String = "wss://sattpv.techexpert.cloud/tunnel/agent"

    enum CodingKeys: String, CodingKey {
        case token, printerHost = "printer_host", printerPort = "printer_port", tunnelURL = "tunnel_url"
    }
}

class ConfigManager {
    static let shared = ConfigManager()

    private let configPath: URL

    private init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let folder = appSupport.appendingPathComponent("TechExpertPrinterAgent", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        configPath = folder.appendingPathComponent("config.json")
    }

    func load() -> AppConfig {
        guard let data = try? Data(contentsOf: configPath),
              let config = try? JSONDecoder().decode(AppConfig.self, from: data) else {
            return AppConfig()
        }
        return config
    }

    func save(_ config: AppConfig) {
        guard let data = try? JSONEncoder().encode(config) else { return }
        try? data.write(to: configPath)
    }
}
