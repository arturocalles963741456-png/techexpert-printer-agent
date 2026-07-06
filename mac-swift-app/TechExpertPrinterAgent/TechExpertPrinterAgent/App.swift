import SwiftUI

@main
struct TechExpertPrinterAgentApp: App {
    @StateObject private var manager = PrinterManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(manager)
                .frame(minWidth: 420, minHeight: 520)
        }
        .windowResizability(.contentMinSize)
    }
}
