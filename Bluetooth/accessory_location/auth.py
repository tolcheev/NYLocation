"""Local helper and publisher-configured HTTPS signing providers."""

import asyncio
import base64
import json
from urllib.parse import urlsplit

from .wire import Message, ProtocolError, parameter


class AuthenticationProvider:
    """JSON-lines subprocess: certificate or sign; private keys stay in the helper."""

    def __init__(self, executable):
        self.executable = executable
        self.process = None

    async def request(self, operation, **fields):
        if self.process is None:
            self.process = await asyncio.create_subprocess_exec(
                self.executable,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=128 * 1024,
            )
        self.process.stdin.write(json.dumps({"op": operation, **fields}).encode() + b"\n")
        await self.process.stdin.drain()
        response = await asyncio.wait_for(self.process.stdout.readline(), 40)
        if not response:
            raise RuntimeError("Authentication provider exited without a response")
        result = json.loads(response)
        if result.get("error"):
            raise RuntimeError(f"Authentication provider: {result['error']}")
        return result

    async def certificate(self):
        result = await self.request("certificate")
        certificate = base64.b64decode(result["certificate"], validate=True)
        if not certificate:
            raise ProtocolError("Empty authentication certificate")
        body = parameter(0, certificate)
        if result.get("type") == "baa":
            intermediate = base64.b64decode(result["intermediate"], validate=True)
            if not intermediate:
                raise ProtocolError("Empty BAA intermediate certificate")
            body += parameter(1, b"\x01") + parameter(2, intermediate)
        elif result.get("type") != "mfi":
            raise ProtocolError("Provider type must be baa or mfi")
        return Message(0xAA01, body)

    async def sign(self, challenge):
        if not 1 <= len(challenge) <= 4096:
            raise ProtocolError("Invalid authentication challenge size")
        result = await self.request("sign", challenge=base64.b64encode(challenge).decode("ascii"))
        signature = base64.b64decode(result["signature"], validate=True)
        if not 1 <= len(signature) <= 4096:
            raise ProtocolError("Invalid authentication signature size")
        return Message(0xAA03, parameter(0, signature))

    async def close(self):
        if self.process is not None:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                self.process.terminate()
                await self.process.wait()


class ReleaseSigner(AuthenticationProvider):
    """The publisher owns the endpoint; private keys never reach the Mac."""

    def __init__(self, url):
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username is not None or parts.password is not None or parts.query or parts.fragment:
            raise ValueError("Expected a public HTTPS signing endpoint without credentials")
        self.url = url

    async def request(self, operation, **fields):
        # System curl uses the Mac trust store. Disable user curl config and
        # redirects. The only outbound data is the operation and iPhone nonce.
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/curl", "-q", "--proto", "=https", "--silent", "--fail",
            "--max-time", "12", "--max-filesize", "65536",
            "--header", "Content-Type: application/json", "--data-binary", "@-",
            "--url", self.url, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            data, _ = await proc.communicate(json.dumps(dict(op=operation, **fields)).encode())
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
        if proc.returncode or not data or len(data) > 65536:
            raise ValueError("Сервис подключения iPhone недоступен.")
        result = json.loads(data)
        if not isinstance(result, dict) or result.get("error"):
            raise ValueError("Сервис не подтвердил подключение iPhone.")
        return result
