import os
from PIL import Image, ImageDraw

# Simple script to generate a basic icon for the Windows ChatMix application
# This creates a 256x256 icon with a simple audio speaker symbol

size = 256
icon = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
draw = ImageDraw.Draw(icon)

# Draw a simple speaker/audio symbol
# Outer circle background
margin = 20
draw.ellipse([(margin, margin), (size - margin, size - margin)], fill=(52, 152, 219), outline=(41, 128, 185), width=4)

# Speaker cone (triangle)
speaker_left = size // 3
speaker_top = size // 3
speaker_bottom = 2 * size // 3
speaker_right = size // 2 - 10

points = [(speaker_left, speaker_top), (speaker_right, speaker_top + (speaker_bottom - speaker_top) // 2), (speaker_left, speaker_bottom)]
draw.polygon(points, fill=(255, 255, 255))

# Sound waves
wave_x = speaker_right + 15
wave_spacing = 20
for i, wave_offset in enumerate([0, 20]):
    y = size // 2 - 30 + wave_offset
    draw.arc([(wave_x - 10, y - 10), (wave_x + 10, y + 10)], 0, 360, fill=(255, 255, 255), width=2)
    draw.arc([(wave_x - 20, y - 20), (wave_x + 20, y + 20)], 0, 360, fill=(255, 255, 255), width=2)

icon.save('windows/icon.ico', 'ICO', sizes=[(256, 256)])
print("Icon created: windows/icon.ico")
