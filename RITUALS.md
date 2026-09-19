# EMULSIFY rituals — b213 / w3.23

Run all before every stage. Each has caught a real fault.

    ./runcheck.sh                        page: module syntax + every $("id") exists
    node vercheck.mjs                    worker: header version == WORKER_VER (the panel lied for two builds)
    timeout 900 python3 golden.py lab-worker.js    chemistry: must print HOLDS (v20 = 1d98c30d46224867)
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
