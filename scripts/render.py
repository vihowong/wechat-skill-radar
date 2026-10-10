#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 HTML 渲染成指定像素尺寸的图片（Chrome / Edge 无头模式）。

用法：
    python render.py in.html out.png --width 1080 --height 570 [--scale 2]
    python render.py in.html out.jpg --width 1080 --height 608 --quality 86

输出后缀是 .jpg/.jpeg 时自动转成 JPEG（需要 Pillow）。
**照片做底图的页面一定用 JPEG**：同样的画面，PNG 通常 700KB 上下，JPEG 只有 150–250KB，
正好卡住公众号配图的体积预算（见 references/visual-recipes.md）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_browser(explicit: str | None) -> str:
    if explicit:
        if Path(explicit).exists():
            return explicit
        raise SystemExit(f"找不到浏览器：{explicit}")
    for cand in CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in ("chrome", "msedge", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("找不到 Chrome / Edge，可用 --browser 指定路径。")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="HTML → PNG")
    ap.add_argument("html")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--wait", type=int, default=3500)
    ap.add_argument("--browser")
    ap.add_argument("--quality", type=int, default=86, help="输出 JPEG 时的质量")
    args = ap.parse_args()

    src = Path(args.html).resolve()
    if not src.exists():
        raise SystemExit(f"找不到输入文件：{src}")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    want_jpeg = out.suffix.lower() in (".jpg", ".jpeg")
    png_target = out.with_suffix(".png") if want_jpeg else out

    cmd = [
        find_browser(args.browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--disable-extensions",
        f"--force-device-scale-factor={args.scale:g}",
        f"--virtual-time-budget={args.wait}",
        f"--window-size={args.width},{args.height}",
        f"--screenshot={png_target}",
        "file:///" + str(src).replace("\\", "/"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if not png_target.exists():
        raise SystemExit("渲染失败。\n" + (res.stderr or res.stdout or "")[-1200:])
    if want_jpeg:
        try:
            from PIL import Image
        except Exception:  # noqa: BLE001
            raise SystemExit("要输出 JPEG 需要 Pillow：pip install pillow（或把输出改成 .png）")
        im = Image.open(png_target).convert("RGB")
        im.save(out, "JPEG", quality=args.quality, optimize=True, progressive=True,
                subsampling=1)
        png_target.unlink()
    final = out
    print(f"已生成 {final}  ({args.width * args.scale:g}×{args.height * args.scale:g}, "
          f"{final.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
