import os
import time
import shutil
import glob
from pathlib import Path
from playwright.sync_api import sync_playwright
import imageio_ffmpeg
import subprocess

def record_demo():
    print("[RECORDER] Starting automated MP4 video recording of Mr. Cabie...")
    output_dir = Path("demo_video_temp")
    output_dir.mkdir(exist_ok=True)

    final_mp4_path = Path("demo_recording.mp4")

    # Reset data first
    from data_manager import DataManager
    dm = DataManager()
    dm.reset_to_default_sample()

    with sync_playwright() as p:
        # Launch Chromium with video recording enabled at 1280x720 (720p HD)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(output_dir),
            record_video_size={"width": 1280, "height": 720}
        )

        page = context.new_page()
        page.goto("http://127.0.0.1:8000")
        page.wait_for_timeout(2500)

        # 1. Show overview
        print("[RECORDER] Capturing dashboard overview...")
        page.wait_for_timeout(2000)

        # 2. Click 08:30 AM simulation preset for Ramesh Kumar
        print("[RECORDER] Triggering 08:30 AM simulation preset for Ramesh Kumar...")
        page.click("button:has-text('08:30 AM')")
        page.wait_for_timeout(3000)

        # 3. Click 09:15 AM simulation preset for Suresh Yadav
        print("[RECORDER] Triggering 09:15 AM simulation preset for Suresh Yadav...")
        page.click("button:has-text('09:15 AM')")
        page.wait_for_timeout(3000)

        # 4. Trigger manual call on Amit Sharma (Row 3)
        print("[RECORDER] Triggering manual call for Amit Sharma...")
        call_buttons = page.query_selector_all("button:has-text('Call Now')")
        if len(call_buttons) >= 3:
            call_buttons[2].click()
        page.wait_for_timeout(3000)

        # 5. Play Voice Preview
        print("[RECORDER] Demonstrating Voice Script Preview...")
        page.click("button:has-text('Listen TTS Sample')")
        page.wait_for_timeout(3000)

        # 6. Smooth scroll down and up to show full system
        print("[RECORDER] Scrolling to show Call Activity Log and TwiML script...")
        page.evaluate("window.scrollTo({top: 250, behavior: 'smooth'})")
        page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        page.wait_for_timeout(3000)

        # Close context to finish video writing
        context.close()
        browser.close()

    # Locate generated video file
    video_files = list(output_dir.glob("*.webm"))
    if not video_files:
        print("[RECORDER] Error: No recorded video file found in temp dir.")
        return

    raw_video = video_files[0]
    print(f"[RECORDER] Raw video captured: {raw_video}")

    # Convert to standard MP4 using ffmpeg binary from imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"[RECORDER] Converting to MP4 format via FFmpeg ({ffmpeg_exe})...")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(raw_video),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        str(final_mp4_path)
    ]
    subprocess.run(cmd, check=True)

    # Clean up temp
    shutil.rmtree(output_dir, ignore_errors=True)

    if final_mp4_path.exists():
        size_mb = round(final_mp4_path.stat().st_size / (1024 * 1024), 2)
        print(f"\n[RECORDER] SUCCESS! Video successfully generated: {final_mp4_path.resolve()} ({size_mb} MB)")

if __name__ == "__main__":
    record_demo()
