#!/usr/bin/env python3
"""
猫耳FM 广播剧下载器
用法：python3 download.py <drama_id>

给定 drama_id，下载该剧的全部信息：
  - 剧集元数据（meta.json）、目录（README.md）
  - 剧封面
  - 每集 info.json、封面、音频（.m4a）、字幕（subtitle.json）、弹幕（danmaku.json）、配图（pics）
"""

import sys
import json
import re
import hmac
import hashlib
import base64
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─── 配置 ────────────────────────────────────────────────────────────────────

APPSECRET = ""

COOKIES = {
    "token": "",
    "equip_id": "",
    "buvid": "",
    "device_token": "",
}


BASE_HEADERS = {
    "Host": "app.missevan.com",
    "User-Agent": "MissEvanApp/6.4.8 (Android;16;Redmi)",
    "channel": "missevan_google",
    "Accept": "application/json",
    "bili-bridge-engine": "cronet",
}

DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7632.110 Mobile Safari/537.36"
}

API_BASE = "https://app.missevan.com"

# ─── 签名 ────────────────────────────────────────────────────────────────────

def _sign(method: str, full_url: str) -> dict:
    """
    生成带签名的请求头。
    full_url 可带 query string。
    """
    parts = full_url.split("?", 1)
    raw_path = parts[0]
    qs = parts[1] if len(parts) > 1 else ""

    encoded_url = urllib.parse.quote(raw_path)  # safe='/' by default
    equip_id = COOKIES["equip_id"]
    token = COOKIES.get("token")

    now = datetime.now(timezone.utc)
    x_m_date = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    x_m_nonce = str(uuid.uuid4())

    lines = [
        method,
        encoded_url,
        qs,
        "equip_id:" + equip_id,
    ]
    if token:
        lines.append("token:" + token)
    lines.append("x-m-date:" + x_m_date)
    lines.append("x-m-nonce:" + x_m_nonce)

    data = "\n".join(lines) + "\n"
    signature = base64.b64encode(
        hmac.new(APPSECRET.encode("utf-8"), data.encode("utf-8"), digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    return {
        **BASE_HEADERS,
        "Authorization": f"MissEvan {signature}",
        "X-M-Date": x_m_date,
        "X-M-Nonce": x_m_nonce,
    }


def api_get(path: str, params: dict = None) -> dict:
    """签名并 GET 一个 API 接口，返回解析后的 JSON dict。"""
    if params:
        qs = urllib.parse.urlencode(params)
        full_url = f"{API_BASE}{path}?{qs}"
    else:
        full_url = f"{API_BASE}{path}"
    headers = _sign("GET", full_url)
    resp = requests.get(full_url, headers=headers, cookies=COOKIES, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─── 下载辅助 ─────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    """去掉文件名中的非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """流式下载任意 URL 到 dest，失败自动重试最多 3 次，返回是否成功。"""
    if dest.exists():
        print(f"  [skip] {dest.name} 已存在")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, stream=True, headers=DOWNLOAD_HEADERS, timeout=60)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            size_kb = dest.stat().st_size / 1024
            print(f"  [ok]   {desc or dest.name} ({size_kb:.0f} KB)")
            return True
        except Exception as e:
            if dest.exists():
                dest.unlink()
            if attempt < 3:
                print(f"  [retry {attempt}/3] {desc or dest.name}: {e}")
            else:
                print(f"  [err]  {desc or dest.name}: {e}")
    return False


def download_audio(audio_urls: list, dest: Path) -> bool:
    """下载第一个（最高质量）音频直链。"""
    return download_file(audio_urls[0], dest, "音频") if audio_urls else False

def fetch_danmaku(sound_id: int):
    """通过 /sound/get-dm 接口获取弹幕，返回原始响应数据（dict），失败返回 None。"""
    data = api_get("/sound/get-dm", {"sound_id": sound_id})
    return data if data.get("success") else None


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def get_drama_detail(drama_id: int) -> dict:
    data = api_get("/drama/drama-detail", {"drama_id": drama_id, "persona_id": 3})
    if not data.get("success"):
        raise RuntimeError(f"drama-detail 请求失败: {data}")
    return data["info"]


def get_sound_detail(sound_id: int) -> dict:
    data = api_get("/sound/sound", {"sound_id": sound_id})
    if not data.get("success"):
        raise RuntimeError(f"sound 请求失败: {data}")
    return data["info"]


def best_audio_urls(info: dict) -> list:
    """从 sound info 中收集所有可能的音频直链（按优先级排列，去重）。"""
    seen = set()
    urls = []

    def _add(u):
        if u and u.startswith("http") and u not in seen:
            seen.add(u)
            urls.append(u)

    # 优先最高码率列表（多 CDN 备用）
    for key in ("soundurl_list", "soundurl_128_list", "soundurl_64_list", "soundurl_32_list"):
        for u in (info.get(key) or []):
            _add(u)
    # 再加单 URL 字段
    for key in ("soundurl", "soundurl_128", "soundurl_64", "soundurl_32"):
        _add(info.get(key))
    return urls


def download_drama(drama_id: int, out_root: str = ".") -> None:
    print(f"=== 获取剧集信息 drama_id={drama_id} ===")
    info = get_drama_detail(drama_id)
    drama = info["drama"]
    episodes_data = info["episodes"]  # ft / music / episode

    drama_name = sanitize(drama["name"])
    out_dir = Path(out_root) / f"{drama_name}_{drama_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {out_dir}")

    # ── 1. 保存元数据 ─────────────────────────────────────────────────────
    meta_path = out_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"[ok] 元数据 -> meta.json")

    # ── 2. 封面 ───────────────────────────────────────────────────────────
    cover_url = drama.get("cover", "")
    if cover_url:
        ext = cover_url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
        download_file(cover_url, out_dir / f"cover.{ext}", "封面")

    # ── 3. 所有分集（episode / ft / music 合并处理）────────────────────
    all_episodes = (
        episodes_data.get("episode", [])
        + episodes_data.get("ft", [])
        + episodes_data.get("music", [])
    )
    total = len(all_episodes)
    print(f"\n共 {total} 集，开始逐集下载...\n")

    for idx, ep in enumerate(all_episodes, 1):
        sound_id = ep.get("sound_id") or ep.get("id")
        ep_name = sanitize(ep.get("name", f"ep{sound_id}"))
        order_str = f"{idx:03d}"
        ep_dir = out_dir / f"{order_str}_{ep_name}"
        ep_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx}/{total}] {ep_name}  (sound_id={sound_id})")

        # 3a. 获取单集详细信息（含音频直链、字幕等）
        try:
            sinfo = get_sound_detail(sound_id)
        except Exception as e:
            print(f"  [err] 获取单集信息失败: {e}")
            continue

        # 3b. 保存单集元数据
        with open(ep_dir / "info.json", "w", encoding="utf-8") as f:
            json.dump(sinfo, f, ensure_ascii=False, indent=2)

        # 3c. 封面
        fc = sinfo.get("front_cover") or ep.get("front_cover")
        if fc:
            ext = fc.rsplit(".", 1)[-1].split("?")[0] or "jpg"
            download_file(fc, ep_dir / f"cover.{ext}", "单集封面")

        # 3d. 音频
        audio_urls = best_audio_urls(sinfo)
        if audio_urls:
            download_audio(audio_urls, ep_dir / "audio.m4a")
        else:
            print("  [warn] 未找到音频直链")

        # 3e. 视频（优先取 status=1 的最高质量）
        if sinfo.get("video"):
            resources = (sinfo.get("video_info") or {}).get("resources", [])
            valid = [r for r in resources if r.get("status") == 1 and r.get("url")]
            if valid:
                best = valid[0]
                ext = best["url"].split("?")[0].rsplit(".", 1)[-1] or "mp4"
                vdesc = f"视频 {best.get('short_name', '')}"
                download_file(best["url"], ep_dir / f"video.{ext}", vdesc)
            else:
                print("  [warn] 有 video 标记但未找到可用视频资源")

        # 3f. 字幕（直接保存原始 JSON）
        sub_url = sinfo.get("subtitle_url", "")
        if sub_url:
            download_file(sub_url, ep_dir / "subtitle.json", "字幕")

        # 3g. 弹幕（保存原始响应 JSON）
        try:
            dm = fetch_danmaku(sound_id)
            if dm:
                with open(ep_dir / "danmaku.json", "w", encoding="utf-8") as f:
                    json.dump(dm, f, ensure_ascii=False, indent=2)
                print(f"  [ok]   弹幕 -> danmaku.json")
        except Exception as e:
            print(f"  [warn] 弹幕获取失败: {e}")

        # 3h. 配图（按 img_url 去重）
        seen_urls = set()
        pi = 0
        for pic in sinfo.get("pics", []):
            img_url = pic.get("img_url", "")
            if not img_url or img_url in seen_urls:
                continue
            seen_urls.add(img_url)
            ext = img_url.rsplit(".", 1)[-1].split("?")[0] or "jpg"
            download_file(img_url, ep_dir / f"pic_{pi:02d}.{ext}", f"配图{pi}")
            pi += 1

        print()

    # ── 4. 生成 README ────────────────────────────────────────────────────
    try:
        from gen_readme import gen_readme
        gen_readme(out_dir)
    except Exception as e:
        print(f"[warn] README 生成失败: {e}")

    print(f"\n=== 下载完成 -> {out_dir} ===")


# ─── 入口 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 download.py <drama_id> [输出目录]")
        sys.exit(1)
    drama_id = int(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else "."
    download_drama(drama_id, out)
