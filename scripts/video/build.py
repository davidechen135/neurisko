"""Build the demo video from the real console: narration (Kokoro TTS, local), browser capture
(Playwright with the installed Chrome) and ffmpeg (imageio-ffmpeg's bundled binary).

Kokoro model files (Apache-2.0, ~350 MB) go in ~/.cache/kokoro/ (or $KOKORO_DIR):
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
  (kokoro-v1.0.onnx, voices-v1.0.bin)

Run (macOS):
  uv run --with playwright --with imageio-ffmpeg --with kokoro-onnx \
    python scripts/video/build.py [--out video/neurisko-demo.mp4] [--voice af_heart] [--speed 1.0]

Outputs the MP4 plus an .srt with the narration, for YouTube captions.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from kokoro_onnx import Kokoro
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
import music  # noqa: E402
from narration import SCENES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "video" / "build"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
KOKORO_DIR = Path(os.environ.get("KOKORO_DIR", Path.home() / ".cache" / "kokoro"))
VOICE = "af_heart"  # Kokoro voice; overridden by --voice
SPEED = 1.1  # a touch brisker than default reads livelier
SIZE = {"width": 1280, "height": 720}
GAP = 0.32  # silence between sentences
TAIL = 0.9  # silence at the end of a scene
RATE_HZ = 24000  # Kokoro's native sample rate
MUSIC_DB = -17.0  # background music level before ducking (scripts/video/music.py)
VOICE_MP4 = BUILD / "voice.mp4"  # concatenated scenes, narration only
# Spoken forms for words the TTS mispronounces. Captions keep the written text.
PRONOUNCE = {
    "Neurisko": "Nyoo-risko", "Qwen": "Kwen", "Kiro": "Keero",
    # Kokoro reads 1981 as "nineteen hundred eighty-one".
    "1981": "nineteen eighty-one", "1982": "nineteen eighty-two", "1983": "nineteen eighty-three",
}

# Per-scene ffmpeg colour grade (each ends with a comma; see cards/fx.css for the story arc).
GRADES = {
    # 1981 archive tape: colour bleed, soft focus, live grain, warm contrast, dark corners.
    "vhs": "rgbashift=rh=4:bh=-4:rv=1,gblur=sigma=0.7,noise=alls=14:allf=t+u,"
           "eq=contrast=1.06:saturation=1.15,vignette=angle=PI/4.5,",
    # Synthwave cards: a touch more saturation, gentle vignette.
    "synth": "eq=saturation=1.1:contrast=1.03,vignette=angle=PI/5,",
    # The real console: left crisp so every number stays readable.
    "clean": "",
}

# Video-only overlays for console scenes: recolour theme, accent frame, chapter sting and tag.
OVERLAY_JS = """
([theme, chapter]) => {
  document.body.dataset.theme = theme;
  const frame = document.createElement('div'); frame.id = 'fx-frame'; document.body.appendChild(frame);
  if (!chapter.length) return;
  const [num, title, sub] = chapter;
  const tag = document.createElement('div'); tag.id = 'fx-tag';
  tag.innerHTML = `<b>${num}</b>${title} <i>· ${sub}</i>`;
  document.body.appendChild(tag);
  const sting = document.createElement('div'); sting.id = 'fx-sting';
  sting.innerHTML = `<div class="num">${num}</div><div class="ttl">${title}</div><div class="sub">${sub}</div>`;
  document.body.appendChild(sting);
}
"""

CAPTION_JS = """
(text) => {
  if (text === null) text = window.__capText || ''; else window.__capText = text;
  let c = document.getElementById('__cap');
  if (!c) {
    c = document.createElement('div'); c.id = '__cap';
    Object.assign(c.style, {position:'fixed', left:'50%', bottom:'26px', transform:'translateX(-50%)',
      maxWidth:'1100px', padding:'8px 16px', background:'rgba(0,0,0,.82)', color:'#fff',
      font:'20px/1.35 -apple-system, Helvetica, sans-serif', textAlign:'center', zIndex:99,
      borderRadius:'4px', textShadow:'none'});
  }
  // An open modal dialog sits in the top layer above everything; put the caption inside it.
  const host = document.querySelector('dialog[open]') || document.body;
  if (c.parentElement !== host) host.appendChild(c);
  c.textContent = text; c.style.display = text ? 'block' : 'none';
}
"""


def sh(*cmd: str) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


@functools.cache
def kokoro() -> Kokoro:
    return Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"))


def tts(text: str, out: Path) -> float:
    spoken = text
    for word, say_as in PRONOUNCE.items():
        spoken = re.sub(rf"\b{word}\b", say_as, spoken)
    lang = "en-gb" if VOICE.startswith("b") else "en-us"
    audio, sr = kokoro().create(spoken, voice=VOICE, speed=SPEED, lang=lang)
    assert sr == RATE_HZ, sr
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE_HZ)
        w.writeframes(pcm.tobytes())
    return len(pcm) / RATE_HZ


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(seconds * RATE_HZ)


def build_audio(scene: dict, d: Path) -> tuple[Path, list[tuple[float, float, str]], float]:
    """Scene narration WAV, sentence timings (start, end, text) and total length."""
    frames, timings, t = [], [], 0.3
    frames.append(silence(0.3))
    for i, line in enumerate(scene["lines"]):
        f = d / f"{scene['name']}-{i}.wav"
        dur = tts(line, f)
        with wave.open(str(f)) as w:
            frames.append(w.readframes(w.getnframes()))
        timings.append((t, t + dur, line))
        t += dur
        frames.append(silence(GAP))
        t += GAP
    frames.append(silence(TAIL))
    total = t + TAIL
    out = d / f"{scene['name']}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE_HZ)
        w.writeframes(b"".join(frames))
    return out, timings, total


def prepare_site() -> Path:
    site = BUILD / "site"
    cmd = [
        "uv", "run", "neurisko", "export", "runs/demo/qwen-s0",
        "--report", "reports/demo/default",
        "--h59", "runs/demo/h59-off", "runs/demo/h59-on",
        "--tcs", "runs/demo/tcs-1981", "runs/demo/tcs-1982",
        "--tcs-reports", "reports/demo/tcs-1981", "reports/demo/tcs-1982",
        "--out", str(site),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
    shutil.copytree(Path(__file__).parent / "cards", site / "video")
    return site


def serve(site: Path) -> int:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


async def record(browser, port: int, scene: dict, timings, total: float, d: Path) -> tuple[Path, float]:
    ctx = await browser.new_context(
        viewport=SIZE, record_video_dir=str(d), record_video_size=SIZE,
        reduced_motion="no-preference",
    )
    page = await ctx.new_page()
    t_create = time.monotonic()
    await page.goto(f"http://127.0.0.1:{port}/{scene['page']}")
    await page.wait_for_load_state("networkidle")
    await page.evaluate("localStorage.setItem('neurisko-crt','on')")
    if "#" in scene["page"]:
        await page.wait_for_timeout(600)  # first render of the console
    if scene.get("theme"):
        await page.add_style_tag(url="/video/fx.css")
        await page.wait_for_timeout(100)
        await page.evaluate(OVERLAY_JS, [scene["theme"], list(scene.get("chapter") or [])])
    offset = time.monotonic() - t_create
    t0 = time.monotonic()

    events = []
    for i, (start, end, text) in enumerate(timings):
        events.append((start, ("caption", text)))
        events.append((end, ("caption", "")))
    for idx, after, action in scene["actions"]:
        events.append((timings[idx][0] + after, action))
    events.sort(key=lambda e: e[0])
    for at, action in events:
        wait = at - (time.monotonic() - t0)
        if wait > 0:
            await asyncio.sleep(wait)
        if isinstance(action, tuple) and action[0] == "caption":
            await page.evaluate(CAPTION_JS, action[1])
        elif isinstance(action, tuple) and action[0] == "click":
            await page.locator(action[1]).nth(action[2]).click()
            await page.evaluate(CAPTION_JS, None)  # re-attach the caption
        else:
            await page.evaluate(action)
    rest = total - (time.monotonic() - t0)
    if rest > 0:
        await asyncio.sleep(rest)
    video = page.video
    await ctx.close()
    return Path(await video.path()), offset


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def probe_seconds(path: Path) -> float:
    err = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def mix(out: Path, seconds: float, music_db: float) -> None:
    """Lay the synthesised music under the narration, ducking it while someone speaks."""
    if music_db == float("-inf") or music_db == float("inf"):
        shutil.copy(VOICE_MP4, out)
        return
    track = music.write(BUILD / "music.wav", seconds + 0.5)
    graph = (
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo,asplit=2[v][key];"
        f"[1:a]volume={music_db}dB[m];"
        # Duck the music ~8 dB under speech; slow release so it swells back between lines.
        "[m][key]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[duck];"
        "[v][duck]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.95[a]"
    )
    sh(FFMPEG, "-y", "-i", str(VOICE_MP4), "-i", str(track), "-filter_complex", graph,
       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
       "-movflags", "+faststart", str(out))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="video/neurisko-demo.mp4")
    ap.add_argument("--only", default=None, help="build one scene (for checking)")
    ap.add_argument("--voice", default=VOICE, help="Kokoro voice: af_heart, am_michael, ...")
    ap.add_argument("--speed", type=float, default=SPEED, help="speech speed (1.0 = normal)")
    ap.add_argument("--music-db", type=float, default=MUSIC_DB,
                    help="music level in dB (e.g. -22); 'inf' disables it")
    ap.add_argument("--remix", action="store_true",
                    help="only redo the music mix on the last build (fast, for tuning)")
    args = ap.parse_args()
    globals().update(VOICE=args.voice, SPEED=args.speed)
    if args.remix:
        out = ROOT / args.out
        mix(out, float(probe_seconds(VOICE_MP4)), args.music_db)
        print(f"remixed {out}")
        return
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    site = prepare_site()
    port = serve(site)
    scenes = [s for s in SCENES if args.only in (None, s["name"])]
    parts, srt, clock = [], [], 0.0
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        for scene in scenes:
            d = BUILD / scene["name"]
            d.mkdir()
            wav, timings, total = build_audio(scene, d)
            webm, offset = await record(browser, port, scene, timings, total, d)
            mp4 = d / "scene.mp4"
            vf = (f"fps=30,{GRADES[scene.get('grade', 'clean')]}"
                  f"fade=t=in:st=0:d=0.25,fade=t=out:st={total - 0.3:.3f}:d=0.3,format=yuv420p")
            sh(FFMPEG, "-y", "-ss", f"{offset:.3f}", "-i", str(webm), "-i", str(wav),
               "-t", f"{total:.3f}", "-map", "0:v", "-map", "1:a",
               "-vf", vf, "-c:v", "libx264", "-preset", "medium",
               "-crf", "20", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
               "-c:a", "aac", "-b:a", "128k", "-ar", "44100", str(mp4))
            parts.append(mp4)
            for start, end, text in timings:
                srt.append((clock + start, clock + end, text))
            clock += total
            print(f"{scene['name']:8} {total:6.1f}s  (total {clock:6.1f}s)", flush=True)
        await browser.close()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    lst = BUILD / "parts.txt"
    lst.write_text("".join(f"file '{m}'\n" for m in parts))
    sh(FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
       "-movflags", "+faststart", str(VOICE_MP4))
    mix(out, clock, args.music_db)
    srt_path = out.with_suffix(".srt")
    srt_path.write_text(
        "\n\n".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t}" for i, (a, b, t) in enumerate(srt, 1))
        + "\n"
    )
    print(f"wrote {out} ({clock:.0f}s) and {srt_path.name}")


if __name__ == "__main__":
    asyncio.run(main())
