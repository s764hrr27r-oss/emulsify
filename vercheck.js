import fs from "fs";
const s = fs.readFileSync("lab-worker.js", "utf8");
const head = /^\/\/ lab-worker\.js — v([0-9.]+)\./m.exec(s);
const rep  = /const WORKER_VER = "([0-9.]+)"/.exec(s);
const g    = fs.existsSync("golden.py") ? fs.readFileSync("golden.py", "utf8") : "";
const gv   = /GOLDEN_V(\d+) = "([0-9a-f]+)"/.exec(g);
console.log(`  header says      v${head ? head[1] : "??"}`);
console.log(`  WORKER_VER says  v${rep ? rep[1] : "??"}   <- this is what the panel shows`);
console.log(`  golden           v${gv ? gv[1] : "??"} = ${gv ? gv[2] : "??"}`);
if (!head || !rep || head[1] !== rep[1]) {
  console.log("\n  MISMATCH - the panel would report a version the worker is not.");
  process.exit(1);
}
console.log("\n  agree");
