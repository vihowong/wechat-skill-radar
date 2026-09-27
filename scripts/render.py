#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 HTML 渲染成指定像素尺寸的 PNG（Chrome / Edge 无头模式）。

用法：
    python render.py in.html out.png --width 1080 --height 570 [--scale 2]
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
    args = ap.parse_args()

    src = Path(args.html).resolve()
    if not src.exists():
        raise SystemExit(f"找不到输入文件：{src}")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

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
        f"--screenshot={out}",
        "file:///" + str(src).replace("\\", "/"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if not out.exists():
        raise SystemExit("渲染失败。\n" + (res.stderr or res.stdout or "")[-1200:])
    print(f"已生成 {out}  ({args.width * args.scale:g}×{args.height * args.scale:g}, "
          f"{out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
