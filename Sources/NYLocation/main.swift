import SwiftUI
import AppKit

struct ContentView: View {
    @StateObject private var controller = SpoofController()
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("NY Location")
                .font(.title2.bold())
            Picker("Подключение", selection: $controller.mode) {
                Text("USB").tag("usb")
                Text("Bluetooth").tag("bluetooth")
            }
            .pickerStyle(.segmented)
            .disabled(controller.running)
            Text(controller.mode == "usb"
                ? "Подключите iPhone кабелем, разблокируйте и нажмите «Доверять». Включите Службы геолокации. Для USB нужен режим разработчика."
                : "Включите Bluetooth и Службы геолокации на iPhone. Выберите этот Mac в настройках Bluetooth. Этот режим доступен на Mac с настроенной авторизацией аксессуара.")
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
