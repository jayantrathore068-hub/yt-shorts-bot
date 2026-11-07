import os, json, asyncio, requests, urllib.parse, time
from io import BytesIO
import edge_tts
from PIL import Image, ImageDraw
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

data = json.loads(os.environ["PAYLOAD"])
webhook_url = data["webhook_url"]
title = data.get("title", "Trending Kahani #shorts")
script_text = data["script"]
prompts = data["prompts"]

# 1. Hindi Voiceover
async def make_audio():
    communicate = edge_tts.Communicate(script_text, "hi-IN-MadhurNeural", rate="+8%")
    await communicate.save("voice.mp3")
asyncio.run(make_audio())

# Backup image generator (agar Pollinations busy ho toh crash nahi hone dega)
def make_fallback_image(index):
    img = Image.new("RGB", (720, 1280), (15, 18, 30))
    draw = ImageDraw.Draw(img)
    for y in range(1280):
        r = int(15 + (y / 1280) * 35)
        g = int(10 + (y / 1280) * 15)
        b = int(30 + (y / 1280) * 55)
        draw.line([(0, y), (720, y)], fill=(r, g, b))
    return img

# 2. Download 4 Vertical Images Safely
img_files = []
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

for i, p in enumerate(prompts):
    fname = f"scene_{i}.jpg"
    success = False
    for attempt in range(3):
        try:
            encoded = urllib.parse.quote(f"{p}, dark cinematic lighting, vertical 9:16")
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&seed={i+100+attempt}"
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 200 and len(r.content) > 5000:
                img = Image.open(BytesIO(r.content)).convert("RGB").resize((720, 1280), Image.LANCZOS)
                img.save(fname, "JPEG", quality=90)
                success = True
                break
        except Exception as e:
            print(f"Retry {attempt+1} for scene {i}: {e}")
        time.sleep(3)

    if not success:
        fallback = make_fallback_image(i)
        fallback.save(fname, "JPEG", quality=90)

    img_files.append(fname)

# 3. Smooth Zoom Effect
def apply_zoom(clip, zoom_ratio=0.15):
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        w, h = img.size
        scale = 1 + (zoom_ratio * (t / clip.duration))
        new_w, new_h = int(w / scale), int(h / scale)
        left, top = (w - new_w) // 2, (h - new_h) // 2
        cropped = img.crop((left, top, left + new_w, top + new_h))
        return np.array(cropped.resize((w, h), Image.LANCZOS))
    return clip.fl(effect)

# 4. Render Video (Direct PIL -> Numpy load so imageio never fails)
audio = AudioFileClip("voice.mp3")
clip_duration = audio.duration / len(img_files)
clips = []
for m in img_files:
    arr = np.array(Image.open(m).convert("RGB"))
    clips.append(apply_zoom(ImageClip(arr).set_duration(clip_duration), 0.18))

final_video = concatenate_videoclips(clips, method="compose").set_audio(audio)
final_video.write_videofile("output.mp4", fps=24, codec="libx264", audio_codec="aac", bitrate="900k", audio_bitrate="96k")

# 5. Get Direct Download Link
with open("output.mp4", "rb") as f:
    upload_res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}).json()

direct_video_url = upload_res["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")

# 6. Send Video back to Make.com Webhook
requests.post(webhook_url, json={
    "title": title,
    "script": script_text,
    "video_url": direct_video_url
})
