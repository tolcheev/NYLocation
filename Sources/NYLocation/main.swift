import SwiftUI
import AppKit

struct ContentView: View {
    @StateObject private var controller = SpoofController()
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("NY Location")
                .font(.title2.bold())
            Text("Перед запуском: выключите авиарежим, включите Bluetooth и Службы геолокации. Сопрягите iPhone с этим Mac.")
                .foregroundStyle(.secondary)
            Button(controller.running ? "Отключить iPhone" : "Подключить и сменить локацию", action: controller.toggle)
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(controller.stopping)
                .frame(maxWidth: .infinity)
            Text(controller.status)
                .foregroundStyle(controller.error ? Color.red : Color.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if controller.running && !controller.error {
                Text("Когда координаты начнут передаваться, откройте на iPhone «Здоровье» → Health Checklist. Настройте апноэ сна, ЭКГ, нерегулярный ритм и уведомления о гипертонии. Затем нажмите «Отключить iPhone».")
                    .font(.callout)
            }
        }
        .padding(24)
        .frame(width: 440)
        .onDisappear { controller.stop() }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

struct NYLocationApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        Window("NY Location", id: "ny-location") { ContentView() }
            .windowResizability(.contentSize)
    }
}
NYLocationApp.main()
