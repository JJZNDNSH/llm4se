import os
import sys
from PIL import Image, ImageDraw, ImageFont
import piexif
from datetime import datetime

def get_exif_date(image_path):
    """获取图片EXIF拍摄日期(年月日)，如果没有则返回None"""
    try:
        exif_data = piexif.load(image_path)
        date_str = exif_data["0th"].get(piexif.ImageIFD.DateTime, None)
        if date_str:
            # 格式：'2023:08:15 10:23:45' -> '2023-08-15'
            date_str = date_str.decode('utf-8')
            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            return date_obj.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None

def add_watermark(image_path, text, font_size, color, position, output_dir):
    """在图片上添加水印"""
    img = Image.open(image_path).convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt_layer)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Pillow 10+ 用 textbbox 获取文字尺寸
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # 兼容老版本
        text_width, text_height = draw.textsize(text, font=font)

    pos_map = {
        "left_top": (10, 10),
        "center": ((img.width - text_width) // 2, (img.height - text_height) // 2),
        "right_bottom": (img.width - text_width - 10, img.height - text_height - 10)
    }
    pos = pos_map.get(position, pos_map["right_bottom"])

    draw.text(pos, text, font=font, fill=color)
    watermarked = Image.alpha_composite(img, txt_layer).convert("RGB")

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(image_path)
    save_path = os.path.join(output_dir, filename)
    watermarked.save(save_path)
    print(f"已保存: {save_path}")

def main():
    if len(sys.argv) < 2:
        print("用法: python add_watermark.py <图片目录>")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("提供的路径不是一个目录")
        sys.exit(1)

    # 用户参数
    font_size = int(input("请输入字体大小(例如 48): "))
    color = input("请输入颜色(例如 red 或 #FF0000): ")
    position = input("请输入位置(left_top/center/right_bottom): ")

    output_dir = folder + "_watermark"

    for filename in os.listdir(folder):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(folder, filename)
            date_text = get_exif_date(path)
            if date_text:
                add_watermark(path, date_text, font_size, color, position, output_dir)
            else:
                print(f"跳过 {filename}: 无EXIF日期")

if __name__ == "__main__":
    main()
