"""Проверки формы в Firefox с локальным API и подменой fetch.

Временный сервер подменяет config.js в памяти, не меняя настройки
публикации и политику. Реальные запросы дважды отправляют уникальный
адрес @example.com для проверки дубликатов. Запускать только с API
разработки, где приём заявок включён явно, и отдельным Firefox.
"""

import argparse
import base64
import contextlib
import json
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ACCEPTED = "Заявка принята. Если вы ещё не в списке, мы добавим ваш email."


class Browser:
    """Клиент Firefox Marionette для браузерных проверок сайта."""

    def __init__(self, port):
        """Подключиться к Firefox и подготовить сеанс."""
        deadline = time.monotonic() + 20
        while True:
            try:
                self.socket = socket.create_connection(
                    ("127.0.0.1", port), timeout=15
                )
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        self.sequence = 0
        self.receive()
        self.command("WebDriver:NewSession", {"capabilities": {}})

    def receive(self):
        """Прочитать сообщение с префиксом его длины."""
        length = bytearray()
        while True:
            char = self.socket.recv(1)
            if char == b":":
                break
            if not char:
                raise ConnectionError("Firefox connection closed")
            length.extend(char)
        data = bytearray()
        while len(data) < int(length):
            chunk = self.socket.recv(int(length) - len(data))
            if not chunk:
                raise ConnectionError("Firefox connection closed")
            data.extend(chunk)
        return json.loads(data)

    def command(self, name, args=None):
        """Передать браузеру команду и вернуть её результат."""
        self.sequence += 1
        payload = json.dumps([0, self.sequence, name, args or {}]).encode()
        self.socket.sendall(str(len(payload)).encode() + b":" + payload)
        response = self.receive()
        if response[2]:
            raise RuntimeError(response[2])
        result = response[3]
        return (
            result.get("value", result) if isinstance(result, dict) else result
        )

    def script(self, script):
        """Выполнить JavaScript в выбранном контексте страницы."""
        # Переменные подмены живут в странице, а не Marionette.
        script = script.replace(
            "window.__qa", "(window.wrappedJSObject || window).__qa"
        )
        return self.command(
            "WebDriver:ExecuteScript",
            {
                "script": script,
                "args": [],
                "newSandbox": True,
                "sandbox": "default",
            },
        )

    def inject(self, script):
        """Вставить в страницу скрипт подмены сетевых ответов."""
        # Элемент script выполняет подмену fetch в контексте страницы.
        self.script(
            "const s=document.createElement('script');"
            f"s.textContent={json.dumps(script)};"
            "document.head.append(s);s.remove();"
        )

    def wait(self, expression, timeout=18):
        """Дождаться JS-условия или вывести состояние формы."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.script(f"return Boolean({expression});")
            if result:
                return
            time.sleep(0.05)
        state = self.script(
            "return {status:document.querySelector('[data-beta-status]')?"
            ".textContent,availability:document"
            ".querySelector('[data-beta-availability]')?.textContent};"
        )
        raise AssertionError(f"Timed out waiting for {expression}: {state}")

    def screenshot(self, path):
        """Сохранить снимок видимой области браузера."""
        encoded = self.command(
            "WebDriver:TakeScreenshot",
            {"full": False, "highlights": [], "scroll": False},
        )
        Path(path).write_bytes(base64.b64decode(encoded))

    def close(self):
        """Закрыть сокет даже при ошибке завершения сеанса."""
        # Сбой завершения сеанса не мешает закрытию сокета.
        with contextlib.suppress(Exception):
            self.command("WebDriver:DeleteSession")
        self.socket.close()


def handler_for(backend_url):
    """Создать HTTP-обработчик с тестовой конфигурацией адреса API."""

    class Handler(SimpleHTTPRequestHandler):
        """Раздавать файлы сайта и локальные настройки приёма заявок."""

        def __init__(self, *args, **kwargs):
            """Настроить раздачу статических файлов из каталога dist."""
            super().__init__(*args, directory=str(DIST), **kwargs)

        def log_message(self, *_args):
            """Отключить журнал HTTP-запросов на время QA."""
            pass

        def end_headers(self):
            """Запретить кеширование тестовых ресурсов."""
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self):
            """Подменить конфиг и раздать ресурсы сайта."""
            path = urlsplit(self.path).path
            if path in ("/configured/config.js", "/closed/config.js"):
                configured = path.startswith("/configured/")
                config = {
                    "apiBaseUrl": backend_url if configured else None,
                    "privacyPolicyUrl": "/privacy-fixture"
                    if configured
                    else None,
                }
                payload = f"window.ASTRO_CONFIG={json.dumps(config)};".encode()
                self.send_response(200)
                self.send_header(
                    "Content-Type", "application/javascript; charset=utf-8"
                )
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if path == "/privacy-fixture":
                payload = (
                    b"<!doctype html><title>Local QA"
                    b" fixture</title><p>Privacy URL fixture for local"
                    b" browser checks.</p>"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            for prefix in ("/configured/", "/closed/"):
                if self.path.startswith(prefix):
                    self.path = "/" + self.path[len(prefix) :]
                    break
            super().do_GET()

    return Handler


def run_cases(browser, origin, email, skip_live=False):
    """Проверить форму, ответы API, ошибки и мобильный диалог."""
    results = []

    def record(name, **details):
        """Записать успешный сценарий и вывести его детали в JSON."""
        result = {"case": name, "passed": True, **details}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    def navigate(mode="configured"):
        """Открыть страницу с выбранным режимом приёма заявок."""
        browser.command(
            "WebDriver:Navigate", {"url": f"{origin}/{mode}/index.html"}
        )
        browser.wait("document.querySelector('[data-beta-form]')")

    def open_form():
        """Открыть диалог и сохранить кнопку возврата фокуса."""
        browser.script(
            "const b=document.querySelector('[data-demo-open]');b.focus();b"
            ".click();"
        )
        browser.wait("document.querySelector('dialog').open")

    def fill_form():
        """Заполнить email и согласие для тестовой заявки."""
        browser.script(
            f"document.querySelector('[name=email]').value={json.dumps(email)};"
            "document.querySelector('[name=consent]').checked=true;"
        )

    def submit():
        """Отправить форму штатным браузерным способом."""
        browser.script(
            "document.querySelector('[data-beta-form]').requestSubmit();"
        )

    def stub_response(status, body, headers=None):
        """Подменить ответ fetch и считать обращения."""
        browser.inject(
            "window.__qaCalls=0;window.fetch=()=>{window.__qaCalls++;"
            "return Promise.resolve(new Response("
            f"{json.dumps(json.dumps(body))},"
            f"{{status:{status},headers:{
                json.dumps(headers or {('Content-Type'): ('application/json')})
            }}}));}};"
        )

    browser.command("WebDriver:SetWindowRect", {"width": 1440, "height": 1000})
    navigate("closed")
    open_form()
    browser.inject(
        "window.__qaCalls=0;window.fetch=()=>{window.__qaCalls++;"
        "throw Error('closed form sent a request');};"
    )
    browser.script(
        "document.querySelector('[data-beta-form]')"
        ".dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));"
    )
    assert browser.script(
        "return [...document"
        ".querySelectorAll('[data-beta-field], [data-beta-submit]')]"
        ".every(e=>e.disabled) && !document"
        ".querySelector('[data-beta-availability]').hidden && window"
        ".__qaCalls===0;"
    )
    record("unconfigured_form_closed")

    if not skip_live:
        for case in ("live_new_signup", "live_duplicate_signup"):
            navigate()
            assert browser.script(
                "return !document.querySelector('[name=email]').disabled "
                "&& document.querySelector('[data-beta-policy]').href"
                ".endsWith('/privacy-fixture');"
            )
            open_form()
            fill_form()
            browser.inject(
                "const originalFetch=window.fetch;window.__qaCalls=0;window"
                ".fetch=(...args)=>{window.__qaCalls++;"
                "return originalFetch(...args).then(r=>{window"
                ".__qaResponseStatus=r.status;return r;});};"
            )
            submit()
            browser.wait(
                "!document.querySelector('[data-beta-success]').hidden"
            )
            state = browser.script(
                "return {status:window.__qaResponseStatus,calls:window"
                ".__qaCalls,accepted:document"
                ".querySelector('[data-beta-success-text]').textContent,"
                "formHidden:document.querySelector('[data-beta-form]').hidden}"
                ";"
            )
            assert state == {
                "status": 202,
                "calls": 1,
                "accepted": ACCEPTED,
                "formHidden": True,
            }, state
            record(case, email=email, **state)

    navigate()
    open_form()
    submit()
    assert browser.script(
        "return document.querySelector('[name=email]')"
        ".getAttribute('aria-invalid')==='true' && document"
        ".querySelector('[name=consent]')"
        ".getAttribute('aria-invalid')==='true' && document"
        ".activeElement===document.querySelector('[name=email]');"
    )
    record("required_email_and_consent")

    navigate()
    open_form()
    fill_form()
    stub_response(400, {"email": ["Этот email нельзя использовать в тесте."]})
    submit()
    browser.wait(
        "document.querySelector('[name=email]')"
        ".getAttribute('aria-invalid')==='true'"
    )
    assert browser.script(
        "return document.querySelector('[name=email]').value==="
        f"{json.dumps(email)} && "
        "!document.querySelector('[data-beta-submit]').disabled && "
        "document.activeElement===document.querySelector('[name=email]') && "
        "window.__qaCalls===1;"
    )
    record("server_400_preserves_email_and_focus")

    navigate()
    open_form()
    fill_form()
    stub_response(
        429,
        {"detail": "Throttle fixture"},
        {"Content-Type": "application/json", "Retry-After": "3"},
    )
    submit()
    browser.wait(
        "document.querySelector('[data-beta-status]').textContent"
        ".includes('3 с.')"
    )
    assert browser.script(
        "return document.querySelector('[name=email]').value==="
        f"{json.dumps(email)} && "
        "!document.querySelector('[data-beta-submit]').disabled;"
    )
    record("rate_limit_preserves_email")

    navigate()
    open_form()
    fill_form()
    browser.inject(
        "window.fetch=()=>Promise.reject(new TypeError('Network fixture'));"
    )
    submit()
    browser.wait(
        "document.querySelector('[data-beta-status]').dataset.state==='error'"
    )
    assert browser.script(
        "return document.querySelector('[name=email]').value==="
        f"{json.dumps(email)} && "
        "!document.querySelector('[data-beta-submit]').disabled;"
    )
    record("network_failure_preserves_email")

    navigate()
    open_form()
    fill_form()
    browser.inject(
        "window.__qaCalls=0;window.fetch=()=>{window.__qaCalls++;"
        "return new Promise(resolve=>window.__qaResolve=resolve);};"
    )
    browser.script(
        "const f=document.querySelector('[data-beta-form]');for(let i=0;i<2;"
        "i++)f.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}"
        "));"
    )
    assert browser.script(
        "return window.__qaCalls===1 && document"
        ".querySelector('[data-beta-submit]').disabled && document"
        ".querySelector('[data-beta-form]')"
        ".getAttribute('aria-busy')==='true';"
    )
    browser.inject(
        f"window.__qaResolve(new Response({
            json.dumps(json.dumps({('detail'): ACCEPTED}))
        },{{status:202,headers:{{'Content-Type':'application/json'}}}}));"
    )
    browser.wait("!document.querySelector('[data-beta-success]').hidden")
    assert browser.script("return window.__qaCalls===1;")
    record("pending_submit_guard")

    navigate()
    open_form()
    fill_form()
    browser.inject(
        "const timer=window.setTimeout;window.setTimeout=(fn,delay,"
        "...args)=>timer(fn,delay===15000?30:delay,...args);window"
        ".fetch=(_url,options)=>new Promise((_resolve,reject)=>options.signal"
        ".addEventListener('abort',"
        "()=>reject(new DOMException('Timeout fixture','AbortError'))));"
    )
    submit()
    browser.wait(
        "document.querySelector('[data-beta-status]').textContent"
        ".includes('вовремя')"
    )
    assert browser.script(
        "return document.querySelector('[name=email]').value==="
        f"{json.dumps(email)} && "
        "!document.querySelector('[data-beta-submit]').disabled;"
    )
    record("timeout_preserves_email")

    navigate()
    browser.command("WebDriver:SetWindowRect", {"width": 500, "height": 1100})
    browser.script(
        "const f=document.createElement('iframe');f.id='qa-beta-mobile';f"
        ".src=location.href;f.style='position:fixed;inset:0;width:390px;"
        "height:844px;border:0;z-index:9999;background:#0a051c';document.body"
        ".replaceChildren(f);"
    )
    frame = browser.command(
        "WebDriver:FindElement",
        {"using": "css selector", "value": "#qa-beta-mobile"},
    )
    browser.command("WebDriver:SwitchToFrame", {"id": frame})
    browser.wait(
        "document.querySelector('[data-beta-form]') && !document"
        ".querySelector('[name=email]').disabled"
    )
    open_form()
    layout = browser.script(
        "const d=document.querySelector('dialog').getBoundingClientRect();"
        "const e=document.querySelector('[name=email]')"
        ".getBoundingClientRect();const b=document"
        ".querySelector('[data-beta-submit]').getBoundingClientRect();return {"
        "width:innerWidth,height:innerHeight,overflow:document.documentElement"
        ".scrollWidth>innerWidth,dialogLeft:d.left,dialogRight:d.right,"
        "dialogTop:d.top,dialogBottom:d.bottom,emailLeft:e.left,emailRight:e"
        ".right,submitRight:b.right};"
    )
    assert layout["width"] == 390 and layout["height"] == 844, layout
    assert not layout["overflow"], layout
    assert 0 <= layout["dialogLeft"] < layout["dialogRight"] <= 390, layout
    assert 0 <= layout["dialogTop"] < layout["dialogBottom"] <= 844, layout
    assert (
        layout["emailLeft"] >= layout["dialogLeft"]
        and layout["emailRight"] <= layout["dialogRight"]
    ), layout
    assert layout["submitRight"] <= layout["dialogRight"], layout
    browser.screenshot("/tmp/astro-beta-mobile.png")
    browser.script("document.querySelector('[data-demo-close]').click();")
    assert browser.script(
        "return !document.querySelector('dialog').open && document"
        ".activeElement===document.querySelector('[data-demo-open]');"
    )
    record("mobile_390_dialog_layout_and_close_focus", **layout)
    return results


def main():
    """Запустить временный сервер и проверки в отдельном Firefox."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default="http://127.0.0.1:18000")
    parser.add_argument("--frontend-port", type=int, default=18001)
    parser.add_argument("--marionette-port", type=int, default=2828)
    parser.add_argument(
        "--email", default=f"qa-browser-{time.time_ns()}@example.com"
    )
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args()
    origin = f"http://127.0.0.1:{args.frontend_port}"
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.frontend_port), handler_for(args.backend_url)
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    browser = None
    # Firefox запускается отдельно: Snap видит свой /tmp и не откроет
    # профиль из TemporaryDirectory, созданный Python вне Snap.
    try:
        browser = Browser(args.marionette_port)
        results = run_cases(browser, origin, args.email, args.skip_live)
        print(
            json.dumps(
                {
                    "passed": len(results),
                    "live_email": None if args.skip_live else args.email,
                    "screenshot": "/tmp/astro-beta-mobile.png",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        if browser:
            browser.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
