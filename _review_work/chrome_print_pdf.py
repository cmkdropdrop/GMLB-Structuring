from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
import websocket


WORKSPACE = Path(__file__).resolve().parent.parent
HTML = WORKSPACE / "_review_work" / "AGILE_Modelling_Fachpaper_reviewed_print.html"
PDF = WORKSPACE / "AGILE_Modelling_Fachpaper_reviewed.pdf"
PROFILE = WORKSPACE / "_review_work" / "chrome_pdf_profile"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class Cdp:
    def __init__(self, url: str) -> None:
        self.ws = websocket.create_connection(url, timeout=60, origin="http://localhost")
        self.next_id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        ident = self.next_id
        self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != ident:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method} failed: {message['error']}")
            return message.get("result", {})

    def close(self) -> None:
        self.ws.close()


def wait_for_debug_port(timeout: float = 30.0) -> int:
    port_file = PROFILE / "DevToolsActivePort"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_file.exists():
            lines = port_file.read_text(encoding="utf-8").splitlines()
            if lines:
                return int(lines[0])
        time.sleep(0.1)
    raise TimeoutError("Chrome did not publish a DevTools port.")


def main() -> None:
    if not HTML.exists():
        raise FileNotFoundError(HTML)
    if PDF.exists():
        raise FileExistsError(f"Refusing to overwrite {PDF}")
    if not CHROME.exists():
        raise FileNotFoundError(CHROME)

    if PROFILE.exists():
        shutil.rmtree(PROFILE)
    PROFILE.mkdir(parents=True)

    url = HTML.resolve().as_uri()
    command = [
        str(CHROME),
        "--headless=new",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-component-update",
        "--no-first-run",
        "--no-default-browser-check",
        "--allow-file-access-from-files",
        "--remote-allow-origins=*",
        "--remote-debugging-port=0",
        f"--user-data-dir={PROFILE}",
        "about:blank",
    ]

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    cdp: Cdp | None = None
    try:
        port = wait_for_debug_port()
        targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=10).json()
        page = next(target for target in targets if target.get("type") == "page")
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Page.navigate", {"url": url})

        deadline = time.time() + 60
        while time.time() < deadline:
            state = cdp.call("Runtime.evaluate", {"expression": "document.readyState"})
            if state.get("result", {}).get("value") == "complete":
                break
            time.sleep(0.2)
        else:
            raise TimeoutError("HTML did not finish loading.")

        cdp.call(
            "Runtime.evaluate",
            {
                "expression": "document.fonts.ready",
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        cdp.call("Emulation.setEmulatedMedia", {"media": "print"})

        footer = (
            '<div style="width:100%;font-family:Arial,sans-serif;font-size:8px;'
            'color:#52657a;text-align:center;">Seite '
            '<span class="pageNumber"></span> von <span class="totalPages"></span></div>'
        )
        result = cdp.call(
            "Page.printToPDF",
            {
                "landscape": False,
                "displayHeaderFooter": True,
                "printBackground": True,
                "scale": 1,
                "paperWidth": 8.2677165,
                "paperHeight": 11.6929134,
                "marginTop": 0.7086614,
                "marginBottom": 0.7480315,
                "marginLeft": 0.6299213,
                "marginRight": 0.6299213,
                "headerTemplate": "<div></div>",
                "footerTemplate": footer,
                "preferCSSPageSize": True,
                "generateDocumentOutline": True,
                "generateTaggedPDF": True,
                "transferMode": "ReturnAsBase64",
            },
        )
        PDF.write_bytes(base64.b64decode(result["data"]))
        print(f"PDF={PDF}")
        print(f"PDF_BYTES={PDF.stat().st_size}")
    finally:
        if cdp is not None:
            try:
                cdp.call("Browser.close")
            except Exception:
                pass
            cdp.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()

