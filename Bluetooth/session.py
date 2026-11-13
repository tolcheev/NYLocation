"""One-button Bluetooth GPS sender. Python 3.9+, standard library only."""
import asyncio
import json
import os
import plistlib
from pathlib import Path
import signal
import subprocess
import sys

from accessory_location.auth import AuthenticationProvider, ReleaseSigner
from accessory_location.link import Link
from accessory_location.profile import identity, location_message, location_sentences
from accessory_location.transport import BluetoothStream, controller_address
from accessory_location.wire import Message, parameter, parameters

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parent / 'Helpers' / 'bluetooth-bridge'
IDENTITY = Path.home() / 'Library/Application Support/NYLocation/identity'


def release_signer_url():
    plist = HERE.parent.parent / 'Info.plist'
    if plist.is_file():
        with plist.open('rb') as file:
            return plistlib.load(file).get('NYLocationSignerURL')


def report(event, text=''):
    print(json.dumps(dict(event=event, text=text), ensure_ascii=False), flush=True)


class LocalIdentity:
    async def certificate(self):
        self.key = Path(os.environ.get('ACCESSORY_MFI_KEY_FILE') or IDENTITY / 'identity.pk8')
        cert = Path(os.environ.get('ACCESSORY_MFI_CERT_FILE') or IDENTITY / 'certificate.p7b')
        if not cert.is_file() or not self.key.is_file():
            raise ValueError('iPhone запросил сертификат GPS-аксессуара. Для подключения нужен настроенный MFi-сертификат и его ключ.')
        return Message(0xAA01, parameter(0, cert.read_bytes()))

    async def sign(self, challenge):
        if len(challenge) != 32:
            raise ValueError('iPhone прислал неизвестный формат запроса подписи.')
        result = subprocess.run(['/usr/bin/openssl', 'pkeyutl', '-sign', '-keyform', 'DER',
                                 '-inkey', str(self.key)], input=challenge, capture_output=True, timeout=5)
        if result.returncode:
            raise ValueError('Не удалось подписать запрос ключом аксессуара.')
        signature = result.stdout
        # OpenSSL returns a DER sequence of two P-256 integers; iAP2 expects r || s.
        if len(signature) < 8 or signature[:1] != b'\x30' or signature[1] != len(signature)-2:
            raise ValueError('Неверный формат подписи сертификата.')
        offset = 2
        parts = []
        for _ in range(2):
            if offset+2 > len(signature) or signature[offset] != 2:
                raise ValueError('Неверная подпись сертификата.')
            end = offset+2+signature[offset+1]
            raw = signature[offset+2:end].lstrip(b'\x00')
            if end > len(signature) or len(raw) > 32 or not raw:
                raise ValueError('Требуется ключ P-256.')
            parts.append(raw.rjust(32,b'\x00'))
            offset = end
        if offset != len(signature):
            raise ValueError('Неверная длина подписи.')
        return Message(0xAA03, parameter(0,b''.join(parts)))


async def control(link, address, signer):
    identified = authenticated = False
    intervals = {}
    due = {}
    fallback_due = 0
    subscribed_once = False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 45
    announced = False
    while True:
        if not (authenticated and identified) and loop.time() > deadline:
            raise ValueError('iPhone не подтвердил подключение GPS-аксессуара.')
        try:
            msg = await link.receive(.25)
        except asyncio.TimeoutError:
            msg = None
        if msg:
            fields = parameters(msg.body)
            if msg.identifier == 0x1D00:
                await link.send(identity('bluetooth', address))
            elif msg.identifier == 0x1D02:
                identified = True
            elif msg.identifier == 0x1D03:
                raise ValueError('iPhone отклонил профиль GPS-аксессуара.')
            elif msg.identifier == 0xAA00:
                await link.send(await signer.certificate())
            elif msg.identifier == 0xAA02:
                challenges = [v for k,v in fields if k == 0]
                if len(challenges) != 1:
                    raise ValueError('Неверный запрос авторизации.')
                await link.send(await signer.sign(challenges[0]))
            elif msg.identifier == 0xAA04:
                raise ValueError('iPhone отклонил сертификат аксессуара.')
            elif msg.identifier == 0xAA05:
                authenticated = True
                report('waiting', 'Bluetooth подключён. Проверяю передачу координат…')
            elif msg.identifier == 0xFFFA:
                subscribed_once = True
                intervals = {k:1.0 for k,v in fields if k in (1,2) and not v}
                for k,v in fields:
                    if k-0x8000 in intervals and len(v)==4:
                        intervals[k-0x8000] = max(1,int.from_bytes(v,'big')/1000)
                due = dict.fromkeys(intervals,0)
            elif msg.identifier == 0xFFFC:
                intervals.clear()
                announced = False
                report('waiting','iPhone завершил запрос координат. Соединение остаётся активным.')
        now = loop.time()
        ready = [k for k in intervals if due[k] <= now]
        fallback = identified and authenticated and not subscribed_once and now >= fallback_due
        if identified and authenticated and (ready or fallback):
            sentences = location_sentences(40.7580,-73.9855)
            # Send the first fix after authentication, then follow subscription intervals.
            await link.send(location_message([sentences[k] for k in ready] if ready else [sentences[2]]))
            if not announced:
                report('sending','Передаю координаты Таймс-сквер. Проверьте нужную функцию на iPhone.')
                announced = True
            for k in ready:
                due[k] = now + intervals[k]
            if fallback:
                fallback_due = now + 5


async def bluetooth_session():
    listing = await asyncio.create_subprocess_exec(str(BRIDGE),'--list',stdout=asyncio.subprocess.PIPE)
    try:
        output, _ = await asyncio.wait_for(listing.communicate(), 8)
    finally:
        if listing.returncode is None:
            listing.kill()
            await listing.wait()
    if listing.returncode:
        raise ValueError('Не удалось прочитать список Bluetooth-устройств.')
    phones = [d for d in json.loads(output) if d['paired'] and (d['phone'] or 'iphone' in d['name'].lower())]
    phones = list({d['address'].lower().replace(':', '-'): d for d in phones}.values())
    if len(phones) != 1:
        raise ValueError('Сопрягите iPhone с Mac в настройках Bluetooth.' if not phones else 'Найдено несколько телефонов. Нужен один сопряжённый iPhone.')
    phone = phones[0]
    report('connecting','Подключаюсь к '+phone['name']+' по Bluetooth…')
    address = await controller_address(str(BRIDGE))
    helper = os.environ.get('NYLOCATION_AUTH_HELPER')
    url = release_signer_url()
    signer = AuthenticationProvider(helper) if helper else ReleaseSigner(url) if url else LocalIdentity()
    bridge = str(BRIDGE)
    stream = await BluetoothStream.open(bridge, phone['address'])
    try:
        try:
            await stream.detect()
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            await stream.close()
            stream = await BluetoothStream.open(bridge, phone['address'], listen=True)
            status = await asyncio.wait_for(stream.process.stderr.readline(), 8)
            if status.strip() != b'LISTENING':
                raise ValueError('macOS не удалось открыть входящий канал Bluetooth.')
            report('waiting', 'На iPhone в настройках Bluetooth нажмите имя этого Mac. Жду 90 секунд.')
            try:
                await stream.detect(timeout=95)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
                raise ValueError('iPhone не открыл канал GPS-аксессуара за 90 секунд.') from None
    except BaseException:
        await stream.close()
        raise
    link = Link(stream)
    try:
        await link.handshake()
        await control(link,address,signer)
    finally:
        await link.close()
        if helper:
            await signer.close()


async def session(mode):
    if mode == 'bluetooth':
        cert = Path(os.environ.get('ACCESSORY_MFI_CERT_FILE') or IDENTITY / 'certificate.p7b')
        key = Path(os.environ.get('ACCESSORY_MFI_KEY_FILE') or IDENTITY / 'identity.pk8')
        if not (release_signer_url() or os.environ.get('NYLOCATION_AUTH_HELPER') or (cert.is_file() and key.is_file())):
            raise ValueError('Bluetooth на этом Mac ещё не настроен. Выберите USB и подключите iPhone кабелем.')
        await bluetooth_session()
        return

    from pymobiledevice3.usbmux import list_devices
    devices = [d for d in await list_devices() if d.is_usb]
    if not devices:
        raise ValueError('iPhone не найден по USB. Подключите кабель для передачи данных и разблокируйте телефон.')
    if len(devices) != 1:
        raise ValueError('Подключите по кабелю только один iPhone.')
    from contextlib import AsyncExitStack
    from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel
    from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
    from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.amfi import AmfiService
    from pymobiledevice3.exceptions import AlreadyMountedError, PairingError, NotTrustedError
    from pymobiledevice3.services.mobile_image_mounter import auto_mount
    from contextlib import suppress

    serial = devices[0].serial
    report('connecting', 'Разблокируйте iPhone и подтвердите «Доверять», если появится запрос.')
    try:
        lockdown = await create_using_usbmux(serial=serial, connection_type='USB', pair_timeout=90)
    except (PairingError, NotTrustedError, TimeoutError) as exc:
        raise ValueError('Не удалось получить доверие iPhone. Разблокируйте телефон и подтвердите подключение.') from exc
    async with lockdown:
        if int(lockdown.product_version.split('.')[0]) < 17:
            raise ValueError('Для этого режима нужен iPhone с iOS 17 или новее.')
        if not await lockdown.get_developer_mode_status():
            with suppress(Exception):
                await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
            raise ValueError('Включите на iPhone режим разработчика в настройках конфиденциальности, подтвердите перезагрузку и повторите подключение.')

    report('connecting', 'Подключаю iPhone по USB…')
    async with AsyncExitStack() as stack:
        async def tunnel():
            return await asyncio.wait_for(stack.enter_async_context(NativeRemotedTunnel(serial=serial)), 60)

        rsd = await tunnel()
        if DvtProvider.RSD_SERVICE_NAME not in rsd.peer_info['Services']:
            report('connecting', 'Готовлю iPhone к первой передаче. Оставьте кабель подключённым. Может потребоваться интернет.')
            with suppress(AlreadyMountedError):
                await asyncio.wait_for(auto_mount(rsd), 600)
            await stack.aclose()
            rsd = await tunnel()
        provider = await asyncio.wait_for(stack.enter_async_context(DvtProvider(rsd)), 30)
        location = await asyncio.wait_for(stack.enter_async_context(LocationSimulation(provider)), 15)
        try:
            await asyncio.wait_for(location.set(40.7580, -73.9855), 12)
            report('sending', 'iPhone принял координаты Таймс-сквер. Оставьте кабель подключённым до окончания настройки.')
            await provider.dtx.wait_disconnected()
            raise ConnectionError('Связь с iPhone прервана.')
        except asyncio.CancelledError:
            await asyncio.wait_for(location.clear(), 5)
            raise


async def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else 'usb'
    if mode not in ('usb', 'bluetooth'):
        raise ValueError('Unknown transport')
    task = asyncio.create_task(session(mode))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):
        loop.add_signal_handler(sig,task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        report('error', str(exc) or f'Не удалось завершить подключение ({type(exc).__name__}). Разблокируйте iPhone и повторите попытку.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
