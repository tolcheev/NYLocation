import AppKit
import Foundation

@MainActor
final class SpoofController: ObservableObject {
    @Published private(set) var running = false
    @Published private(set) var stopping = false
    @Published private(set) var error = false
    @Published private(set) var status = "Готово к подключению."
    private var worker: Process?

    init() {
        _ = NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification,
                                                    object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.stop() }
        }
    }

    func toggle() {
        if worker != nil { stop(); return }
        if Bundle.main.object(forInfoDictionaryKey: "NYLocationBluetoothOnly") as? Bool == true,
           Bundle.main.object(forInfoDictionaryKey: "NYLocationSignerURL") == nil,
           ProcessInfo.processInfo.environment["NYLOCATION_AUTH_HELPER"] == nil {
            let root = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/NYLocation/identity")
            let env = ProcessInfo.processInfo.environment
            let cert = env["ACCESSORY_MFI_CERT_FILE"] ?? root.appendingPathComponent("certificate.p7b").path
            let key = env["ACCESSORY_MFI_KEY_FILE"] ?? root.appendingPathComponent("identity.pk8").path
            guard [cert, key].allSatisfy(FileManager.default.isReadableFile(atPath:)) else {
                error = true
                status = "В этой предварительной версии ещё не подключён сервис авторизации. На новом Mac передача координат пока недоступна."
                return
            }
        }
        guard let script = Bundle.main.url(forResource: "session", withExtension: "py", subdirectory: "Bluetooth") else {
            error = true
            status = "В приложении отсутствует модуль геолокации."
            return
        }
        let child = Process()
        let pipe = Pipe()
        let configured = Bundle.main.object(forInfoDictionaryKey: "NYLocationDevicePython") as? String
        let interpreter = configured.flatMap { FileManager.default.isExecutableFile(atPath: $0) ? $0 : nil }
        child.executableURL = URL(fileURLWithPath: interpreter ?? "/usr/bin/python3")
        child.arguments = ["-B", "-u", script.path]
        child.standardInput = FileHandle.nullDevice
        child.standardOutput = pipe
        child.standardError = FileHandle.nullDevice
        error = false
        do {
            try child.run()
        } catch {
            self.error = true
            status = "Не удалось запустить модуль геолокации: " + error.localizedDescription
            return
        }
        worker = child
        running = true
        status = "Ищу iPhone…"
        Task {
            do {
                for try await line in pipe.fileHandleForReading.bytes.lines {
                    guard !stopping, worker === child, let data = line.data(using: .utf8),
                          let message = try? JSONDecoder().decode(Event.self, from: data) else { continue }
                    error = message.event == "error"
                    status = message.text
                }
            } catch {
                if !stopping { self.error = true; status = "Связь с модулем геолокации прервана." }
            }
            if child.isRunning {
                await Task.detached { child.waitUntilExit() }.value
            }
            guard worker === child else { return }
            if stopping { error = false; status = "Соединение закрыто. Проверьте обычную геопозицию iPhone." }
            else if !error { error = true; status = "Сеанс геолокации завершился." }
            worker = nil
            stopping = false
            running = false
        }
    }

    func stop() {
        guard let worker, worker.isRunning, !stopping else { return }
        stopping = true
        status = "Отключаюсь…"
        worker.terminate()
    }

    private struct Event: Decodable {
        let event: String
        let text: String
    }
}
