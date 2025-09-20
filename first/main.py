import os
import sys
from PIL import Image, ImageDraw, ImageFont
import piexif
from datetime import datetime

def get_date_info(image_path):
    """获取图片拍摄日期，没有EXIF就用文件创建日期"""
    # 先尝试从 EXIF 获取
    try:
        exif_data = piexif.load(image_path)
        date_str = exif_data["0th"].get(piexif.ImageIFD.DateTime, None)
        if date_str:
            date_str = date_str.decode('utf-8')
            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            return date_obj.strftime("%Y-%m-%d")
    except Exception:
        pass  # 没有 EXIF 或读取失败

    # 如果没有EXIF日期，返回文件创建日期
    try:
        ctime = os.path.getctime(image_path)
        return datetime.fromtimestamp(ctime).strftime("%Y-%m-%d")
    except Exception:
        return None

def add_watermark(image_path, text, font_size, color, position, output_dir):
    """在图片上添加水印"""
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"无法打开 {image_path}: {e}")
        return

    txt_layer = Image.new("RGBA", img.size, (255,255,255,0))
    draw = ImageDraw.Draw(txt_layer)

    # 选择字体
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = draw.textsize(text, font=font)

    # 位置映射
    pos_map = {
        "left_top": (10, 10),
        "center": ((img.width - text_width) // 2, (img.height - text_height) // 2),
        "right_bottom": (img.width - text_width - 10, img.height - text_height - 10)
    }
    pos = pos_map.get(position, pos_map["right_bottom"])

    # 画文字
    draw.text(pos, text, font=font, fill=color)
    watermarked = Image.alpha_composite(img, txt_layer).convert("RGB")

    # 保存
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, os.path.basename(image_path))
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

    font_size = int(input("请输入字体大小(例如 48): "))
    color = input("请输入颜色(例如 red 或 #FF0000): ")
    position = input("请输入位置(left_top/center/right_bottom): ")

    output_dir = folder + "_watermark"

    for filename in os.listdir(folder):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(folder, filename)
            date_text = get_date_info(path)
            if date_text:
                add_watermark(path, date_text, font_size, color, position, output_dir)
            else:
                print(f"跳过 {filename}: 无日期信息")

if __name__ == "__main__":
    main()
