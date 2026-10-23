"""Small browser smoke check using Firefox's bundled Marionette protocol.

Start an isolated Firefox with --headless --marionette before running.
No third-party dependencies. Screenshots are written to /tmp.
"""
import base64
import json
import socket
import time
from pathlib import Path


class Browser:
    def __init__(self):
        self.socket = socket.create_connection(('127.0.0.1', 2828), timeout=15)
        self.sequence = 0
        self.receive()

    def receive(self):
        length = bytearray()
        while True:
            char = self.socket.recv(1)
            if char == b':':
                break
            if not char:
                raise ConnectionError('Firefox connection closed')
            length.extend(char)
        data = bytearray()
        while len(data) < int(length):
            data.extend(self.socket.recv(int(length) - len(data)))
        return json.loads(data)

    def command(self, name, args=None):
        self.sequence += 1
        data = json.dumps([0, self.sequence, name, args or {}]).encode()
        self.socket.sendall(str(len(data)).encode() + b':' + data)
        response = self.receive()
        if response[2]:
            raise RuntimeError(response[2])
        result = response[3]
        return result.get('value', result) if isinstance(result, dict) else result

    def script(self, script):
        return self.command('WebDriver:ExecuteScript', {'script': script, 'args': [], 'newSandbox': True, 'sandbox': 'default'})

    def screenshot(self, path):
        data = self.command('WebDriver:TakeScreenshot', {'full': False, 'highlights': [], 'scroll': False})
        Path(path).write_bytes(base64.b64decode(data))


browser = Browser()
try:
    browser.command('WebDriver:DeleteSession')
except RuntimeError:
    pass
browser.command('WebDriver:NewSession', {'capabilities': {}})
url = (Path(__file__).resolve().parents[1] / 'dist/index.html').as_uri()
browser.command('WebDriver:Navigate', {'url': url})
time.sleep(0.5)
browser.command('WebDriver:SetWindowRect', {'width': 1440, 'height': 1000})
time.sleep(0.2)
print('Desktop:', browser.script('return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,images:[...document.images].every(i=>i.complete&&i.naturalWidth>0)};'))
browser.screenshot('/tmp/astro-desktop.png')
for phase in (0.35, 0.60, 0.90):
    browser.script(f'const s=document.querySelector("[data-story]");scrollTo({{top:(s.offsetHeight-document.querySelector(".story__sticky").getBoundingClientRect().height)*{phase},behavior:"instant"}});')
    time.sleep(0.2)
    print('Transition', phase, browser.script('const s=document.querySelector("[data-story]");return {scene:s.dataset.scene,hero:getComputedStyle(document.querySelector(".hero-figure")).opacity,title:getComputedStyle(document.querySelector(".hero-title")).opacity,privacy:getComputedStyle(document.querySelector(".chapter--privacy")).opacity};'))
    browser.screenshot(f'/tmp/astro-transition-{int(phase * 100)}.png')
browser.script('scrollTo({top:0,behavior:"instant"});')
time.sleep(0.2)
assert browser.script('return document.querySelector("[data-story]").dataset.scene === "intro" && !document.querySelector("[data-chapter=intro]").inert;'), 'Reverse transition did not restore intro'
print('Signal:', browser.script('document.querySelector("[data-signal]").click();return {pressed:document.querySelector("[data-signal]").getAttribute("aria-pressed"),title:document.querySelector("[data-cue-title]").textContent};'))
print('Dialog:', browser.script('document.querySelector("[data-demo-open]").click();const open=document.querySelector("dialog").open;document.querySelector("[data-demo-close]").click();return {open,closed:!document.querySelector("dialog").open};'))
browser.script('const s=document.querySelector("[data-story]");scrollTo({top:(s.offsetHeight-document.querySelector(".story__sticky").getBoundingClientRect().height)*.9,behavior:"instant"});')
time.sleep(0.2)
print('Privacy:', browser.script('return {scene:document.querySelector("[data-story]").dataset.scene,introInert:document.querySelector("[data-chapter=intro]").inert,privacyInert:document.querySelector("[data-chapter=privacy]").inert};'))
browser.screenshot('/tmp/astro-privacy.png')
browser.script('document.querySelector("[data-message-delete]").click();')
time.sleep(0.55)
print('Message:', browser.script('const message=document.querySelector("[data-message]");const hidden=message.hidden;document.querySelector("[data-message-delete]").click();return {hidden,restored:!message.hidden};'))
browser.command('WebDriver:SetWindowRect', {'width': 390, 'height': 844})
browser.command('WebDriver:SetWindowRect', {'width': 500, 'height': 1100})
browser.script('scrollTo({top:0,behavior:"instant"});const f=document.createElement("iframe");f.id="qa-mobile-frame";f.src=location.href;f.style="position:fixed;inset:0;width:390px;height:844px;border:0;z-index:9999;background:#0a051c";document.body.replaceChildren(f);')
time.sleep(0.3)
mobile_frame = browser.command('WebDriver:FindElement', {'using': 'css selector', 'value': '#qa-mobile-frame'})
browser.command('WebDriver:SwitchToFrame', {'id': mobile_frame})
time.sleep(0.3)
print('Mobile:', browser.script('return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth};'))
browser.screenshot('/tmp/astro-mobile.png')
print('Mobile menu:', browser.script('document.querySelector("[data-nav-toggle]").click();const open=document.body.classList.contains("is-menu-open");document.querySelector("[data-nav-toggle]").click();return {open,closed:!document.body.classList.contains("is-menu-open")};'))
browser.script('const s=document.querySelector("[data-story]");scrollTo({top:(s.offsetHeight-document.querySelector(".story__sticky").getBoundingClientRect().height)*.9,behavior:"instant"});')
time.sleep(0.3)
print('Mobile controls:', browser.script('const b=document.querySelector("[data-message-delete]").getBoundingClientRect();const f=document.querySelector(".scene-footer").getBoundingClientRect();return {buttonTop:b.top,buttonBottom:b.bottom,footerTop:f.top,height:innerHeight,overlap:b.bottom>f.top};'))
browser.screenshot('/tmp/astro-mobile-privacy.png')
for width, height in ((760, 700), (650, 800)):
    browser.command('WebDriver:SwitchToFrame', {})
    browser.script(f'const f=document.querySelector("iframe");f.style.width="{width}px";f.style.height="{height}px";')
    browser.command('WebDriver:SwitchToFrame', {'id': mobile_frame})
    browser.script('scrollTo({top:0,behavior:"instant"});')
    time.sleep(0.2)
    layout = browser.script('const t=document.querySelector(".hero-title").getBoundingClientRect();const c=document.querySelector(".chapter--intro .chapter__copy").getBoundingClientRect();return {width:innerWidth,height:innerHeight,titleBottom:t.bottom,copyTop:c.top,overflow:document.documentElement.scrollWidth>innerWidth};')
    print('Wide mobile:', layout)
    assert layout['copyTop'] >= layout['titleBottom'], 'Headline overlaps description'
    assert not layout['overflow'], 'Wide mobile overflows horizontally'
    browser.script('const s=document.querySelector("[data-story]");scrollTo({top:(s.offsetHeight-document.querySelector(".story__sticky").getBoundingClientRect().height)*.9,behavior:"instant"});')
    time.sleep(0.2)
    controls = browser.script('return {bottom:document.querySelector(".demo-controls").getBoundingClientRect().bottom,footerTop:document.querySelector(".scene-footer").getBoundingClientRect().top};')
    print('Wide mobile controls:', controls)
    assert controls['bottom'] <= controls['footerTop'], 'Demo controls overlap progress footer'
browser.command('WebDriver:SetWindowRect', {'width': 360, 'height': 640})
browser.command('WebDriver:SwitchToFrame', {})
browser.script('const f=document.querySelector("iframe");f.style.width="360px";f.style.height="640px";')
browser.command('WebDriver:SwitchToFrame', {'id': mobile_frame})
browser.script('scrollTo({top:0,behavior:"instant"});')
time.sleep(0.2)
print('Short screen:', browser.script('return {width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth,sticky:getComputedStyle(document.querySelector(".story__sticky")).position,bothAccessible:[...document.querySelectorAll("[data-chapter]")].every(e=>!e.inert)};'))
browser.command('WebDriver:DeleteSession')
browser.socket.close()
