# EMULSIFY rituals — b232 / w3.24

Run all before every stage. Each has caught a real fault.

    ./runcheck.sh                        page: module syntax + every $("id") exists
    node vercheck.mjs                    worker: header version == WORKER_VER (the panel lied for two builds)
    timeout 900 python3 golden.py lab-worker.js    chemistry: must print HOLDS (v21 = 4be892e9e27c70ec; v20 was 1d98c30d46224867)
    python3 bandcheck.py                 chemistry: strips == whole frame, exact
    python3 e2e-server.py &  sleep 9;  python3 e2e.py     THE PAGE, RUNNING: headless Chromium, fake
                                         camera, stub worker on the real protocol, real develop()
                                         behind POST /develop. Boot, shoot, bath, print, save, panel,
                                         crash recovery. Must end "page errors: none".

Template rules for lab-worker.js (the Python lives in a JS template literal):
no backticks, no ${, no single backslashes. The golden harness refuses NUL.

    python3 e2e-overlay.py               THE ROTATION PROOF: every control measured in both orientations,
                                         portrait carried through the phone's rotation, must land within
                                         1.5px; writes rotation-overlay.png (rotated portrait blended over
                                         landscape - a control that landed shows as ONE shape).
    python3 e2e-glass.py                 the lens ladder (crop per lens, EXIF mm), the anamorphic
                                         toggle (finder aspect, desqueezed print width), landscape column order.
                                         The stub forwards EVERY field the page sends (ana, dc, mm, leak) - it
                                         hid a missing desqueeze once by not forwarding ana.
                                         b222: THE FINDER SHOWS THE NEGATIVE - the gate's window, read back
                                         from the video element's geometry in frame pixels, must equal the
                                         negative capture() cut (size within 1.5 px, centred within 1 px) for
                                         every lens, under the squeeze, and turned. b221 showed the whole frame
                                         at the 33 (the print was the middle 79%); this line fails on it 5 times.
    python3 e2e-visitor.py               b223-b232 THE VISITORS: the SIGN IN pill top left (one tap opens the sheet;
                                         signed in it reads the initials and opens the panel, SIGN OUT first); the
                                         sheet opens with Rachel G typed in, no picture anywhere before sign-in (the
                                         pill wears her 192 px JPEG only once signed in); a wrong password is refused;
                                         every one of RG's twelve passwords opens the saucer sky in any case; RITA with
                                         RG's password is refused, RITA + enemyofman (any case) opens the hive (bee
                                         badge, bee shutter, serif face, plain WELCOME, RITA; while a frame develops the finder deals what Rita is doing to Luca from a 169-line shuffled deck, a new one every 4 s); RG's sky has no pink planet; nothing is
                                         stored and a reload signs out; a plain sign-in has no sky; a frame develops
                                         under each sky; fourteen sounds (seven per sky) render offline from the
                                         page's own synthesizer to sfx-<sky>-*.wav (peak 0.05-0.19, nothing clips).
                                         Writes visitor-*.png.
