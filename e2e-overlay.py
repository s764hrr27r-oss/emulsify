"""THE ROTATION PROOF. Portrait and landscape are rendered at the same phone size,
every control's centre is measured in both, the portrait centres are carried
through the phone's own rotation - counter-clockwise: (x, y) -> (y, W - x) - and
compared with where landscape actually put them. The two screenshots are then
blended, the portrait one rotated the same way, so a control that landed where
the rotation carried it shows as ONE shape and a miss shows as two."""
import asyncio, sys
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont
STUB = open("/home/claude/emulsify/e2e-stub.js").read()
W, H = 430, 932
PLANT = """(n) => new Promise(res => { const r = indexedDB.open('emulsify-one', 3); r.onsuccess = () => { const db = r.result; let k = 0; const one = i => { const c = document.createElement('canvas'); c.width = 88; c.height = 110; const g = c.getContext('2d'); g.fillStyle = `hsl(${i*47},50%,45%)`; g.fillRect(0,0,88,110); g.fillStyle='#fff'; g.font='40px sans-serif'; g.fillText(String(i), 28, 72); c.toBlob(b => { const t = db.transaction(['prints','thumbs'],'readwrite'); const id = String(1600000000000 + i); t.objectStore('prints').put(b, id); t.objectStore('thumbs').put(b, id); t.oncomplete = () => { if (++k === n) res(); }; }, 'image/jpeg', 0.8); }; for (let i = 0; i < n; i++) one(i); }; })"""
IDS = ("shutter", "lens", "menu", "strip", "finder")
async def shot(b, w, h, name, landr=False):
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, permissions=["camera"])
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route("**/lab-worker.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=STUB))
    if landr: await pg.add_init_script("Object.defineProperty(window, 'orientation', { get: () => -90 });")
    await pg.goto("http://127.0.0.1:8765/index.html")
    await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
    await pg.evaluate(PLANT, 6); await pg.reload()
    await pg.wait_for_function("document.getElementById('state').textContent === 'READY'", timeout=20000)
    await pg.wait_for_function("document.querySelectorAll('#strip img').length >= 6", timeout=10000)
    rects = {}
    for id in IDS:
        rects[id] = await pg.evaluate(f"(() => {{ const r = document.getElementById('{id}').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }})()")
    first = await pg.evaluate("(() => { const r = document.querySelector('#strip img').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })()")
    rects["newest"] = first
    await pg.screenshot(path=f"/home/claude/emulsify/{name}.png")
    await ctx.close()
    return rects, errs
def centre(r): return (r[0] + r[2] / 2, r[1] + r[3] / 2)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--no-sandbox"])
        P, e1 = await shot(b, W, H, "ov-portrait")
        L, e2 = await shot(b, H, W, "ov-landscape")
        R, e3 = await shot(b, H, W, "ov-landscape-r", landr=True)
        await b.close()
    worst = 0
    print("island LEFT (turned counter-clockwise): portrait (x,y) -> landscape (y, W-x)")
    for id in ("shutter", "lens", "menu", "newest"):
        px, py = centre(P[id]); want = (py, W - px); got = centre(L[id])
        d = ((want[0]-got[0])**2 + (want[1]-got[1])**2) ** .5; worst = max(worst, d)
        print(f"  {id:8s} portrait ({px:5.1f},{py:5.1f}) -> should land ({want[0]:5.1f},{want[1]:5.1f})   landscape has ({got[0]:5.1f},{got[1]:5.1f})   miss {d:4.1f}px")
    print("island RIGHT (turned clockwise): portrait (x,y) -> landscape (H-y, x)")
    for id in ("shutter", "lens", "menu", "newest"):
        px, py = centre(P[id]); want = (H - py, px); got = centre(R[id])
        d = ((want[0]-got[0])**2 + (want[1]-got[1])**2) ** .5; worst = max(worst, d)
        print(f"  {id:8s} -> should land ({want[0]:5.1f},{want[1]:5.1f})   landscape has ({got[0]:5.1f},{got[1]:5.1f})   miss {d:4.1f}px")
    # the overlay: portrait rotated CCW, blended over landscape
    a = Image.open("/home/claude/emulsify/ov-portrait.png").rotate(90, expand=True)
    bimg = Image.open("/home/claude/emulsify/ov-landscape.png")
    a = a.resize(bimg.size, Image.LANCZOS)
    ov = Image.blend(bimg.convert("RGB"), a.convert("RGB"), 0.5)
    ov2 = Image.new("RGB", (bimg.width, bimg.height * 2 + 24), (18,18,20))
    ov2.paste(ov, (0, 0)); ov2.paste(bimg.convert("RGB"), (0, bimg.height + 24))
    # tint: portrait in orange, landscape in cyan, so a coincident control turns white-ish and a miss shows two colours
    ta = Image.merge("RGB", (a.convert("L"), a.convert("L").point(lambda v: int(v*0.55)), a.convert("L").point(lambda v: int(v*0.15))))
    tb = Image.merge("RGB", (bimg.convert("L").point(lambda v: int(v*0.15)), bimg.convert("L").point(lambda v: int(v*0.7)), bimg.convert("L")))
    tint = Image.blend(ta, tb, 0.5).point(lambda v: min(255, int(v * 1.8)))
    ov2.paste(tint, (0, 0))
    ov2.save("/home/claude/emulsify/rotation-overlay.png", optimize=True)
    print(f"\nworst miss {worst:.1f}px   page errors: {(e1+e2+e3) or 'none'}")
    sys.exit(0 if worst < 1.5 and not (e1+e2+e3) else 1)
asyncio.run(main())
