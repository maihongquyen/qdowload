#!/usr/bin/env python3
import argparse
import hashlib
import hmac as hmac_lib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("\033[91m[!] Thieu: pip install requests\033[0m")
    sys.exit(1)

try:
    from PIL import Image as _PIL_Image
    PILLOW_OK = True
except ImportError:
    PILLOW_OK = False

# =============================================================================
# ANSI COLORS
# =============================================================================

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"

    # Foreground
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    PURPLE = "\033[95m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    GRAY   = "\033[90m"

    # Background accents
    BG_BLUE   = "\033[44m"
    BG_GREEN  = "\033[42m"
    BG_RED    = "\033[41m"
    BG_PURPLE = "\033[45m"

def ok(msg):   return "{}✓  {}{}".format(C.GREEN,  msg, C.RESET)
def err(msg):  return "{}✗  {}{}".format(C.RED,    msg, C.RESET)
def warn(msg): return "{}⚠  {}{}".format(C.YELLOW, msg, C.RESET)
def info(msg): return "{}›  {}{}".format(C.CYAN,   msg, C.RESET)
def dim(msg):  return "{}{}{}".format(C.GRAY, msg, C.RESET)
def bold(msg): return "{}{}{}".format(C.BOLD, msg, C.RESET)

def hdr(title, width=62):
    inner = " {} ".format(title)
    pad   = max(0, width - len(inner) - 2)
    l, r  = pad // 2, pad - pad // 2
    return ("{}{}{} {}{}{}{} {}{}".format(
        C.BG_PURPLE, C.WHITE, C.BOLD,
        "─"*l, inner, "─"*r,
        C.RESET, C.PURPLE, C.RESET))

def sep(width=62, char="─", color=C.GRAY):
    return "{}{}{}".format(color, char*width, C.RESET)

# =============================================================================
# CAU HINH
# =============================================================================

COS_BUCKET          = "aovcamp-h5-1254801811"
COS_REGION          = "ap-singapore"
COS_HOST            = "{}.cos.{}.myqcloud.com".format(COS_BUCKET, COS_REGION)
CDN_BASE            = "https://kg-camp.mobagarena.com"
API_BASE            = "https://kgvn-api.mobagarena.com"
IMAGE_EXTS          = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}
DEFAULT_HAR         = "0919.har"
OFFICIAL_STICKER_ID = "190"
NAMEPLATE_ID        = "49"
NAMEPLATE_PICURL    = "https://kg-camp.mobagarena.com/manage/flowborn_official/ZeoMxjHs.png"
MAX_MEDIA_PER_ACC   = 6

# Delay (giay) giua moi poster thread de tranh -1999 frequency limited
POSTER_STAGGER      = 3.6
# Delay giua cac vong lap
ROUND_DELAY         = 3.0
# Delay khoi dong moi acc thread
ACC_STAGGER         = 2.0

# ROLE_CONFIG: key = (main_job, gender)
ROLE_CONFIG = {
    (1,1): {"label":"Assassin Nam"},
    (1,2): {"label":"Assassin Nu"},
    (2,1): {"label":"Tank Nam"},
    (2,2): {"label":"Tank Nu"},
    (3,1): {"label":"Support Nam"},
    (3,2): {"label":"Support Nu"},
    (4,1): {"label":"Mid Nam",
            "baseInfo_id":"62",
            "baseInfo_picUrl": CDN_BASE+"/manage/flowborn_official/5fXAjyuq.png"},
    (4,2): {"label":"Mid Nu",
            "baseInfo_id":"63",
            "baseInfo_picUrl": CDN_BASE+"/manage/flowborn_official/5fXAjyuq.png"},
    (5,1): {"label":"Ad Nam",
            "baseInfo_id":"32",
            "baseInfo_picUrl": CDN_BASE+"/manage/flowborn_official/Pd7zTH2f.png"},
    (5,2): {"label":"Ad Nu",
            "baseInfo_id":"33",
            "baseInfo_picUrl": CDN_BASE+"/manage/flowborn_official/Pd7zTH2f.png"},
    (6,1): {"label":"Jungle Nam"},
    (6,2): {"label":"Jungle Nu"},
}

FIXED_HEADERS = {
    "camp-source":        "AOV-CAMP",
    "msdk-gameid":        "1137",
    "camp-authtype":      "msdk",
    "areaid":             "1",
    "msdk-os":            "1",
    "logicworldid":       "1011",
    "aov-language":       "VN",
    "msdk-channelid":     "10",
    "aov-region":         "1137",
    "origin":             "https://kgvn-camp.mobagarena.com",
    "x-requested-with":   "com.garena.game.kgvn",
    "referer":            "https://kgvn-camp.mobagarena.com/",
    "sec-ch-ua":          '"Chromium";v="146", "Not-A.Brand";v="24", "Android WebView";v="146"',
    "sec-ch-ua-mobile":   "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-site":     "same-site",
    "sec-fetch-mode":     "cors",
    "sec-fetch-dest":     "empty",
    "accept":             "*/*",
    "accept-language":    "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "accept-encoding":    "gzip, deflate, br, zstd",
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 15; SM-A165F Build/AP3A.240905.015.A2; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/146.0.7680.177 "
        "Mobile Safari/537.36 MSDK/5.36.000 mQQAppId/1105779914 "
        "mWXAppId/wx7a814e3ceeda8320 mGameId/1137 MSDKdeviceId/disable"
    ),
}

_print_lock = threading.Lock()
def tprint(msg):
    with _print_lock:
        print(msg, flush=True)

# =============================================================================
# UTILS
# =============================================================================

def gen_traceparent():
    return "00-{}-{}-01".format(os.urandom(16).hex(), os.urandom(8).hex())

def check_connectivity():
    for host in ["kgvn-api.mobagarena.com", "8.8.8.8"]:
        try:
            socket.setdefaulttimeout(5)
            socket.getaddrinfo(host, 443)
            return True
        except socket.gaierror:
            continue
    return False

def make_session():
    s = requests.Session()
    r = Retry(total=3, backoff_factor=1.5,
              status_forcelist=[500,502,503,504],
              allowed_methods=["POST","PUT","GET"])
    a = HTTPAdapter(max_retries=r)
    s.mount("https://", a); s.mount("http://", a)
    return s

def ask_choice(prompt, options):
    print("\n" + "{}{}{}".format(C.CYAN, prompt, C.RESET))
    for k, v in options.items():
        print("    {}[{}]{} {}".format(C.YELLOW+C.BOLD, k, C.RESET, v))
    while True:
        try:
            c = input("    {}Chon: {}".format(C.PURPLE, C.RESET)).strip()
            if c in options:
                return c
            print(warn("Nhap: " + " / ".join(options.keys())))
        except KeyboardInterrupt:
            print("\n" + err("Huy")); sys.exit(0)

def cinput(prompt):
    """Input co mau."""
    try:
        return input("{}{}{}".format(C.PURPLE, prompt, C.RESET)).strip()
    except KeyboardInterrupt:
        print("\n" + err("Huy")); sys.exit(0)

def has_ffmpeg():
    try:
        subprocess.run(["ffmpeg","-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def countdown(msg, secs):
    """Hien thi dem nguoc co mau."""
    for i in range(int(secs), 0, -1):
        tprint("{}  {} {}{}s...{}".format(
            C.GRAY, msg, C.YELLOW, i, C.RESET))
        time.sleep(1)

# =============================================================================
# COS SIGNING
# =============================================================================

def _hmac_sha1(key, msg):
    return hmac_lib.new(key, msg.encode(), hashlib.sha1).hexdigest()

def build_cos_auth(sid, skey, method, pathname, clen):
    now   = int(time.time())
    end   = now + 86400
    kt    = "{};{}".format(now, end)
    sk    = _hmac_sha1(skey.encode(), kt)
    hh    = "content-length={}&host={}".format(clen, COS_HOST)
    hs    = "{}\n{}\n\n{}\n".format(method.lower(), pathname, hh)
    hhttp = hashlib.sha1(hs.encode()).hexdigest()
    s2s   = "sha1\n{}\n{}\n".format(kt, hhttp)
    sig   = _hmac_sha1(sk.encode(), s2s)
    return ("q-sign-algorithm=sha1&q-ak={}"
            "&q-sign-time={}&q-key-time={}"
            "&q-header-list=content-length;host&q-url-param-list="
            "&q-signature={}").format(sid, kt, kt, sig)

# =============================================================================
# PARSE HAR
# =============================================================================

def parse_har(har_path):
    """
    Tra ve: (auth_token, user_path, main_job, gender, baseInfo_raw)
    Uu tien: getpostereditinfo RESPONSE > save* REQUEST > default
    """
    with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
        har = json.load(f)

    auth_token = None
    user_path  = None
    main_job   = 5
    gender     = 2
    bi_raw     = {}

    for entry in har["log"]["entries"]:
        if "getpostereditinfo" not in entry["request"]["url"]:
            continue
        try:
            body = json.loads(
                entry.get("response",{}).get("content",{}).get("text","{}"))
            bi = body.get("data",{}).get("picInfo",{}).get("baseInfo",{})
            if bi:
                main_job = int(bi.get("mainJob", main_job))
                gender   = int(bi.get("gender",  gender))
                bi_raw   = bi
        except Exception:
            pass

    for entry in har["log"]["entries"]:
        req = entry["request"]
        url = req["url"]

        if "kgvn-api.mobagarena.com" in url and not auth_token:
            hdrs = {h["name"].lower(): h["value"]
                    for h in req.get("headers",[])}
            if "msdk-itopencodeparam" in hdrs:
                auth_token = hdrs["msdk-itopencodeparam"]

        if req["method"] == "PUT" and COS_HOST in url and not user_path:
            path  = url.split(COS_HOST)[1].split("?")[0]
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                user_path = "/" + "/".join(parts[:3]) + "/"

        if not bi_raw and any(
            k in url for k in ("saveposter","savepostereditinfo")
        ):
            try:
                body = json.loads(req.get("postData",{}).get("text","{}"))
                bi   = body.get("picInfo",{}).get("baseInfo",{})
                if bi:
                    main_job = int(bi.get("mainJob", main_job))
                    gender   = int(bi.get("gender",  gender))
                    bi_raw   = bi
                elif "mainJob" in body:
                    main_job = int(body["mainJob"])
            except Exception:
                pass

    return auth_token, user_path, main_job, gender, bi_raw

def get_role_label(mj, gdr):
    return ROLE_CONFIG.get((mj,gdr),{}).get("label",
           "Job{} G{}".format(mj,gdr))

def role_color(mj, gdr):
    """Mau theo vai tro."""
    colors = {4: C.CYAN, 5: C.YELLOW, 1: C.RED,
              2: C.BLUE, 3: C.GREEN,  6: C.PURPLE}
    return colors.get(mj, C.WHITE)

# =============================================================================
# MEDIA PROCESSING
# =============================================================================

def prepare_media(file_path):
    """
    Xu ly media truoc khi upload.
    Tra ve dict:
      png_bytes  : bytes PNG de server render (bat buoc)
      anim_bytes : bytes GIF (None neu khong phai GIF/MP4)
      anim_ext   : "gif" | None
      label      : mo ta ngan
      name       : ten file goc
    """
    file_path = Path(file_path)
    ext       = file_path.suffix.lower()
    raw       = file_path.read_bytes()

    # ---- JPG / PNG / WEBP ---------------------------------------------------
    if ext in (".jpg",".jpeg",".png",".webp"):
        return {
            "png_bytes":  raw,
            "anim_bytes": None,
            "anim_ext":   None,
            "label":      "{} {:,}B".format(ext.upper().lstrip("."), len(raw)),
            "name":       file_path.name,
        }

    # ---- GIF ----------------------------------------------------------------
    if ext == ".gif":
        if not PILLOW_OK:
            print(err("GIF can Pillow: pip install Pillow")); sys.exit(1)
        try:
            gif = _PIL_Image.open(io.BytesIO(raw))
            gif.seek(0)
            buf = io.BytesIO()
            gif.convert("RGBA").save(buf, format="PNG")
            png_b = buf.getvalue()
            print(info("    GIF: frame1→PNG {:,}B  +  GIF goc {:,}B".format(
                len(png_b), len(raw))))
            return {
                "png_bytes":  png_b,
                "anim_bytes": raw,
                "anim_ext":   "gif",
                "label":      "GIF {:,}B anim".format(len(raw)),
                "name":       file_path.name,
            }
        except Exception as e:
            print(err("Loi GIF: " + str(e))); sys.exit(1)

    # ---- MP4 ----------------------------------------------------------------
    if ext == ".mp4":
        if not has_ffmpeg():
            print(err("MP4 can ffmpeg: pkg install ffmpeg")); sys.exit(1)
        tmp_mp4 = tempfile.mktemp(suffix=".mp4")
        tmp_gif = tempfile.mktemp(suffix=".gif")
        tmp_png = tempfile.mktemp(suffix=".png")
        try:
            with open(tmp_mp4,"wb") as f: f.write(raw)
            print(info("    MP4 → GIF (fps=10 scale=320)..."))
            subprocess.run(
                ["ffmpeg","-i",tmp_mp4,
                 "-vf","fps=10,scale=320:-1:flags=lanczos",
                 "-loop","0", tmp_gif, "-y"],
                capture_output=True, check=True
            )
            with open(tmp_gif,"rb") as f: gif_b = f.read()
            subprocess.run(
                ["ffmpeg","-i",tmp_gif,"-vframes","1",
                 "-f","image2",tmp_png,"-y"],
                capture_output=True, check=True
            )
            with open(tmp_png,"rb") as f: png_b = f.read()
            for fp in [tmp_mp4,tmp_gif,tmp_png]:
                try: os.unlink(fp)
                except: pass
            print(info("    PNG render {:,}B  GIF anim {:,}B".format(
                len(png_b), len(gif_b))))
            return {
                "png_bytes":  png_b,
                "anim_bytes": gif_b,
                "anim_ext":   "gif",
                "label":      "MP4→GIF {:,}B anim".format(len(gif_b)),
                "name":       file_path.name,
            }
        except subprocess.CalledProcessError as e:
            print(err("ffmpeg that bai: " + str(e))); sys.exit(1)
        except Exception as e:
            print(err("Loi MP4: " + str(e))); sys.exit(1)

    print(err("Dinh dang khong ho tro: " + ext)); sys.exit(1)

# =============================================================================
# SCAN FILES
# =============================================================================

def scan_media(directory):
    files = sorted([
        p for p in Path(directory).iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ])
    if not files:
        print(err("Khong tim thay media trong: " + directory))
        sys.exit(1)
    return files

def find_har_files(directory="."):
    return sorted(Path(directory).glob("*.har"))

# =============================================================================
# API HELPERS
# =============================================================================

def api_post(session, endpoint, payload, auth_token,
             retry_on_code1=False, max_retries=3, delay=3.0):
    hdrs = dict(FIXED_HEADERS)
    hdrs["content-type"]         = "application/json"
    hdrs["msdk-itopencodeparam"] = auth_token
    hdrs["traceparent"]          = gen_traceparent()
    hdrs["priority"]             = "u=1, i"
    data = {}
    for attempt in range(max_retries):
        try:
            r = session.post(API_BASE+endpoint,
                             json=payload, headers=hdrs, timeout=25)
            r.raise_for_status()
            data = r.json()
            if retry_on_code1 and data.get("code") == 1:
                wait = delay*(attempt+1)
                tprint(warn("  code=1 thu lai {}s [{}/{}]".format(
                    int(wait), attempt+1, max_retries)))
                time.sleep(wait); continue
            return data
        except requests.exceptions.ConnectionError as e:
            tprint(err("Loi ket noi: "+str(e)))
            return {"code":-1,"msg":str(e)}
        except requests.exceptions.Timeout:
            if attempt < max_retries-1:
                tprint(warn("  Timeout [{}/{}] thu lai...".format(
                    attempt+1, max_retries)))
                time.sleep(delay)
            else:
                return {"code":-1,"msg":"timeout"}
    return data

def cos_put(session, url, data, headers, label=""):
    for attempt in range(3):
        try:
            resp = session.put(url, data=data, headers=headers, timeout=60)
            if resp.status_code == 200:
                return resp
            tprint(warn("  COS {} [{}]: {}".format(
                label, resp.status_code, resp.text[:120])))
            if attempt < 2: time.sleep(2)
        except requests.exceptions.ConnectionError as e:
            tprint(err("COS loi: "+str(e))); return None
    return resp



# =============================================================================
# BUILD picInfo
# =============================================================================

def build_pic_info(pic_info_raw, bi_har, sticker_url,
                   main_job, gender,
                   nameplate_text=None, nameplate_picurl=None):
    bg  = pic_info_raw.get("bg",{})
    bpi = pic_info_raw.get("baseInfo",{})
    cfg = ROLE_CONFIG.get((main_job,gender),{})
    bi  = {
        "id":       (bi_har.get("id")
                     or bpi.get("id")
                     or cfg.get("baseInfo_id","32")),
        "gender":   int(bi_har.get("gender")    or bpi.get("gender",    gender)),
        "mainJob":  int(bi_har.get("mainJob")   or bpi.get("mainJob",   main_job)),
        "picUrl":   (bi_har.get("picUrl")
                     or bpi.get("picUrl")
                     or cfg.get("baseInfo_picUrl",
                                CDN_BASE+"/manage/flowborn_official/Pd7zTH2f.png")),
        "skinColor":int(bi_har.get("skinColor") or bpi.get("skinColor",1)),
    }
    result = {
        "bg":{"id":bg.get("id","30"),
              "picUrl":bg.get("picUrl",
                              CDN_BASE+"/manage/flowborn_official/4uxOQChv.png")},
        "baseInfo": bi,
        "stickerList": [{
            "id":     OFFICIAL_STICKER_ID,
            "picUrl": sticker_url,
            "width":  484.1990950226244,
            "height": 484.1990950226244,
            "posX":   -124.24919457013574,
            "posY":   -76.04248388393627,
            "rotate": 0, "source":1, "type":1,
        }],
    }
    if nameplate_text:
        result["nameplateList"] = [{
            "id": NAMEPLATE_ID,
            "picUrl": nameplate_picurl or NAMEPLATE_PICURL,
            "content": nameplate_text,
            "font":0,"fontSize":0,"textLength":0,
            "width":256,"height":59.91396199095023,
            "posX":0,"posY":204.82141004190632,"rotate":0,
        }]
    return result

# =============================================================================
# COMPOSITE NAMEPLATE
# =============================================================================

def composite_nameplate(png_bytes, name_text, session):
    if not PILLOW_OK:
        return png_bytes
    from PIL import ImageDraw, ImageFont
    NP_Y = 204.82/264.73; NP_H = 59.91/264.73
    img  = _PIL_Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    W, H = img.size
    nh   = max(40, int(H*NP_H))
    ny   = H - nh
    tmpl = None
    try:
        resp = session.get(NAMEPLATE_PICURL, timeout=10)
        if resp.status_code == 200:
            tmpl = _PIL_Image.open(io.BytesIO(resp.content)).convert("RGBA")
            tmpl = tmpl.resize((W,nh), _PIL_Image.LANCZOS)
    except Exception:
        pass
    if tmpl is None:
        tmpl = _PIL_Image.new("RGBA",(W,nh),(0,0,0,0))
        dt   = ImageDraw.Draw(tmpl)
        for i in range(nh):
            dt.line([(0,i),(W,i)],
                    fill=(int(80+40*i/nh),int(60+40*i/nh),int(180+40*i/nh),200))
    ov = _PIL_Image.new("RGBA",(W,H),(0,0,0,0))
    ov.paste(tmpl,(0,ny))
    img  = _PIL_Image.alpha_composite(img,ov)
    draw = ImageDraw.Draw(img)
    font = None
    for fp in ["/system/fonts/NotoSansCJK-Regular.ttc",
               "/system/fonts/NotoSans-Regular.ttf",
               "/system/fonts/Roboto-Regular.ttf",
               "/system/fonts/DroidSans.ttf"]:
        try:
            font = ImageFont.truetype(fp, max(16,int(nh*0.52))); break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()
    bb   = draw.textbbox((0,0), name_text, font=font)
    tw,th= bb[2]-bb[0], bb[3]-bb[1]
    tx   = (W-tw)//2
    ty   = ny + (nh-th)//2 - bb[1]
    draw.text((tx+2,ty+2), name_text, font=font, fill=(0,0,0,180))
    draw.text((tx,ty),     name_text, font=font, fill=(255,255,255,255))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()

# =============================================================================
# POSTER WORKER  (1 media / 1 thread)
# =============================================================================

def poster_worker(idx, acc_lbl, auth_token, user_path,
                  main_job, gender, bi_har, creds,
                  media, pic_info_raw, is_share,
                  nameplate_text, nameplate_picurl, results):
    tag     = "{}[{} P{:02d}]{}".format(
        C.BLUE+C.BOLD, acc_lbl[:14], idx, C.RESET)
    session = make_session()

    png_b    = media["png_bytes"]
    anim_b   = media["anim_bytes"]
    anim_ext = media["anim_ext"]
    fname    = media.get("name","?")

    try:
        # A. createposter
        tprint("{} Tao poster {}...".format(tag, dim(fname[:16])))
        r = api_post(session,"/api/game/poster/flowborn/createposter",
                     {},auth_token)
        if r.get("code") != 0:
            tprint("{} {}".format(tag, err("createposter: "+r.get("msg","")[:40])))
            results[idx-1]=(False,"createposter: "+r.get("msg","")[:40]); return
        pid = r["data"]["posterId"]
        tprint("{} PosterID={}{}{}".format(tag, C.YELLOW, pid, C.RESET))
        time.sleep(0.5)

        # B. COS upload
        ck   = "{}{}/1/{}.png".format(user_path, main_job, pid)
        ck_l = "{}{}/1/{}_large.png".format(user_path, main_job, pid)

        def mkhdr(key, buf, ct):
            return {
                "Authorization":        build_cos_auth(
                    creds["tmpSecretId"],creds["tmpSecretKey"],"PUT",key,len(buf)),
                "Content-Type":         ct,
                "Content-Length":       str(len(buf)),
                "Host":                 COS_HOST,
                "x-cos-security-token": creds["token"],
                "Origin":               "https://kgvn-camp.mobagarena.com",
                "Referer":              "https://kgvn-camp.mobagarena.com/",
            }

        r2 = cos_put(session,"https://"+COS_HOST+ck,
                     png_b, mkhdr(ck,png_b,"image/png"), ".png")
        if r2 is None or r2.status_code != 200:
            tprint("{} {}".format(tag, err("COS .png FAIL")))
            results[idx-1]=(False,"COS .png fail"); return
        tprint("{} COS .png {} {:,}B".format(tag, ok("OK"), len(png_b)))

        cos_put(session,"https://"+COS_HOST+ck_l,
                png_b, mkhdr(ck_l,png_b,"image/png"), "_large")

        sticker_url = CDN_BASE + ck

        # GIF/MP4 animation upload (spoof ct: image/png)
        if anim_b is not None and anim_ext:
            ck_a  = "{}{}/1/{}.{}".format(user_path, main_job, pid, anim_ext)
            r_a   = cos_put(session,"https://"+COS_HOST+ck_a,
                            anim_b, mkhdr(ck_a,anim_b,"image/png"),
                            "."+anim_ext)
            if r_a is not None and r_a.status_code == 200:
                sticker_url = CDN_BASE + ck_a
                tprint("{} COS .{} {} {:,}B {}".format(
                    tag, anim_ext, ok("OK"), len(anim_b),
                    dim("(animation)")))
            else:
                tprint("{} {}".format(
                    tag, warn(".{} FAIL → dung .png".format(anim_ext))))

        time.sleep(0.5)

        # C-E. save
        pi = build_pic_info(pic_info_raw, bi_har, sticker_url,
                            main_job, gender,
                            nameplate_text, nameplate_picurl)

        rs = api_post(session,
                      "/api/game/poster/flowborn/savepostereditinfo",
                      {"mainJob":main_job,"picInfo":pi},
                      auth_token,
                      retry_on_code1=True, max_retries=4, delay=4.0)
        tprint("{} editInfo {}".format(
            tag, ok("OK") if rs.get("code")==0 else warn("code={}".format(rs.get("code")))))
        time.sleep(1.5)

        rp = api_post(session,
                      "/api/game/poster/flowborn/saveposter",
                      {"posterId":pid,"isApply":True,"isShare":is_share,
                       "mainJob":main_job,"picInfo":pi,
                       "picUrl":CDN_BASE+user_path},
                      auth_token,
                      retry_on_code1=True, max_retries=4, delay=4.0)

        unavail = rp.get("data",{}).get("unavailableResources",[])
        kind    = "{}GIF{}".format(C.CYAN,C.RESET) if anim_b else "IMG"

        if rp.get("code")==0 and not unavail:
            tprint("{} {} ID={}{}{}  [{}]".format(
                tag, ok("THANH CONG"), C.GREEN, pid, C.RESET, kind))
            results[idx-1]=(True, pid, sticker_url, kind)
        elif rp.get("code")==0:
            tprint("{} {} (co resource bi tu choi)".format(tag, ok("OK")))
            results[idx-1]=(True, pid, sticker_url, kind)
        else:
            tprint("{} {} {}".format(
                tag, err("THAT BAI"), rp.get("msg","")[:40]))
            results[idx-1]=(False,"saveposter: "+rp.get("msg","")[:40])

    except Exception as e:
        tprint("{} {}".format(tag, err("EXCEPTION: "+str(e)[:50])))
        results[idx-1]=(False,"exception: "+str(e)[:40])

# =============================================================================
# ACC WORKER  (1 acc / 1 thread)
# =============================================================================

def acc_worker(acc, media_list, rounds, is_share,
               nameplate_text, nameplate_picurl, mod_mode, acc_results):
    lbl  = acc["label"]
    har  = acc["har"]
    rc   = role_color(acc["main_job"], acc["gender"])

    tprint("\n" + sep(62, "═", C.PURPLE))
    tprint("{}{}  START  {}{}".format(C.PURPLE+C.BOLD, "▶", lbl, C.RESET))
    tprint(sep(62, "═", C.PURPLE))

    auth_token, user_path, main_job, gender, bi_har = parse_har(har)
    if not auth_token or not user_path:
        tprint(err("  [{}] Khong co token/path — bo qua".format(lbl)))
        acc_results[lbl]={"ok":0,"fail":0,"rounds":[]}; return

    tprint("  {}Vai tro : {}{}{}{} (job={} gender={})".format(
        C.GRAY, rc+C.BOLD, get_role_label(main_job,gender),
        C.RESET, C.GRAY, main_job, gender) + C.RESET)
    tprint(dim("  Token   : {}...".format(auth_token[:35])))
    tprint(dim("  COS     : {}".format(user_path)))

    sess = make_session()

    # COS credentials
    tprint(info("  [1/3] COS credentials..."))
    r = api_post(sess,"/api/tool/getcoscredential",
                 {"scene":"FlowbornPoster"},auth_token)
    if r.get("code") != 0:
        tprint(err("  getCos FAIL: {}".format(r)))
        acc_results[lbl]={"ok":0,"fail":0,"rounds":[]}; return
    creds = r["data"]
    tprint(ok("  SecretId: {}...".format(creds["tmpSecretId"][:20])))
    time.sleep(0.5)

    # Poster edit info
    tprint(info("  [2/3] Lay picInfo hien tai..."))
    r = api_post(sess,"/api/game/poster/flowborn/getpostereditinfo",
                 {"mainJob":main_job},auth_token)
    if r.get("code")==0 and r.get("data",{}).get("picInfo"):
        pic_info_raw = r["data"]["picInfo"]
        if not bi_har:
            bi_har = pic_info_raw.get("baseInfo",{})
        tprint(ok("  picInfo OK"))
    else:
        pic_info_raw = {}
        tprint(warn("  Dung cau hinh mac dinh"))
    time.sleep(0.5)

    # Validate nameplate
    np_url = nameplate_picurl
    if mod_mode == "2" and nameplate_text:
        tprint(info("  [3/3] Validate nameplate \"{}\"...".format(nameplate_text)))
        rc2 = api_post(sess,"/api/game/poster/flowborn/textsynccheck",
                       {"text":nameplate_text},auth_token)
        if rc2.get("code") != 0:
            tprint(warn("  Server tu choi ten → bo qua nameplate"))
            nameplate_text = None
        else:
            tprint(ok("  Ten hop le"))
            nr = api_post(sess,"/api/game/poster/flowborn/geteditorresource",
                          {"type":2,"mainJob":main_job,"page":1,"pageSize":20},
                          auth_token)
            if nr.get("code")==0 and nr["data"].get("list"):
                np_url = (nr["data"]["list"][0]
                          .get("nameplate",{})
                          .get("picUrl") or NAMEPLATE_PICURL)

    # Apply composite nameplate
    working_media = []
    for m in media_list:
        if mod_mode == "2" and nameplate_text:
            new_png = composite_nameplate(m["png_bytes"], nameplate_text, sess)
            working_media.append({**m, "png_bytes": new_png})
        else:
            working_media.append(m)

    n_media    = len(working_media)
    total_ok   = total_fail = 0
    round_logs = []

    for rnd in range(1, rounds+1):
        tprint("")
        tprint("{}  [{}] Vong {:02d}/{:02d}  —  {} media song song{}".format(
            C.CYAN+C.BOLD, lbl[:16], rnd, rounds, n_media, C.RESET))

        results = [None]*n_media
        threads = []
        for i, m in enumerate(working_media, 1):
            t = threading.Thread(
                target=poster_worker,
                args=(i, lbl, auth_token, user_path,
                      main_job, gender, bi_har, creds,
                      m, pic_info_raw, is_share,
                      nameplate_text, np_url, results),
                daemon=True,
            )
            threads.append(t)

        for t in threads:
            t.start()
            # ---- 3.6s stagger giua moi poster de fix -1999 frequency limited ----
            time.sleep(POSTER_STAGGER)

        for t in threads:
            t.join()

        ok_n  = sum(1 for res in results if res and res[0])
        fail_n= n_media - ok_n
        total_ok   += ok_n
        total_fail += fail_n
        round_logs.append((rnd, results))

        summary = "{} OK  {} FAIL".format(
            "{}{}{}".format(C.GREEN, ok_n,   C.RESET),
            "{}{}{}".format(C.RED,   fail_n, C.RESET))
        tprint("  {}[{}] Vong {:02d}: {}{}".format(
            C.BOLD, lbl[:16], rnd, summary, C.RESET))

        if rnd < rounds:
            tprint(dim("  [{}] Nghi {}s truoc vong tiep...".format(
                lbl[:16], ROUND_DELAY)))
            time.sleep(ROUND_DELAY)

    # Tong ket acc
    tprint("")
    tprint("{}┌─ DONE: {} {}".format(C.GREEN+C.BOLD, lbl, C.RESET))
    for rnd, results in round_logs:
        for i, res in enumerate(results,1):
            g = (rnd-1)*n_media+i
            if res and res[0]:
                kind = res[3] if len(res)>3 else "?"
                tprint("{}│{}  V{:02d}#{:02d} {}  [{}]  ID={}".format(
                    C.GREEN, C.RESET, rnd, g, ok("OK"), kind, res[1]))
            else:
                msg = str(res[1])[:35] if res else "?"
                tprint("{}│{}  V{:02d}#{:02d} {}  {}".format(
                    C.GREEN, C.RESET, rnd, g, err("FAIL"), msg))
    tprint("{}└─ OK:{} {}{}{}  FAIL:{} {}{}{}  TONG:{}{}".format(
        C.GREEN,
        C.RESET, C.GREEN+C.BOLD, total_ok,   C.RESET,
        C.RESET, C.RED+C.BOLD,   total_fail, C.RESET,
        C.BOLD, rounds*n_media) + C.RESET)

    acc_results[lbl]={"ok":total_ok,"fail":total_fail,"rounds":round_logs}

# =============================================================================
# BOOST WORKER
# =============================================================================

def boost_worker(acc_lbl, auth_token, poster_id, role_id,
                 count, delay_s, boost_results):
    session = make_session()
    tprint(info("[{}] Boost {}x  delay={}s".format(acc_lbl, count, delay_s)))
    ok_n=fail_n=0
    for i in range(1,count+1):
        rc = api_post(session,
                      "/api/game/poster/flowborn/getposterunusableresource",
                      {"posterId":poster_id,"roleId":role_id},auth_token)
        if rc.get("data",{}).get("unavailableResources"):
            tprint(warn("[{}][{}] Poster bi khoa — dung".format(acc_lbl,i))); break
        r = api_post(session,
                     "/api/game/poster/flowborn/quickapplyposter",
                     {"posterId":poster_id,"roleId":role_id},auth_token)
        if r.get("code")==0:
            ok_n+=1
            tprint(ok("[{}][{}] OK  (tong={})".format(acc_lbl,i,ok_n)))
        else:
            fail_n+=1
            tprint(err("[{}][{}] FAIL  code={}  msg={}".format(
                acc_lbl,i,r.get("code"),r.get("msg",""))))
            if fail_n>=3:
                tprint(warn("[{}] 3 fail lien tiep — dung".format(acc_lbl))); break
        time.sleep(delay_s)
    tprint("{}[{}] Boost xong: {} ok  {} fail{}".format(
        C.BOLD, acc_lbl, ok_n, fail_n, C.RESET))
    boost_results[acc_lbl]={"ok":ok_n,"fail":fail_n}

# =============================================================================
# MAIN
# =============================================================================

def run(har_path_arg, image_dir, rounds_arg):
    # Banner
    print("")
    print("{}{}".format(C.PURPLE, "═"*62))
    print("{}  KGVN Flowborn Poster  ·  Multi-Account Tool v3.4    ".format(
        C.WHITE+C.BOLD))
    print("{}  JPG · PNG · WEBP · GIF · MP4  |  Acc chay song song  ".format(C.CYAN))
    print("{}{}".format(C.PURPLE, "═"*62) + C.RESET)

    print("\n" + info("Kiem tra ket noi..."))
    if not check_connectivity():
        print(err("Khong co ket noi internet!")); sys.exit(1)
    print(ok("Mang OK"))

    # ---- Tim HAR ----
    use_one = (har_path_arg and har_path_arg != DEFAULT_HAR
               and os.path.exists(har_path_arg))
    if use_one:
        har_files = [Path(har_path_arg)]
    else:
        har_files = find_har_files(".")
        if not har_files and os.path.exists(DEFAULT_HAR):
            har_files = [Path(DEFAULT_HAR)]
    har_files = [h for h in har_files if h.exists()]

    if not har_files:
        print(err("Khong tim thay .har nao!")); sys.exit(1)

    # ---- Parse + hien thi ----
    print("\n" + bold("Phan tich {} file HAR:".format(len(har_files))))
    print("  {}{:<28}  {:<22}  {}{}".format(
        C.GRAY, "File", "Vai tro", "Trang thai", C.RESET))
    print("  " + sep(58, "─", C.GRAY))
    acc_info = []
    for idx_h, h in enumerate(har_files, 1):
        tok,upath,mj,gdr,bi = parse_har(str(h))
        role   = get_role_label(mj,gdr)
        rc     = role_color(mj,gdr)
        status = ok("OK") if (tok and upath) else err("THIEU TOKEN/PATH")
        lbl    = "{} [{}]".format(h.stem, role)
        print("  {}{:02d}.{} {:<25}  {}{:<22}{}  {}".format(
            C.YELLOW, idx_h, C.RESET,
            h.name[:25],
            rc+C.BOLD, role, C.RESET,
            status))
        acc_info.append({
            "har":str(h), "token":tok, "user_path":upath,
            "main_job":mj, "gender":gdr, "baseInfo":bi, "label":lbl
        })

    valid = [a for a in acc_info if a["token"] and a["user_path"]]
    if not valid:
        print(err("Khong co acc nao hop le!")); sys.exit(1)

    # ---- Chon acc ----
    selected = valid
    if len(valid) > 1:
        print("")
        print("  {}Nhap 'all' / ENTER = dung TAT CA {} acc{}".format(
            C.CYAN, len(valid), C.RESET))
        print("  {}Nhap STT cach nhau (vd: 1 3) = chon rieng{}".format(
            C.GRAY, C.RESET))
        raw = cinput("  > ")

        if raw and raw.lower() != "all":
            try:
                idxs = [int(x)-1 for x in raw.split()]
                sel  = [acc_info[i] for i in idxs
                        if 0<=i<len(acc_info) and acc_info[i]["token"]]
                if sel: selected = sel
                else: print(warn("Khong hop le → Dung tat ca"))
            except Exception:
                print(warn("Nhap sai → Dung tat ca"))

    n_acc = len(selected)
    print("\n  {} acc se chay {}SONG SONG{}:".format(
        n_acc, C.GREEN+C.BOLD, C.RESET))
    for a in selected:
        rc = role_color(a["main_job"], a["gender"])
        print("    {}●{} {}{}{}".format(
            rc, C.RESET, rc, a["label"], C.RESET))

    # ---- Chuc nang ----
    main_mode = ask_choice(
        "Chon chuc nang:",
        {"1":"{}Mod media poster{} (JPG / PNG / GIF / MP4)".format(
            C.GREEN+C.BOLD, C.RESET),
         "2":"{}Tang luot dung nen{} (Boost)".format(
            C.YELLOW+C.BOLD, C.RESET)}
    )

    # ===========================================================
    # BOOST
    # ===========================================================
    if main_mode == "2":
        print("\n" + bold("Nhap thong tin poster:"))
        poster_id = cinput("  PosterId  : ")
        role_id   = cinput("  RoleId    : ")
        try:
            count = int(cinput("  So lan    : "))
            d     = cinput("  Delay giay [mac dinh 1.0]: ")
            delay_s = float(d) if d else 1.0
        except ValueError:
            print(err("Nhap sai")); sys.exit(1)

        boost_results = {}
        threads = [threading.Thread(
            target=boost_worker,
            args=(a["label"],a["token"],poster_id,role_id,
                  count,delay_s,boost_results),
            daemon=True,
        ) for a in selected]

        print("\n" + bold("Bat dau boost {} acc SONG SONG...".format(n_acc)))
        for t in threads: t.start()
        for t in threads: t.join()

        print("\n" + sep(62, "═", C.PURPLE))
        print("{}  BOOST TONG KET  ({} acc song song){}".format(
            C.WHITE+C.BOLD, n_acc, C.RESET))
        print(sep(62, "─", C.GRAY))
        grand_ok=grand_fail=0
        for lbl,res in boost_results.items():
            print("  {:<32}  {}OK:{:<5}{}  {}FAIL:{}{}".format(
                lbl[:32],
                C.GREEN, res["ok"],   C.RESET,
                C.RED,   res["fail"], C.RESET))
            grand_ok+=res["ok"]; grand_fail+=res["fail"]
        print(sep(62, "─", C.GRAY))
        print("  {}TONG: OK={}  FAIL={}{}".format(
            C.BOLD, grand_ok, grand_fail, C.RESET))
        print(sep(62, "═", C.PURPLE))
        return

    # ===========================================================
    # MOD POSTER
    # ===========================================================

    print("\n" + info("Quet media trong: " + image_dir))
    all_files = scan_media(image_dir)
    print("  Tim thay {} file:".format(len(all_files)))
    TYPE_COLORS = {
        ".jpg":"{}JPG{}".format(C.YELLOW,C.RESET),
        ".jpeg":"{}JPG{}".format(C.YELLOW,C.RESET),
        ".png":"{}PNG{}".format(C.CYAN,C.RESET),
        ".webp":"{}WEBP{}".format(C.CYAN,C.RESET),
        ".gif":"{}GIF{}".format(C.GREEN+C.BOLD,C.RESET),
        ".mp4":"{}MP4{}".format(C.PURPLE+C.BOLD,C.RESET),
    }
    for i,p in enumerate(all_files,1):
        tc = TYPE_COLORS.get(p.suffix.lower(), p.suffix.upper())
        print("  {}[{}]{}  {}  {}  {:.1f} KB".format(
            C.YELLOW, i, C.RESET,
            tc, p.name,
            p.stat().st_size/1024))

    # Phan cong anh
    if len(all_files)==1:
        img_mode="2"
        print("\n" + info("1 file duy nhat → tat ca acc dung chung."))
    else:
        if len(all_files) < n_acc:
            print("\n" + warn("{} file < {} acc — mode 1 se lap vong anh.".format(
                len(all_files), n_acc)))
        img_mode = ask_choice(
            "Che do phan cong media:",
            {"1":"Moi acc {}1 bo rieng{}  (acc1→file1, acc2→file2, ...)".format(
                C.BOLD, C.RESET),
             "2":"Tat ca acc dung {}chung{}  (toi da {} file/acc)".format(
                C.BOLD, C.RESET, MAX_MEDIA_PER_ACC)}
        )

    if img_mode=="1":
        print("\n  Phan cong (rieng):")
        for i,a in enumerate(selected):
            f  = all_files[i % len(all_files)]
            rc = role_color(a["main_job"],a["gender"])
            print("    {}{}{}  →  {}".format(rc, a["label"][:30], C.RESET, f.name))
    else:
        shared = all_files[:MAX_MEDIA_PER_ACC]
        print("\n" + info("Dung chung {} file: {}".format(
            len(shared), ", ".join(p.name for p in shared))))

    # Che do luu
    save_mode = ask_choice(
        "Che do LUU poster:",
        {"1":"{}Luu rieng{}  (chi minh toi dung)".format(C.CYAN,C.RESET),
         "2":"{}Quang truong{}  (moi nguoi thay)".format(C.YELLOW,C.RESET)}
    )
    is_share = (save_mode=="2")

    # Che do MOD
    mod_mode = ask_choice(
        "Che do MOD:",
        {"1":"Chi mod media",
         "2":"Mod media + {}composite ten nhan vat{}  (can Pillow)".format(
             C.CYAN, C.RESET)}
    )
    nameplate_text   = None
    nameplate_picurl = NAMEPLATE_PICURL
    if mod_mode=="2":
        if not PILLOW_OK:
            print(warn("pip install Pillow → Bo qua nameplate."))
            mod_mode="1"
        else:
            nameplate_text = cinput("\n  Ten nhan vat: ")
            if not nameplate_text:
                print(warn("Ten trong → bo qua")); mod_mode="1"

    # So vong
    if rounds_arg:
        rounds = max(1, rounds_arg)
    else:
        raw = cinput("\n  So vong lap (moi vong = {}s stagger/poster, ENTER=1): ".format(
            POSTER_STAGGER))
        try:
            rounds = int(raw) if raw else 1
            rounds = max(1, rounds)
        except ValueError:
            rounds = 1

    if img_mode=="1":
        grand_total = rounds * n_acc
    else:
        imgs_per    = min(len(all_files), MAX_MEDIA_PER_ACC)
        grand_total = rounds * imgs_per * n_acc

    print("\n  {} acc  ×  {} vong  ≈  {}{}{}  poster tong".format(
        n_acc, rounds, C.GREEN+C.BOLD, grand_total, C.RESET))
    print(dim("  Stagger poster: {}s  |  Delay vong: {}s  |  Stagger acc: {}s".format(
        POSTER_STAGGER, ROUND_DELAY, ACC_STAGGER)))

    # Pre-process media
    print("\n" + info("Xu ly media truoc khi chay..."))
    shared_media_list = None
    if img_mode=="2":
        shared_files = all_files[:MAX_MEDIA_PER_ACC]
        shared_media_list = []
        for p in shared_files:
            print(info("  Xu ly: {}".format(p.name)))
            shared_media_list.append(prepare_media(p))

    acc_media_map = {}
    for i,a in enumerate(selected):
        lbl = a["label"]
        if img_mode=="1":
            f = all_files[i % len(all_files)]
            print(info("  {} → {}".format(lbl[:25], f.name)))
            acc_media_map[lbl] = [prepare_media(f)]
        else:
            acc_media_map[lbl] = shared_media_list

    # Confirm
    confirm = cinput("\n  Nhap 'ok' de bat dau, Ctrl+C de huy: ")
    if confirm.lower() != "ok":
        print(err("Huy")); sys.exit(0)

    # ===========================================================
    # SPAWN ACC THREADS — tat ca song song
    # ===========================================================
    acc_results = {}
    threads     = []

    print("\n" + bold("Bat dau {} acc SONG SONG...".format(n_acc)))
    for a in selected:
        t = threading.Thread(
            target=acc_worker,
            args=(a, acc_media_map[a["label"]],
                  rounds, is_share,
                  nameplate_text, nameplate_picurl, mod_mode,
                  acc_results),
            daemon=True,
        )
        threads.append(t)

    for t in threads:
        t.start()
        time.sleep(ACC_STAGGER)   # stagger khoi dong acc

    for t in threads:
        t.join()

    # ===========================================================
    # TONG KET CUOI
    # ===========================================================
    print("")
    print(sep(62, "═", C.PURPLE))
    print("{}  TONG KET  ({} acc song song){}".format(
        C.WHITE+C.BOLD, n_acc, C.RESET))
    print(sep(62, "─", C.GRAY))
    grand_ok=grand_fail=0
    for a in selected:
        res = acc_results.get(a["label"],{"ok":0,"fail":0})
        ok_a,fail_a = res["ok"],res["fail"]
        grand_ok+=ok_a; grand_fail+=fail_a
        rc = role_color(a["main_job"],a["gender"])
        print("  {}{:<30}{}  {}OK:{:<4}{}  {}FAIL:{:<4}{}  TONG:{}".format(
            rc, a["label"][:30], C.RESET,
            C.GREEN, ok_a,   C.RESET,
            C.RED,   fail_a, C.RESET,
            ok_a+fail_a))
    print(sep(62, "─", C.GRAY))
    print("  {}TONG CONG:  OK={}{}{}  FAIL={}{}{}  /  {} poster{}".format(
        C.BOLD,
        C.GREEN, grand_ok,   C.RESET+C.BOLD,
        C.RED,   grand_fail, C.RESET+C.BOLD,
        grand_total, C.RESET))
    print(sep(62, "═", C.PURPLE))
    print("\n  {}Mo game → Flowborn Poster de thay sticker custom!{}\n".format(
        C.CYAN, C.RESET))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="KGVN Flowborn Poster - Multi-Account Tool v3.4",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "TINH NANG:\n"
            "  * JPG / PNG / WEBP / GIF / MP4\n"
            "  * Delay 3.6s stagger fix loi -1999 frequency limited\n"
            "  * Acc chay song song dong thoi\n"
            "  * Tu dong nhan dien vai tro + gioi tinh tu HAR\n"
            "  * Giao dien mau sac\n"
            "\nCAI DAT:\n"
            "  pip install requests Pillow\n"
            "  # MP4: pkg install ffmpeg  hoac  apt install ffmpeg\n"
            "\nVI DU:\n"
            "  python kgvn_multi.py\n"
            "  python kgvn_multi.py --rounds 3\n"
            "  python kgvn_multi.py --dir /sdcard/DCIM\n"
            "  python kgvn_multi.py --har acc1.har\n"
        ),
    )
    ap.add_argument("--har",    default=DEFAULT_HAR)
    ap.add_argument("--dir",    default=".")
    ap.add_argument("--rounds", type=int, default=None)
    args = ap.parse_args()
    run(args.har, args.dir, args.rounds)
