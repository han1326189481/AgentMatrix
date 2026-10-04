from PIL import Image, ImageDraw

input_path = "image/logo.jpg"
output_path = "frontend/public/favicon.ico"

img = Image.open(input_path).convert("RGBA")
size = 64
img = img.resize((size, size), Image.LANCZOS)

mask = Image.new("L", (size, size), 0)
draw = ImageDraw.Draw(mask)
draw.ellipse((0, 0, size-1, size-1), fill=255)

result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
result.paste(img, (0, 0), mask)

result.save(output_path)
print(f"Favicon created: {output_path}")