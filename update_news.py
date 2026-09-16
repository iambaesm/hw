#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Asset-news updater for the quarterly monitoring dashboard.

- Searches public news with GDELT DOC 2.0 API (direct article URLs).
- Falls back to Google News RSS when GDELT is unavailable.
- Fetches article pages and creates a short extractive 2–3 sentence summary.
- Encrypts the resulting news payload with AES-256-GCM.
- Requires environment variable NEWS_DATA_KEY_B64 (base64-encoded 32-byte key).

No internal portfolio data is sent to a paid LLM/API.
"""
import os, re, json, base64, html, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "news.enc.json"
LOOKBACK_DAYS = 45
MAX_ITEMS = 3

ASSETS = {
    "dlive": {
        "label": "딜라이브 인수금융",
        "queries": ['딜라이브 매각 리캡 MBK', '"D\'LIVE" Korea cable MBK recapitalization']
    },
    "sia_a330": {
        "label": "싱가폴 항공 A330",
        "queries": ['Singapore Airlines A330-300 aircraft value lease', 'A330-300 lease rates aircraft values']
    },
    "gre2_685fifth": {
        "label": "한화 GLOBAL REAL ESTATE 2호",
        "queries": ['"685 Fifth Avenue" New York office loan', '"685 Fifth Avenue" CMBS']
    },
    "gres1_churchill": {
        "label": "한화 GLOBAL REAL ESTATE STRATEGY 1호",
        "queries": ['"5 Churchill Place" Canary Wharf office', '"5 Churchill Place" London sale']
    },
    "sangju_yeongcheon": {
        "label": "상주영천 고속도로",
        "queries": ['상주영천고속도로 통행량', '상주영천고속도로 민자']
    },
    "one_state_st": {
        "label": "하나대체투자 사모부동산 67호",
        "queries": ['"One State Street Plaza" New York office loan', '"One State Street Plaza" Manhattan']
    },
    "dumbo": {
        "label": "신한AIM부동산 제7호",
        "queries": ['"Dumbo Heights" Brooklyn office', '"DUMBO Heights" Kushner CIM']
    },
    "tsx_broadway": {
        "label": "신한AIM부동산 제10호",
        "queries": ['"TSX Broadway" Times Square loan', '"TSX Broadway" hotel retail']
    },
    "sll": {
        "label": "현대인베스트먼트 선순위대출 1호",
        "queries": ['SLL중앙 회생 큐리어스', '콘텐트리중앙 SLL중앙 회생']
    },
    "brookfield_bid2": {
        "label": "신한 BROOKFIELD 인프라대출 7호",
        "queries": ['"Brookfield Infrastructure Debt Fund II"', 'Brookfield infrastructure debt fund']
    },
    "ares_idf4": {
        "label": "KB ARES IDF IV",
        "queries": ['"Southern Water" Ares restructuring debt', '"Ares Infrastructure Debt Fund IV"']
    }
}

UA = "Mozilla/5.0 (compatible; HWGIAssetNewsMonitor/1.0; +https://github.com/)"

def fetch(url, timeout=20):
    req=urllib.request.Request(url, headers={"User-Agent":UA, "Accept-Language":"ko,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl(), dict(r.headers)

def parse_dt(s):
    if not s: return None
    for fn in (
        lambda x: datetime.fromisoformat(x.replace("Z","+00:00")),
        parsedate_to_datetime
    ):
        try:
            d=fn(s)
            if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            pass
    m=re.search(r'(\d{4})(\d{2})(\d{2})(?:T?(\d{2})(\d{2})(\d{2}))?', s)
    if m:
        y,mo,da,hh,mi,se=m.groups()
        return datetime(int(y),int(mo),int(da),int(hh or 0),int(mi or 0),int(se or 0),tzinfo=timezone.utc)
    return None

def gdelt_search(query, days=LOOKBACK_DAYS):
    end=datetime.now(timezone.utc)
    start=end-timedelta(days=days)
    params={
        "query":query,
        "mode":"ArtList",
        "maxrecords":"30",
        "format":"json",
        "sort":"HybridRel",
        "startdatetime":start.strftime("%Y%m%d%H%M%S"),
        "enddatetime":end.strftime("%Y%m%d%H%M%S"),
    }
    url="https://api.gdeltproject.org/api/v2/doc/doc?"+urllib.parse.urlencode(params)
    raw,_,_=fetch(url)
    data=json.loads(raw.decode("utf-8","replace"))
    out=[]
    for a in data.get("articles",[]):
        out.append({
            "title":html.unescape(a.get("title","")).strip(),
            "url":a.get("url",""),
            "source":a.get("domain",""),
            "published":a.get("seendate",""),
        })
    return out

def google_rss_search(query):
    q=urllib.parse.quote(query+" when:45d")
    url=f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    raw,_,_=fetch(url)
    root=ET.fromstring(raw)
    out=[]
    for it in root.findall(".//item"):
        title=(it.findtext("title") or "").strip()
        link=(it.findtext("link") or "").strip()
        pub=(it.findtext("pubDate") or "").strip()
        source=""
        s=it.find("source")
        if s is not None and s.text: source=s.text.strip()
        out.append({"title":title,"url":link,"source":source,"published":pub})
    return out

class PExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_p=0; self.buf=[]; self.paras=[]
        self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","svg"): self.skip+=1
        if tag=="p" and not self.skip:
            self.in_p+=1; self.buf=[]
    def handle_endtag(self, tag):
        if tag=="p" and self.in_p and not self.skip:
            txt=re.sub(r"\s+"," "," ".join(self.buf)).strip()
            if len(txt)>=50: self.paras.append(txt)
            self.in_p=max(0,self.in_p-1); self.buf=[]
        if tag in ("script","style","noscript","svg") and self.skip: self.skip-=1
    def handle_data(self, data):
        if self.in_p and not self.skip: self.buf.append(data)

def article_text(url):
    try:
        raw, final, headers=fetch(url, timeout=15)
        ctype=(headers.get("Content-Type") or "").lower()
        if "html" not in ctype and b"<html" not in raw[:500].lower():
            return "", final
        txt=raw.decode("utf-8","replace")
        p=PExtractor(); p.feed(txt)
        body=" ".join(p.paras)
        return body[:25000], final
    except Exception:
        return "", url

def sentence_summary(text, title):
    text=html.unescape(re.sub(r"\s+"," ",text or "")).strip()
    if not text:
        return title.strip()
    # remove common page noise
    text=re.sub(r"(Copyright|All rights reserved|무단전재|재배포 금지).*?$","",text,flags=re.I)
    text=text.replace("다. ", "다.\n")
    sents=re.split(r'\n+|(?<=[.!?。])\s+', text)
    keep=[]
    seen=set()
    for s in sents:
        s=s.strip()
        if len(s)<45 or len(s)>360: continue
        key=re.sub(r"\W+","",s.lower())[:120]
        if not key or key in seen: continue
        seen.add(key); keep.append(s)
        if len(keep)>=3: break
    if not keep:
        return text[:420] + ("…" if len(text)>420 else "")
    return " ".join(keep)

def norm_title(s):
    s=re.sub(r"\s+"," ",html.unescape(s or "")).strip()
    s=re.sub(r"\s*[-–—]\s*[^-–—]{2,40}$","",s).strip()
    return s

def dedupe(items):
    out=[]; keys=set()
    for x in items:
        t=norm_title(x.get("title",""))
        if not t: continue
        k=re.sub(r"[^0-9a-z가-힣]+","",t.lower())[:100]
        if k in keys: continue
        keys.add(k); x["title"]=t; out.append(x)
    return out

def load_previous(key):
    if not OUT.exists(): return {}
    try:
        pkg=json.loads(OUT.read_text(encoding="utf-8"))
        iv=base64.b64decode(pkg["iv"]); ct=base64.b64decode(pkg["ciphertext"])
        plain=AESGCM(key).decrypt(iv,ct,None)
        return json.loads(plain.decode("utf-8"))
    except Exception:
        return {}

def encrypt_payload(data,key):
    iv=os.urandom(12)
    plain=json.dumps(data,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    ct=AESGCM(key).encrypt(iv,plain,None)
    return {"v":1,"alg":"AES-256-GCM","iv":base64.b64encode(iv).decode(),"ciphertext":base64.b64encode(ct).decode()}

def main():
    key_b64=os.environ.get("NEWS_DATA_KEY_B64","").strip()
    if not key_b64:
        raise SystemExit("NEWS_DATA_KEY_B64 is required")
    key=base64.b64decode(key_b64)
    if len(key)!=32: raise SystemExit("NEWS_DATA_KEY_B64 must decode to exactly 32 bytes")

    previous=load_previous(key)
    assets_out={}
    now=datetime.now(timezone.utc)

    for asset_key,cfg in ASSETS.items():
        candidates=[]
        for q in cfg["queries"]:
            try:
                candidates += google_rss_search(q)
            except Exception as e:
                print(f"[WARN] RSS {asset_key}: {e}")

        # Google News RSS가 전부 실패했을 때만 GDELT를 보조적으로 사용
        if not candidates:
            for q in cfg["queries"]:
                try:
                    candidates += gdelt_search(q)
                except Exception as e:
                    print(f"[WARN] GDELT {asset_key}: {e}")

        candidates=dedupe(candidates)
        enriched=[]
        for c in candidates[:8]:
            dt=parse_dt(c.get("published",""))
            if dt and (now-dt).days > LOOKBACK_DAYS+2: continue
            text,final=article_text(c.get("url",""))
            summary=sentence_summary(text,c["title"])
            enriched.append({
                "title":c["title"],
                "source":c.get("source",""),
                "published":dt.isoformat() if dt else c.get("published",""),
                "url":final or c.get("url",""),
                "summary":summary
            })
            if len(enriched)>=MAX_ITEMS: break

        if not enriched:
            enriched=((previous.get("assets",{}).get(asset_key,{}) or {}).get("items") or [])

        assets_out[asset_key]={"label":cfg["label"],"items":enriched[:MAX_ITEMS]}

    payload={
        "generated_at":now.isoformat(),
        "lookback_days":LOOKBACK_DAYS,
        "source_mode":"GDELT + Google News RSS fallback; extractive summary",
        "assets":assets_out
    }
    OUT.write_text(json.dumps(encrypt_payload(payload,key),ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"updated {OUT}")

if __name__=="__main__":
    main()
