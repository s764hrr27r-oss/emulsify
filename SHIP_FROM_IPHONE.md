# Emulsify — ship it from your iPhone

Static files. Host on GitHub Pages, entirely from Safari:

1. github.com → New repository → `emulsify` → Public → Create.
2. "uploading an existing file" → upload everything in this zip → Commit.
3. Settings → Pages → Deploy from branch → main / root → Save.
4. Open https://YOURNAME.github.io/emulsify/ → Share → Add to Home Screen.

## What it is
One camera. One film (Honey 70 — the canon, verbatim, running in
WebAssembly). One button. Shoot; the frame develops in ~30–45 s; the
thumbnail chip breathes amber while the tray works, then shows the print.
Tap the chip for the print, SAVE sends it to Photos. Shoot freely while
frames develop — they queue.

First launch downloads the chemistry once (~60 MB), then it's cached.
Everything stays on the phone. No accounts, no uploads, no feed.

To swap the stock to Scope 70: in index.html change profile:"honey" to
"scope" (one line). The canon never changes.
