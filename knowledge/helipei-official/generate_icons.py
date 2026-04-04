from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    # Color: #007bff (Primary Blue from CSS)
    img = Image.new('RGB', (size, size), color='#007bff')
    d = ImageDraw.Draw(img)
    
    # Draw a circle in the middle
    margin = size // 10
    d.ellipse([margin, margin, size - margin, size - margin], outline='white', width=size//20)
    
    # Draw text "HO" (Helibei Official)
    text = "HO"
    
    try:
        font_path = "/System/Library/Fonts/Helvetica.ttc"
        if not os.path.exists(font_path):
             font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
        
        font_size = size // 2
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) / 2
    y = (size - text_height) / 2 - (bbox[1] / 2)
    
    d.text((x, y), text, fill='white', font=font)
    
    img.save(filename)
    print(f"Created {filename}")

if __name__ == "__main__":
    create_icon(192, "icon-192.png")
    create_icon(512, "icon-512.png")
