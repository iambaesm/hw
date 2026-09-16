#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DEFAULT_ITERATIONS = 250_000

@dataclass(frozen=True)
class DashboardSpec:
    kind: str
    target: str
    title: str

def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def detect_dashboard(html: str, filename: str = "", config: dict | None = None) -> DashboardSpec:
    config = config or load_config()
    hay = (filename + "\n" + re.sub(r"<[^>]+>", " ", html)).lower()
    scored = []
    for kind, spec in config["dashboards"].items():
        score = sum(max(2, len(kw)) for kw in spec.get("keywords", []) if kw.lower() in hay)
        if score:
            scored.append((score, kind, spec))
    if not scored:
        raise ValueError("대시보드 유형을 자동 판별하지 못했습니다. --kind 옵션을 사용하세요.")
    scored.sort(reverse=True)
    _, kind, spec = scored[0]
    return DashboardSpec(kind, spec["target"], spec["title"])

def normalize_password(password: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", password.strip())

def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        normalize_password(password).encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )

def encrypt_html(plain_html: str, password: str, title: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)
    ct = AESGCM(derive_key(password, salt, iterations)).encrypt(iv, plain_html.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    template = r'''<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover"><meta name="robots" content="noindex,nofollow,noarchive"><meta http-equiv="Cache-Control" content="no-store,no-cache,must-revalidate,max-age=0"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0"><title>__TITLE__ · 암호화</title><style>:root{--nav:#182430;--accent:#F37321;--bg:#F2F3F1;--ink:#1C2733;--muted:#77828E;--line:#DDE2DE}*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:Pretendard,'Noto Sans KR','Malgun Gothic',sans-serif}body{min-height:100vh;background:var(--bg);color:var(--ink);display:grid;place-items:center;padding:24px}.lock{width:min(420px,100%);background:#fff;border:1px solid var(--line);border-radius:16px;padding:26px 24px;box-shadow:0 10px 32px rgba(24,36,48,.10)}.mark{width:44px;height:44px;border-radius:12px;background:var(--nav);display:grid;place-items:center;margin-bottom:16px;color:#fff;font-size:22px}h1{font-size:1.18rem;margin:0 0 6px;font-weight:850}.sub{font-size:.82rem;color:var(--muted);line-height:1.55;margin-bottom:18px}label{display:block;font-size:.78rem;font-weight:800;margin-bottom:7px}input{width:100%;height:46px;border:1px solid #CCD3CE;border-radius:10px;padding:0 13px;font:inherit;outline:none;background:#fff}button{width:100%;height:46px;margin-top:10px;border:0;border-radius:10px;background:var(--nav);color:#fff;font:inherit;font-weight:800;cursor:pointer}.err{display:none;margin-top:10px;font-size:.76rem;color:#B33A2B}</style></head><body><div class="lock"><div class="mark">🔒</div><h1>__TITLE__</h1><div class="sub">암호화된 사내 자료입니다. 비밀번호를 입력하면 화면이 열립니다.</div><form id="unlockForm"><label for="pw">비밀번호</label><input id="pw" type="password" autocomplete="current-password" autofocus><button id="btn" type="submit">현황 열기</button><div class="err" id="err">비밀번호를 다시 확인해 주세요.</div></form></div><script>const CIPHER="__CIPHER__",SALT="__SALT__",IV="__IV__",ITERATIONS=__ITER__;function B64(s){const bin=atob(s),out=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)out[i]=bin.charCodeAt(i);return out;}document.getElementById("unlockForm").addEventListener("submit",async e=>{e.preventDefault();const btn=document.getElementById("btn"),err=document.getElementById("err");err.style.display="none";btn.disabled=true;try{const pw=(document.getElementById("pw").value||"").trim().normalize("NFKC"),enc=new TextEncoder(),baseKey=await crypto.subtle.importKey("raw",enc.encode(pw),"PBKDF2",false,["deriveKey"]),key=await crypto.subtle.deriveKey({name:"PBKDF2",salt:B64(SALT),iterations:ITERATIONS,hash:"SHA-256"},baseKey,{name:"AES-GCM",length:256},false,["decrypt"]),plain=await crypto.subtle.decrypt({name:"AES-GCM",iv:B64(IV)},key,B64(CIPHER)),page=new TextDecoder("utf-8").decode(plain);document.open();document.write(page);document.close();}catch(ex){console.error("dashboard decrypt failed",ex);err.style.display="block";btn.disabled=false;}});</script></body></html>'''
    return (template.replace("__TITLE__", title)
            .replace("__CIPHER__", b64(ct))
            .replace("__SALT__", b64(salt))
            .replace("__IV__", b64(iv))
            .replace("__ITER__", str(iterations)))

def _extract(wrapper: str, name: str) -> str:
    m = re.search(rf'{re.escape(name)}="([^"]+)"', wrapper)
    if not m:
        raise ValueError(f"{name} not found")
    return m.group(1)

def verify_wrapper(wrapper: str, password: str, expected_plain: str | None = None) -> str:
    cipher = base64.b64decode(_extract(wrapper, "CIPHER"))
    salt = base64.b64decode(_extract(wrapper, "SALT"))
    iv = base64.b64decode(_extract(wrapper, "IV"))
    m = re.search(r"ITERATIONS=(\d+)", wrapper)
    if not m:
        raise ValueError("ITERATIONS not found")
    plain = AESGCM(derive_key(password, salt, int(m.group(1)))).decrypt(iv, cipher, None).decode("utf-8")
    if expected_plain is not None and plain != expected_plain:
        raise ValueError("암호화 검증 실패")
    return plain

def github_get_sha(repo: str, path: str, token: str) -> str | None:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "HWGI-Dashboard-Publisher/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def github_put(repo: str, path: str, content: str, token: str, message: str, sha: str | None = None) -> dict:
    payload = {"message": message, "content": base64.b64encode(content.encode()).decode()}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        data=json.dumps(payload).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "HWGI-Dashboard-Publisher/1.0",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--kind", default="auto")
    ap.add_argument("--output")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--repo", default="iambaesm/hw")
    ap.add_argument("--target")
    args = ap.parse_args()

    password = os.environ.get("DASHBOARD_PASSWORD", "")
    if not password:
        print("DASHBOARD_PASSWORD is required", file=sys.stderr)
        return 2

    src = Path(args.input)
    plain = src.read_text(encoding="utf-8")
    cfg = load_config()
    if args.kind == "auto":
        spec = detect_dashboard(plain, src.name, cfg)
    else:
        raw = cfg["dashboards"][args.kind]
        spec = DashboardSpec(args.kind, raw["target"], raw["title"])

    target = args.target or spec.target
    wrapper = encrypt_html(plain, password, spec.title)
    verify_wrapper(wrapper, password, plain)
    out = Path(args.output or target)
    out.write_text(wrapper, encoding="utf-8")
    print(f"[OK] kind={spec.kind} target={target}")
    print("[OK] decrypt verification passed")

    if args.publish:
        token = os.environ.get("GH_TOKEN", "")
        if not token:
            print("GH_TOKEN is required for --publish", file=sys.stderr)
            return 3
        sha = github_get_sha(args.repo, target, token)
        res = github_put(args.repo, target, wrapper, token, f"Publish {spec.title}", sha)
        print("[OK] published commit=" + ((res.get("commit") or {}).get("sha") or ""))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
