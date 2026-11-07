import os
import json
import asyncio
import requests
import urllib.parse
import edge_tts
import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

# 1. Read Payload from Make.com
payload_str = os.environ.get("PAYLOAD", "{}")
try:
    data = json.loads(payload_str)
except Exception:
    data = {}

title = data.get("title", "Mystery Short #shorts")
script_text = data.get("script", "क्या आप जानते हैं इस रहस्य के बारे में? यह सच में हैरान कर देने वाला है।")
prompts = data.get("prompts", [
    "dark mysterious cinematic scene",
    "eerie surreal mystery background",
    "confusing close up mystery shot",
    "shocking revelation cinematic lighting"
])
webhook_url = data.get("webhook_url", "")

# 2. Generate Hindi Voiceover (Edge-TTS)
async def make_Audio():
    communicate = edge_tts.Communicate(script_text, "hi-IN-MadhurNeural", rate="+10%")
    await communicate.save("voice.mp3")

asyncio.run(make_Audio())

# 3. Download AI Images from Pollinations (with safe fallback)
img_files = []
for i, p in enumerate(prompts[:4]):
    filename = f"img_{i}.jpg"
    clean_p = urllib.parse.quote(f"{p}, vertical 9:16 aspect ratio, cinematic, dark mystery, hyperrealistic, 8k")
    url = f"https://image.pollinations.ai/prompt/{clean_p}?width=720&height=1280&nologo=true&seed={i+42}"
    
    success = False
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(filename, "wb") as f:
                    f.write(r.content)
                img = Image.open(filename).convert("RGB").resize((720, 1280))
                img.save(filename)
                success = True
                break
        except Exception:
            pass
            
    if not success:
        # Fallback solid dark image if download fails
        img = Image.new("RGB", (720, 1280), color=(15, 15, 25))
        img.save(filename)
        
    img_files.append(filename)

# Zoom effect function
def apply_zoom(clip, zoom_ratio=0.15):
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        base_size = img.size
        scale = 1 + (zoom_ratio * (t / clip.duration))
        new_size = [int(base_size[0] * scale), int(base_size[1] * scale)]
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        x = (new_size[0] - base_size[0]) // 2
        y = (new_size[1] - base_size[1]) // 2
        img = img.crop((x, y, x + base_size[0], y + base_size[1]))
        return np.array(img)
    return clip.fl(effect)

# 4. Render Video (100% YouTube Compatible yuv420p format)
audio = AudioFileClip("voice.mp3")
clip_duration = audio.duration / len(img_files)
clips = []

for m in img_files:
    arr = np.array(Image.open(m).convert("RGB"))
    clip = ImageClip(arr).set_duration(clip_duration)
    clips.append(apply_zoom(clip, 0.15))

final_video = concatenate_videoclips(clips, method="compose").set_audio(audio)
final_video.write_videofile(
    "output.mp4",
    fps=24,
    codec="libx264",
    audio_codec="aac",
    temp_audiofile="temp-audio.m4a",
    remove_temp=True,
    ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]
)

# 5. Push video directly to GitHub Repo (100% Direct MP4 Link)
os.system("git config user.name 'github-actions'")
os.system("git config user.email 'actions@github.com'")
os.system("git add output.mp4")
os.system("git commit -m 'Update rendered short' || true")
os.system("git push origin main --force")

repo = os.environ.get("GITHUB_REPOSITORY", "jayantrathore068-hub/yt-shorts-bot")
direct_video_url = f"https://raw.githubusercontent.com/{repo}/main/output.mp4"

# 6. Send Video back to Make.com Webhook
final_webhook = "https://hook.us2.make.com/7ggp3l3jfk9uuofxxfuremegrft4jwb0"
if final_webhook.startswith("http"):
    requests.post(final_webhook, json={
        "title": title,
        "script": script_text,
        "video_url": direct_video_url
    })
elif webhook_url.startswith("http"):
    requests.post(webhook_url, json={
        "title": title,
        "script": script_text,
        "video_url": direct_video_url
    })
