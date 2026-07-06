import SwiftUI

// MARK: - App Theme
struct AppTheme {
    static let primaryBlue = Color(red: 37/255, green: 99/255, blue: 235/255)   // #2563EB
    static let blueLight = Color(red: 219/255, green: 234/255, blue: 254/255)   // #DBEAFE
    static let blueDark = Color(red: 30/255, green: 64/255, blue: 175/255)      // #1E40AF
    static let textDark = Color(red: 30/255, green: 41/255, blue: 59/255)       // #1E293B
    static let textMuted = Color(red: 100/255, green: 116/255, blue: 139/255)   // #64748B
    static let green = Color(red: 22/255, green: 163/255, blue: 74/255)         // #16A34A
    static let red = Color(red: 220/255, green: 38/255, blue: 38/255)           // #DC2626
    static let gray = Color(red: 226/255, green: 232/255, blue: 240/255)        // #E2E8F0
    static let border = Color(red: 203/255, green: 213/255, blue: 225/255)      // #CBD5E1
}

// MARK: - Content View
struct ContentView: View {
    @EnvironmentObject private var manager: PrinterManager
    @State private var tokenInput: String = ""
    @State private var showingLog = true

    var body: some View {
        VStack(spacing: 0) {
            scrollViewContent
        }
        .background(Color.white)
        .onAppear {
            tokenInput = manager.token
            let saved = ConfigManager.shared.load()
            if tokenInput.isEmpty { tokenInput = saved.token }
            manager.token = saved.token
        }
    }

    // MARK: - Scrollable Content
    private var scrollViewContent: some View {
        ScrollView {
            VStack(spacing: 16) {
                headerSection
                statusSection
                Divider()
                if manager.state == .connected {
                    connectedSection
                } else {
                    tokenSection
                }
                Divider()
                logSection
                footerSection
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 20)
        }
    }

    // MARK: - Header
    private var headerSection: some View {
        VStack(spacing: 2) {
            Text("TechExpert")
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(AppTheme.primaryBlue)
            Text("Printer Agent")
                .font(.system(size: 12))
                .foregroundColor(AppTheme.textMuted)
        }
    }

    // MARK: - Status Indicator
    private var statusSection: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(manager.state == .connected ? AppTheme.green :
                      manager.state == .connecting ? AppTheme.primaryBlue :
                      AppTheme.gray)
                .frame(width: 10, height: 10)
            Text(manager.state.label)
                .font(.system(size: 11))
                .foregroundColor(manager.state == .connected ? AppTheme.green :
                                 manager.state == .connecting ? AppTheme.primaryBlue :
                                 AppTheme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Token Input (Disconnected)
    private var tokenSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Token de conexión")
                .font(.system(size: 11, weight: .bold))
                .foregroundColor(AppTheme.textDark)

            Text("Copia el token desde el panel Administración → Impresora")
                .font(.system(size: 9))
                .foregroundColor(AppTheme.textMuted)

            TextField("Pega aquí el token...", text: $tokenInput)
                .textFieldStyle(.plain)
                .font(.system(size: 10, design: .monospaced))
                .padding(8)
                .background(AppTheme.gray.opacity(0.3))
                .cornerBorder(color: AppTheme.border, radius: 6)

            Button(action: { manager.token = tokenInput; manager.connect() }) {
                Text("Conectar")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(AppTheme.primaryBlue)
                    .cornerRadius(6)
            }
            .buttonStyle(.plain)
            .disabled(tokenInput.trimmingCharacters(in: .whitespaces).isEmpty || manager.state == .connecting)
        }
    }

    // MARK: - Connected View
    private var connectedSection: some View {
        VStack(spacing: 14) {
            // Account card
            VStack(alignment: .leading, spacing: 2) {
                Text("CUENTA CONECTADA")
                    .font(.system(size: 8, weight: .bold))
                    .foregroundColor(AppTheme.primaryBlue)
                Text("TechExpert")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(AppTheme.textDark)
                Text("Agente conectado vía túnel")
                    .font(.system(size: 10))
                    .foregroundColor(AppTheme.textMuted)
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(AppTheme.blueLight)
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(AppTheme.primaryBlue, lineWidth: 1))

            // Actions
            VStack(alignment: .leading, spacing: 6) {
                Text("ACCIONES")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(AppTheme.textMuted)

                HStack(spacing: 8) {
                    actionButton("🧾 Probar ticket", color: AppTheme.primaryBlue, action: manager.testPrint)
                    actionButton("💰 Abrir cajón", color: AppTheme.primaryBlue, action: manager.openDrawer)
                }

                HStack(spacing: 8) {
                    actionButton("🔍 Estado", color: AppTheme.primaryBlue, action: manager.requestStatus)
                    actionButton("❌ Desconectar", color: AppTheme.red, action: manager.disconnect)
                }
            }
        }
    }

    private func actionButton(_ title: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(color)
                .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }

    // MARK: - Log
    private var logSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("REGISTRO")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(AppTheme.textMuted)
                Spacer()
                Button("Limpiar") {
                    manager.logs.removeAll()
                }
                .buttonStyle(.plain)
                .font(.system(size: 9))
                .foregroundColor(AppTheme.primaryBlue)
                .cursor(.pointingHand)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 1) {
                        ForEach(manager.logs) { entry in
                            HStack(alignment: .top, spacing: 4) {
                                Text(entry.timestamp, style: .time)
                                    .font(.system(size: 8, design: .monospaced))
                                    .foregroundColor(AppTheme.textMuted)
                                    .frame(width: 45, alignment: .leading)
                                Text(entry.message)
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundColor(colorForLevel(entry.level))
                                    .textSelection(.enabled)
                            }
                            .id(entry.id)
                        }
                    }
                    .padding(8)
                }
                .frame(height: 120)
                .background(AppTheme.gray.opacity(0.3))
                .cornerRadius(6)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(AppTheme.border, lineWidth: 1))
                .onChange(of: manager.logs.count) { _ in
                    if let last = manager.logs.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
    }

    private func colorForLevel(_ level: PrinterManager.LogLevel) -> Color {
        switch level {
        case .info: return AppTheme.textDark
        case .success: return AppTheme.green
        case .error: return AppTheme.red
        case .debug: return AppTheme.textMuted
        case .command: return AppTheme.primaryBlue
        }
    }

    // MARK: - Footer
    private var footerSection: some View {
        HStack {
            Spacer()
            Text("v2.0.0 | sattpv.techexpert.cloud")
                .font(.system(size: 8))
                .foregroundColor(AppTheme.textMuted)
        }
    }
}

// MARK: - Corner Border Modifier
extension View {
    func cornerBorder(color: Color, radius: CGFloat) -> some View {
        self.overlay(
            RoundedRectangle(cornerRadius: radius)
                .stroke(color, lineWidth: 1)
        )
    }
}

// MARK: - Preview
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(PrinterManager())
    }
}
