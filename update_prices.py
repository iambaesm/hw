#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, base64, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/"price-config.enc.json"
OUT=ROOT/"prices.enc.json"
UA="Mozilla/5.0 (compatible; HWGIPriceMonitor/1.0)"

def b64d(s): return base64.b64decode(s)
def decrypt_pkg(path,key):
    pkg=json.loads(path.read_text(encoding="utf-8"))
    pt=AESGCM(key).decrypt(b64d(pkg["iv"]),b64d(pkg["ciphertext"]),None)
    return json.loads(pt.decode("utf-8"))
def encrypt_pkg(obj,key):
    iv=os.urandom(12)
    pt=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode()
    ct=AESGCM(key).encrypt(iv,pt,None)
    return {"v":1,"alg":"AES-256-GCM","iv":base64.b64encode(iv).decode(),"ciphertext":base64.b64encode(ct).decode()}
def get_json(url,timeout=15):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","replace"))
def num(x):
    if x is None: return None
    if isinstance(x,(int,float)): return float(x)
    s=str(x).replace(",","").replace("원","").strip()
    try:return float(s)
    except:return None

def naver_quote(code):
    u=f"https://m.stock.naver.com/api/stock/{urllib.parse.quote(code)}/basic"
    d=get_json(u)
    p=num(d.get("closePrice") or d.get("currentPrice"))
    if p is None: raise ValueError("Naver price missing")
    asof=d.get("localTradedAt") or d.get("tradeStopType") or ""
    return {"price":p,"currency":"KRW","asof":asof,"source":"NAVER Finance"}

def yahoo_quote(symbol,currency_hint=""):
    u="https://query1.finance.yahoo.com/v8/finance/chart/"+urllib.parse.quote(symbol,safe="")+"?interval=1m&range=1d&includePrePost=false"
    d=get_json(u)
    result=((d.get("chart") or {}).get("result") or [None])[0]
    if not result: raise ValueError("Yahoo result missing")
    meta=result.get("meta") or {}
    p=meta.get("regularMarketPrice")
    if p is None:
        closes=(((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
        vals=[x for x in closes if x is not None]
        p=vals[-1] if vals else None
    if p is None: raise ValueError("Yahoo price missing")
    ts=meta.get("regularMarketTime")
    asof=datetime.fromtimestamp(ts,timezone.utc).isoformat() if ts else ""
    cur=meta.get("currency") or currency_hint or ""
    if symbol.endswith(".L") and cur=="GBP":
        cur="GBX"
        if float(p)<50: p=float(p)*100
    return {"price":float(p),"currency":cur,"asof":asof,"source":"Yahoo Finance"}

def main():
    key_b64=os.environ.get("PRICE_DATA_KEY_B64","").strip()
    if not key_b64: raise SystemExit("PRICE_DATA_KEY_B64 is required")
    key=base64.b64decode(key_b64)
    if len(key)!=32: raise SystemExit("PRICE_DATA_KEY_B64 must decode to 32 bytes")

    cfg=decrypt_pkg(CONFIG,key)
    previous={}
    try: previous=decrypt_pkg(OUT,key).get("prices",{})
    except Exception: pass

    prices={}
    for s in cfg.get("symbols",[]):
        rec=None; errors=[]
        if s.get("naver"):
            try: rec=naver_quote(s["naver"])
            except Exception as e: errors.append("Naver:"+str(e))
        if rec is None and s.get("yahoo"):
            try: rec=yahoo_quote(s["yahoo"],s.get("currency",""))
            except Exception as e: errors.append("Yahoo:"+str(e))
        if rec is None:
            old=previous.get(s["key"])
            if old:
                rec=dict(old)
                rec["stale"]=True
                rec["error"]=" | ".join(errors)
            else:
                print("[WARN]",s["key"]," | ".join(errors))
                continue
        rec["name"]=s.get("name","")
        rec["market"]=s.get("market","")
        prices[s["key"]]=rec

    payload={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "prices":prices
    }
    OUT.write_text(json.dumps(encrypt_pkg(payload,key),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"updated {len(prices)}/{len(cfg.get('symbols',[]))} prices")

if __name__=="__main__":
    main()
