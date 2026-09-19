#!/bin/sh
# The page script is a module body (top-level await): parse it as one.
node -e '
const fs=require("fs"),s=fs.readFileSync("index.crashguard.work","utf8");
const js=[...s.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join("\n");
fs.writeFileSync("/tmp/_page.mjs", js);
const ids=new Set([...s.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]));
const used=new Set([...js.matchAll(/\$\(\s*"([^"]+)"\s*\)/g)].map(m=>m[1]));
const miss=[...used].filter(u=>!ids.has(u));
console.log("DOM audit:", miss.length?miss.join(", "):"clean");
console.log("BUILD:", /const BUILD = (\d+);/.exec(s)[1], "  page:", (s.length/1024).toFixed(0)+" KB", " js:", (js.length/1024).toFixed(0)+" KB");
' || exit 1
node --check /tmp/_page.mjs && echo "syntax: clean (module)"
