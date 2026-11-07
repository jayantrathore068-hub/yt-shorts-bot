import os
import json
import asyncio
import requests
import urllib.parse
import edge_tts
from PIL import Image
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# Make.com se aane wala data read karein
data = json.loads(os.environ["PAYLOAD"])
row_number = data.get("row_number", "2")
webhook_url = data["webhook_url"]
title = data.get("title", "Rahasyamayi Kahani #shorts")
script_text = data["script"]
prompts = data["prompts"]

# 1. Hindi Voiceover Generate Karein (Edge-TTS)
async def make_audio():
    communicate = edge_tts.Communicate(script_text, "hi-IN-MadhurNeural", rate="+8%")
    await communicate.save("voice.mp3")

asyncio.run(make_audio())

# 2. Pollinations.ai se 4 Vertical Images Download Karein
img_files = []
for i, p in enumerate(prompts):
    encoded = urllib.parse.quote(f"{p}, dark suspense cinematic, vertical 9:16")
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=720&height=1280&nologo=true&seed={i+42}"
    r = requests.get(url, timeout=60)
    fname = f"scene_{i}.jpg"
    with open(fname, "wb") as f:
        f.write(r.content)
    img_files.append(fname)

# 3. Smooth Zoom-In Effect (Ken Burns Effect)
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

# 4. Audio aur Images ko Mila Kar Video Render Karein (<4MB Size for Make.com Free Plan)
audio = AudioFileClip("voice.mp3")
clip_duration = audio.duration / len(img_files)
clips = [apply_zoom(ImageClip(m).set_duration(clip_duration), 0.18) for m in img_files]

final_video = concatenate_videoclips(clips, method="compose").set_audio(audio)
final_video.write_videofile(
    "output.mp4",
    fps=24,
    codec="libx264",
    audio_codec="aac",
    bitrate="900k",
    audio_bitrate="96k"
)

# 5. Video ko Temporary Host par Upload Karke Direct Download Link Nikaalein
with open("output.mp4", "rb") as f:
    upload_res = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}).json()

raw_url = upload_res["data"]["url"]
direct_video_url = raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")

# 6. Make.com ke Webhook par Video Link aur Details Wapas Bhejein
webhook_payload = {
    "row_number": row_number,
    "title": title,
    "script": script_text,
    "video_url": direct_video_url
}
requests.post(webhook_url, json=webhook_payload)
print("Video successfully sent to Make.com:", direct_video_url)
