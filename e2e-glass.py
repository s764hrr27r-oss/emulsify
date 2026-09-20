import asyncio, base64, io
from playwright.async_api import async_playwright
from PIL import Image
STUB = open("/home/claude/emulsify/e2e-stub.js").read()
NEG_DIMS = """() => new Promise(res => { const r = indexedDB.open('emulsify-one', 3); r.onsuccess = () => { const t = r.result.transaction('negs').objectStore('negs').getAll(); t.onsuccess = () => { const rec = t.result[t.result.length-1]; if (!rec) return res(null); createImageBitmap(rec.blob).then(b => res([b.width, b.height])); }; }; })"""
PRINT = """() => new Promise(res => { const r = indexedDB.open('emulsify-one', 3); r.onsuccess = () => { const t = r.result.transaction('prints').objectStore('prints').getAll(); t.onsuccess = () => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(t.result[t.result.length-1]); }; }; })"""
WINDOW = """() => { const v = document.getElementById('video'), f = document.getElementById('finder');
  const V = v.getBoundingClientRect(), F = f.getBoundingClientRect(); const vw = v.videoWidth, vh = v.videoHeight;
  const x0 = (F.left - V.left) / V.width * vw, x1 = (F.right - V.left) / V.width * vw, y0 = (F.top - V.top) / V.height * vh, y1 = (F.bottom - V.top) / V.height * vh;
  return { vw, vh, x0, y0, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2 - vw / 2, cy: (y0 + y1) / 2 - vh / 2 }; }"""
def window_check(win, dims):
    """the finder's window, in frame pixels, must be the negative: same size, centred on the frame"""
    ok = abs(win["w"] - dims[0]) <= 1.5 and abs(win["h"] - dims[1]) <= 1.5 and abs(win["cx"]) <= 1 and abs(win["cy"]) <= 1
    return ("PASS" if ok else "FAIL") + f"  finder window {win['w']:.1f}x{win['h']:.1f} of the {win['vw']}x{win['vh']} frame, centre off by ({win['cx']:.1f},{win['cy']:.1f})  vs negative {dims[0]}x{dims[1]}"
async def shoot(pg):
    await pg.click("#shutter")
    await pg.wait_for_function("document.getElementById('bath').classList.contains('on')", timeout=5000)
    dims = await pg.evaluate(NEG_DIMS)
    await pg.wait_for_function("document.getElementById('print').classList.contains('on')", timeout=120000)
    b64 = await pg.evaluate(PRINT); im = Image.open(io.BytesIO(base64.b64decode(b64))); ex = im.getexif()
    await pg.click("#back"); await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
    return dims, im.size, " | ".join(str(v) for v in ex.values() if isinstance(v, str))[:40]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream","--no-sandbox"])
        ctx = await b.new_context(viewport={"width":430,"height":932}, device_scale_factor=2, is_mobile=True, has_touch=True, permissions=["camera"])
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("**/lab-worker.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUB))
        await pg.goto("http://127.0.0.1:8765/index.html")
        await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000)
        print("THE GLASS (fake camera reports one device, labelled neither ultra nor tele -> every lens realises from a 26):")
        fails = 0
        for i in range(3):
            lab = await pg.text_content("#lens")
            win = await pg.evaluate(WINDOW)
            dims, psize, exif = await shoot(pg)
            chk = window_check(win, dims); fails += chk.startswith("FAIL")
            print(f"  lens {lab:5s} negative {dims[0]}x{dims[1]}   print {psize[0]}x{psize[1]}   exif {exif}")
            print(f"        {chk}")
            await pg.click("#lens"); await asyncio.sleep(0.8)
        print("\nANAMORPHIC:")
        sq0 = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sq').trim()")
        f0 = await pg.evaluate("(() => { const r = document.getElementById('finder').getBoundingClientRect(); return (r.width/r.height).toFixed(3); })()")
        await pg.click("#menu"); await pg.click("#pana"); t = await pg.text_content("#pana"); await pg.click("#pclose")
        sq1 = await pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sq').trim()")
        f1 = await pg.evaluate("(() => { const r = document.getElementById('finder').getBoundingClientRect(); return (r.width/r.height).toFixed(3); })()")
        print(f"  off: --sq {sq0}  finder aspect {f0}      on: '{t}'  --sq {sq1}  finder aspect {f1}  (4/5 = 0.800, 4*1.33/5 = 1.064)")
        await asyncio.sleep(0.3); win = await pg.evaluate(WINDOW)
        dims, psize, exif = await shoot(pg)
        chk = window_check(win, dims); fails += chk.startswith("FAIL")
        print(f"  shot with the squeeze on: negative {dims[0]}x{dims[1]} (squeezed, as the sensor saw it)  ->  print {psize[0]}x{psize[1]}  (880 x 1.33 = 1170: the lab desqueezed it)")
        print(f"        {chk}")
        await pg.screenshot(path="/home/claude/emulsify/b215-portrait.png")
        await ctx.close()
        ctx = await b.new_context(viewport={"width":932,"height":430}, device_scale_factor=2, is_mobile=True, has_touch=True, permissions=["camera"])
        pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("**/lab-worker.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUB))
        await pg.goto("http://127.0.0.1:8765/index.html")
        await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
        await asyncio.sleep(0.5)
        rows = []
        for id in ("strip","lens","shutter","menu"):
            r = await pg.evaluate(f"(() => {{ const r = document.getElementById('{id}').getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.height)]; }})()"); rows.append((id, r))
        print("\nLANDSCAPE right column, top to bottom: " + "  ".join(f"{id} y={r[1]}" for id, r in rows))
        await pg.wait_for_function("document.getElementById('video').videoWidth > 0", timeout=10000); await asyncio.sleep(0.3)
        win = await pg.evaluate(WINDOW); dims, psize, exif = await shoot(pg)
        chk = window_check(win, dims); fails += chk.startswith("FAIL")
        print(f"  landscape shot: negative {dims[0]}x{dims[1]}  print {psize[0]}x{psize[1]}\n        {chk}")
        print(f"\nTHE FINDER SHOWS THE NEGATIVE: {'all PASS' if not fails else str(fails) + ' FAIL'}")
        await pg.screenshot(path="/home/claude/emulsify/b215-landscape.png")
        print(f"\npage errors: {errs or 'none'}")
        await b.close()
asyncio.run(main())
