import AppKit
import Foundation

@MainActor
final class SpoofController: ObservableObject {
    @Published private(set) var running = false
    @Published private(set) var stopping = false
    @Published private(set) var error = false
    @Published private(set) var status = "Готово к подключению."
    @Published var mode = "usb"
    private var worker: Process?

    init() {
        _ = NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification,
                                                    object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.stop() }
        }
    }

    func toggle() {
        if worker != nil { stop(); return }
        guard let script = Bundle.main.url(forResource: "session", withExtension: "py", subdirectory: "Bluetooth") else {
            error = true
            status = "В приложении отсутствует модуль геолокации."
            return
        }
        let child = Process()
        let pipe = Pipe()
        #if arch(arm64)
        let arch = "arm64"
        #else
        let arch = "x86_64"
        #endif
        guard let python = Bundle.main.resourceURL?.appendingPathComponent("Runtime/\(arch)/bin/python3"),
              FileManager.default.isExecutableFile(atPath: python.path) else {
            error = true
            status = "В архиве отсутствует модуль подключения. Распакуйте приложение заново."
            return
        }
        child.executableURL = python
        child.arguments = ["-E", "-s", "-B", "-u", script.path, mode]
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
            if stopping {
                error = child.terminationStatus != 0
                status = error ? "Связь прервана. Проверьте геопозицию на iPhone." : "Сеанс завершён."
            }
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
