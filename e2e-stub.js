/* the worker's protocol, verbatim; the chemistry runs in CPython behind /develop */
const WORKER_VER = "3.23";
let CURJOB = 0;
const step = (n, t) => postMessage({ progress: t, step: n, steps: 5 });
const boot = (async () => { for (const [n,t] of [[1,"warming the lab…"],[2,"mixing chemistry…"],[3,"loading the canon…"],[4,"probing…"],[5,"ready"]]) { step(n,t); await new Promise(r=>setTimeout(r,60)); } postMessage({ ready: true, probe: 100, ver: WORKER_VER }); })();
onmessage = async (e) => {
  const { id, neg, seed, size } = e.data;
  try {
    await boot; CURJOB = id;
    postMessage({ id, stage: "neg", b64: "" });
    const r = await fetch(`/develop?seed=${seed}&size=${size||1100}&leak=${e.data.leak||0}&mm=${e.data.mm||0}&build=${e.data.build||0}&ana=${e.data.ana||1}&dc=${e.data.dc?1:0}`, { method: "POST", body: neg });
    const j = await r.json();
    const bin = atob(j.jpg); const bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    postMessage({ id, ok: true, result: bytes, secs: j.secs }, [bytes.buffer]);
  } catch (err) { postMessage({ id, ok: false, error: String(err) }); }
};
