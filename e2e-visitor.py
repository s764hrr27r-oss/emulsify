"""e2e-visitor.py - the sign-in, the alien sky, the sounds (b223).

Headless Chromium with the fake camera and the stub lab. Checks: a wrong password
is refused; initials typed as "Rachel G" become RG; the right password turns the
sky alien and it survives a reload; a frame still develops under it; the sounds
render offline to WAV (so they can be heard without a phone); a plain sign-in
has no sky; sign-out clears everything. Writes visitor-*.png and sfx-*.wav."""
import asyncio, io, struct, wave
from playwright.async_api import async_playwright
STUB = open("/home/claude/emulsify/e2e-stub.js").read()
URL = "http://127.0.0.1:8765/index.html"
OUT = "/home/claude/emulsify/"
SOUNDS = {"alien": {"shutter": 0.4, "lens": 0.6, "develop": 2.2, "print": 1.0, "welcome": 3.2, "nope": 0.8, "bye": 0.9},
          "hive": {"shutter": 0.6, "lens": 0.5, "develop": 2.2, "print": 2.2, "welcome": 3.2, "nope": 0.6, "bye": 1.0}}
RENDER = """async ([which, name, secs]) => { const c = new OfflineAudioContext(1, Math.ceil(44100 * secs), 44100); self.__sfx(which, name, c);
  const b = await c.startRendering(); return Array.from(b.getChannelData(0)); }"""
async def sign(pg, ini, pw, via="pill"):
    if via == "pill": await pg.click("#who")
    else: await pg.click("#menu"); await pg.click("#psign")
    if ini is not None: await pg.fill("#si-ini", ini)
    await pg.fill("#si-pw", pw); await pg.click("#si-go"); await asyncio.sleep(0.4)
    return await pg.evaluate("[document.documentElement.classList.contains('alien'), document.getElementById('whot').textContent, document.getElementById('flash').textContent, localStorage.who || '', localStorage.alien || '']")
PASSWORDS = ["banjo", "loon", "love", "choke", "magnet", "hug", "alien", "puke", "levity", "490110", "stability", "stable"]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
        ctx = await b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2, is_mobile=True, has_touch=True, permissions=["camera"])
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("**/lab-worker.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUB))
        await pg.goto(URL); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        fails = 0
        def check(ok, what):
            nonlocal fails; fails += (not ok); print(("  PASS  " if ok else "  FAIL  ") + what)
        pill = await pg.evaluate("(() => { const r = document.getElementById('who').getBoundingClientRect(); return [document.getElementById('whot').textContent, Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })()")
        check(pill[0] == "SIGN IN" and pill[2] < 60 and pill[4] >= 26, f"the pill at the top left reads '{pill[0]}' at ({pill[1]},{pill[2]}) {pill[3]}x{pill[4]} px")
        await pg.click("#who"); await asyncio.sleep(0.15); pre = await pg.input_value("#si-ini"); foc = await pg.evaluate("document.activeElement && document.activeElement.id")
        sheet = await pg.evaluate("[document.getElementById('panel').classList.contains('on'), !document.getElementById('signin').hidden]")
        check(sheet == [True, True] and pre == "Rachel G" and foc == "si-pw", f"one tap on the pill opens the sheet with 'Rachel G' typed in and the cursor in the password: '{pre}', focus={foc}")
        shown = await pg.evaluate("[...document.images].filter(i => i.src.startsWith('data:image/jpeg') && !i.hidden && i.getBoundingClientRect().width > 0).length")
        check(shown == 0, f"no picture anywhere before sign-in (sheet open): {shown} shown")
        await pg.click("#si-x"); await pg.click("#pclose")
        r = await sign(pg, None, "mandolin", via="panel")
        check(not r[0] and r[1] == "SIGN IN" and "NOT THE PASSWORD" in r[2], f"wrong password refused (via the panel's first line): alien={r[0]} pill='{r[1]}' flash='{r[2]}'")
        await pg.click("#si-x"); await pg.click("#pclose")
        r = await sign(pg, None, "BANJO")
        check(r[0] and r[1] == "RG" and r[3] == "" and r[4] == "" and "WELCOME ABOARD, RG" in r[2], f"pre-typed name + BANJO (upper case): alien={r[0]} who='{r[1]}' nothing stored (who='{r[3]}' alien='{r[4]}') flash='{r[2]}'")
        pic = await pg.evaluate("(() => { const i = document.getElementById('whoimg'); const r = i.getBoundingClientRect(); return [!i.hidden, Math.round(r.width), Math.round(r.height), getComputedStyle(document.querySelector('#who svg')).display]; })()")
        check(pic[0] and pic[1] == 22 and pic[3] == "none", f"the pill wears her picture: shown={pic[0]} {pic[1]}x{pic[2]} px, alien badge hidden behind it ({pic[3]})")
        # every password, in a different case each time
        await pg.click("#who"); first = await pg.evaluate("document.querySelector('#psheet button').id + ':' + document.querySelector('#psheet button').textContent")
        check(first == "psign:SIGN OUT - RG", f"signed in, the pill opens the panel and its first line is '{first.split(':')[1]}'")
        await pg.click("#psign"); await asyncio.sleep(0.2)      # sign out
        okpw = []
        for i, w in enumerate(PASSWORDS):
            typed = w.upper() if i % 3 == 0 else (w.capitalize() if i % 3 == 1 else w)
            r = await sign(pg, None, typed); okpw.append(bool(r[0] and r[1] == "RG"))
            await pg.click("#who"); await pg.click("#psign"); await asyncio.sleep(0.15)   # sign out again
        check(all(okpw), f"all {len(PASSWORDS)} passwords open the sky regardless of case: {sum(okpw)}/{len(PASSWORDS)}")
        r = await sign(pg, None, "banjo")
        bg = await pg.evaluate("getComputedStyle(document.body).backgroundImage.split('radial-gradient').length - 1")
        glow = await pg.evaluate("getComputedStyle(document.getElementById('who')).boxShadow !== 'none'")
        planet = await pg.evaluate("/19px/.test(getComputedStyle(document.body).backgroundImage)")
        check(bg >= 14 and glow and not planet, f"the sky: {bg} fixed stars in the body background, the pill glows green ({glow}), no pink planet ({not planet})")
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000); await asyncio.sleep(0.3)
        await pg.screenshot(path=OUT + "visitor-camera.png")
        await pg.click("#who"); await asyncio.sleep(0.2); await pg.screenshot(path=OUT + "visitor-panel.png"); await pg.click("#psign"); await asyncio.sleep(0.2)
        # psign now reads SIGN OUT and signs out; undo that for the sheet screenshot
        r = await pg.evaluate("[document.documentElement.classList.contains('alien'), document.getElementById('whot').textContent]")
        check(not r[0] and r[1] == "SIGN IN", f"SIGN OUT from the panel: alien={r[0]} pill='{r[1]}'")
        await pg.click("#who"); await asyncio.sleep(0.2); await pg.screenshot(path=OUT + "visitor-signin.png")
        await pg.fill("#si-ini", "rg"); await pg.fill("#si-pw", "Loon"); await pg.click("#si-go"); await asyncio.sleep(0.4)
        r = await pg.evaluate("[document.documentElement.classList.contains('alien'), document.getElementById('whot').textContent]")
        check(r[0] and r[1] == "RG", f"'rg' + Loon: alien={r[0]} who='{r[1]}'")
        await pg.reload(); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        r = await pg.evaluate("[document.documentElement.classList.contains('alien'), document.getElementById('whot').textContent]")
        check(not r[0] and r[1] == "SIGN IN", f"a restart signs out: alien={r[0]} pill='{r[1]}'")
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000)
        await sign(pg, None, "stable")
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000)
        await pg.click("#shutter"); await pg.wait_for_function("document.getElementById('bath').classList.contains('on')", timeout=5000)
        await pg.screenshot(path=OUT + "visitor-developing.png")
        await pg.wait_for_function("document.getElementById('print').classList.contains('on')", timeout=120000)
        await pg.screenshot(path=OUT + "visitor-print.png")
        code = await pg.text_content("#pcode"); check(bool(code and "·" in code), f"a frame develops under the sky: print code '{code}'")
        await pg.click("#back"); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        print("  the sounds, rendered offline from the page's own synthesizer:")
        for which, names in SOUNDS.items():
            for name, secs in names.items():
                data = await pg.evaluate(RENDER, [which, name, secs])
                peak = max(abs(x) for x in data); rms = (sum(x * x for x in data) / len(data)) ** 0.5
                nz = [i for i, x in enumerate(data) if abs(x) > 1e-4]; dur = (nz[-1] - nz[0]) / 44100 if nz else 0
                with wave.open(OUT + f"sfx-{which}-{name}.wav", "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
                    w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x)) * 32767)) for x in data))
                check(peak > 0.02 and peak < 0.6 and dur > 0.05, f"sfx {which:5s} {name:8s} {dur:.2f}s  peak {peak:.2f}  rms {rms:.3f}  -> sfx-{which}-{name}.wav")
        await pg.click("#who"); await pg.click("#psign"); await asyncio.sleep(0.2)    # sign out
        r = await sign(pg, "L B", "")
        check(not r[0] and r[1] == "LB" and r[4] == "" and "SIGNED IN - LB" in r[2], f"a plain sign-in has no sky: alien={r[0]} who='{r[1]}' flash='{r[2]}'")
        nopic = await pg.evaluate("document.getElementById('whoimg').hidden")
        check(nopic, "and no picture on the pill for initials without one")
        await pg.click("#who"); await pg.click("#psign"); await asyncio.sleep(0.2)    # sign out LB
        r = await sign(pg, "Rita", "banjo")
        check(not r[0] and "NOT THE PASSWORD" in r[2], f"Rita with Rachel's password: refused ({r[2]})")
        await pg.click("#si-x"); await pg.click("#pclose")
        r = await sign(pg, "Rita", "EnemyOfMan")
        hive = await pg.evaluate("[document.documentElement.classList.contains('hive'), document.documentElement.classList.contains('alien'), getComputedStyle(document.getElementById('whobee')).display !== 'none', getComputedStyle(document.body).fontFamily]")
        check(hive[0] and not hive[1] and r[1] == "RITA" and r[2] == "WELCOME, RITA" and hive[2], f"Rita + EnemyOfMan: hive={hive[0]} alien={hive[1]} pill='{r[1]}' bee badge={hive[2]} flash='{r[2]}' font='{hive[3][:24]}'")
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000); await asyncio.sleep(0.3)
        await pg.screenshot(path=OUT + "visitor-hive-camera.png")
        await pg.click("#shutter"); await pg.wait_for_function("document.getElementById('bath').classList.contains('on')", timeout=5000)
        word = await pg.text_content("#bathtext"); await asyncio.sleep(1.2); await pg.screenshot(path=OUT + "visitor-hive-developing.png")
        await asyncio.sleep(3.4); word2 = await pg.text_content("#bathtext")
        lines = await pg.evaluate("LUCA_COUNT")
        await pg.wait_for_function("document.getElementById('print').classList.contains('on')", timeout=120000); await asyncio.sleep(0.3)
        shown = await pg.evaluate("document.getElementById('flash').classList.contains('on')"); await pg.screenshot(path=OUT + "visitor-hive-print.png")
        w1 = word.split("  ")[0]; w2 = word2.split("  ")[0]
        check(w1.startswith("RITA IS") and w2.startswith("RITA IS") and w1 != w2 and lines >= 160 and not shown, f"under the hive the finder says what Rita is doing to Luca - '{w1}' then '{w2}' ({lines} lines in the deck), no line with the print")
        await pg.click("#back"); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        await pg.click("#who"); await pg.click("#psign"); await asyncio.sleep(0.2)
        r = await pg.evaluate("[document.documentElement.className, document.getElementById('whot').textContent]")
        check(r[0] == "" and r[1] == "SIGN IN", f"Rita signs out: html class='{r[0]}' pill='{r[1]}'")
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 932, "height": 430}, device_scale_factor=2, is_mobile=True, has_touch=True, permissions=["camera"])
        pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("**/lab-worker.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUB))
        await pg.goto(URL); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        await sign(pg, None, "490110")
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000); await asyncio.sleep(0.3)
        await pg.screenshot(path=OUT + "visitor-landscape.png")
        r = await pg.evaluate("[document.documentElement.classList.contains('alien'), document.getElementById('whot').textContent]")
        check(r[0] and r[1] == "RG", f"landscape, signed in: alien={r[0]} who='{r[1]}'")
        print(f"\nTHE VISITOR: {'all PASS' if not fails else str(fails) + ' FAIL'}   page errors: {errs or 'none'}")
        await b.close()
asyncio.run(main())
