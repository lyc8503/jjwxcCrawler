#!/usr/bin/env python3
"""用法: python3 gen_readme.py <剧集文件夹路径>"""

import sys, json, re
from pathlib import Path
from datetime import datetime


def fmt_dur(ms):
    ms = int(ms)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s = ms // 1000
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_ts(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def strip_html(s):
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def gen_readme(out_dir: Path):
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    d = meta["drama"]
    all_eps = (
        meta["episodes"].get("episode", [])
        + meta["episodes"].get("ft", [])
        + meta["episodes"].get("music", [])
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append(f"# {d['name']}")
    lines.append("")
    lines.append(f"原著：{d.get('author', '')}　出品：{d.get('username', '')}　{d.get('type_name', '')}")
    lines.append(f"上线：{fmt_ts(d.get('create_time', 0))}　最近更新：{fmt_ts(d.get('lastupdate_time', 0))}")
    lines.append(f"标签：{' · '.join(lb['name'] for lb in d.get('labels', []))}")
    lines.append(
        f"价格：{d.get('price', 0)} 钻石　"
        f"播放量：{d.get('view_count', 0):,}　"
        f"订阅：{d.get('subscription_num', 0):,}　"
        f"评论：{d.get('comment_count', 0):,}"
    )
    lines.append(f"drama_id: {d['id']}　下载于 {now}")
    lines.append("")
    lines.append("---")
    lines.append("")

    abstract = strip_html(d.get("abstract", ""))
    if abstract:
        lines.append(abstract)
        lines.append("")
        lines.append("---")
        lines.append("")

    for idx, ep in enumerate(all_eps, 1):
        name     = ep.get("name", "")
        snd      = ep.get("sound_id") or ep.get("id")
        dur      = fmt_dur(ep.get("duration", 0))
        date     = fmt_ts(ep.get("create_time", 0))
        views    = int(ep.get("view_count", 0))
        fav      = 0
        tags     = []
        soundstr = ep.get("soundstr", "")

        ep_dir    = out_dir / f"{idx:03d}_{sanitize(name)}"
        has_audio = (ep_dir / "audio.m4a").exists()
        has_sub   = (ep_dir / "subtitle.json").exists()
        has_dm    = (ep_dir / "danmaku.json").exists()

        info_path = ep_dir / "info.json"
        if info_path.exists():
            try:
                si       = json.loads(info_path.read_text(encoding="utf-8"))
                dur      = fmt_dur(si.get("duration", ep.get("duration", 0)))
                views    = si.get("view_count", views)
                fav      = si.get("favorite_count", 0)
                tags     = [t["name"] for t in si.get("tags", [])]
                soundstr = si.get("soundstr", soundstr)
            except Exception:
                pass

        badges  = ("[音频]" if has_audio else "[锁定]") + (" [字幕]" if has_sub else "") + (" [弹幕]" if has_dm else "")
        fav_str = f"  收藏 {fav:,}" if fav else ""

        lines.append(f"{idx:03d}  **{name}** `{snd}`　{dur}　{date}　播放 {views:,}{fav_str}　{badges}")
        if soundstr and soundstr != name:
            lines.append(f"    {soundstr}")
        if tags:
            lines.append(f"    {' · '.join(tags)}")
        lines.append("")

    lines.append("---")
    lines.append("[音频] 音频已下载　[锁定] 无音频（DRM/付费）　[字幕] 字幕　[弹幕] 弹幕")

    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] README.md -> {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 gen_readme.py <剧集文件夹>")
        sys.exit(1)
    gen_readme(Path(sys.argv[1]))
