"""
Generates sample_report.png from sample_report.txt so the full
upload -> OCR -> ... pipeline can be tested end-to-end without needing
a real scanned report. Run once: python sample_data/generate_sample_image.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
text = (HERE / "sample_report.txt").read_text()

width, line_height = 900, 26
lines = text.splitlines()
height = line_height * (len(lines) + 4)

img = Image.new("RGB", (width, height), "white")
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("DejaVuSansMono.ttf", 18)
except OSError:
    font = ImageFont.load_default()

y = 20
for line in lines:
    draw.text((30, y), line, fill="black", font=font)
    y += line_height

out_path = HERE / "sample_report.png"
img.save(out_path)
print(f"Wrote {out_path}")
