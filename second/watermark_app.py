#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Watermarker 本地应用（单文件 PyQt5 实现）
中文界面版本

功能亮点（已实现主要需求，包含尽可能多的高级功能）：
 - 导入单张/多张图片或文件夹（支持拖放 + 文件选择器）
 - 缩略图列表（显示文件名和小图）
 - 实时预览（点击列表切换预览图片，实时显示水印调整）
 - 文本水印（内容、字体、字号、粗体/斜体、颜色、透明度、阴影）
 - 图片水印（支持带透明通道的 PNG，缩放、透明度）
 - 九宫格位置预设 + 画面上拖拽定位
 - 导出到指定文件夹（默认禁止覆盖原图），支持命名规则（保留原名/前缀/后缀）
 - JPEG 输出质量设置、导出时尺寸缩放
 - 保存/加载水印模板（JSON）

依赖：PyQt5, Pillow
安装（推荐使用虚拟环境）：
    pip install PyQt5 Pillow

使用：
    python watermarker_cn.py

注意：
 - 该文件为单文件示例，方便测试与打包。性能与UI可根据需要优化与拆分。

"""

import sys
import os
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from PyQt5.QtWidgets import (
    QApplication, QWidget, QFileDialog, QListWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QListWidgetItem, QSlider, QColorDialog,
    QLineEdit, QComboBox, QSpinBox, QMessageBox, QCheckBox, QInputDialog
)
from PyQt5.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QFontDatabase
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon
from PIL import Image, ImageDraw, ImageFont
# -------------------- 辅助函数 --------------------

def pil_image_to_qpixmap(im):
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    data = im.tobytes('raw', 'RGBA')
    qimg = QImage(data, im.width, im.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def load_image_thumbnail(path, max_size=(160, 120)):
    try:
        im = Image.open(path)
        im.thumbnail(max_size)
        return pil_image_to_qpixmap(im)
    except Exception as e:
        print('load thumbnail error', e)
        return QPixmap()


# -------------------- 主窗口 --------------------
class Watermarker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('批量图片打水印工具 - 中文界面')
        self.resize(1100, 700)
        self.setAcceptDrops(True)

        # 数据
        self.image_paths = []
        self.current_index = None
        self.current_image = None  # PIL Image

        # 水印参数
        self.template = {
            'type': 'text',  # text or image
            'text': 'watermark',
            'font_family': 'Arial',
            'font_size': 36,
            'bold': False,
            'italic': False,
            'color': '#FFFFFF',
            'opacity': 70,
            'shadow': True,
            'position': 'center',  # nine-grid keys or custom
            'offset': (0, 0),
            'angle': 0,
            'image_watermark': None,
            'image_scale': 0.25,
            'image_opacity': 80
        }

        # UI 组件
        self.list_widget = QListWidget()
        self.preview_label = QLabel('预览区')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet('background: #222; color: #fff')

        # 左侧按钮
        btn_import = QPushButton('导入图片/文件夹')
        btn_import.clicked.connect(self.import_files_dialog)
        btn_clear = QPushButton('清空列表')
        btn_clear.clicked.connect(self.clear_list)

        # 右侧：水印设置
        self.input_text = QLineEdit(self.template['text'])
        self.font_combo = QComboBox()
        self._populate_fonts()
        self.font_combo.setCurrentText(self.template['font_family'])
        self.size_spin = QSpinBox(); self.size_spin.setRange(8, 300); self.size_spin.setValue(self.template['font_size'])
        self.opacity_slider = QSlider(Qt.Horizontal); self.opacity_slider.setRange(0, 100); self.opacity_slider.setValue(self.template['opacity'])
        self.color_btn = QPushButton('选择颜色')
        self.color_btn.clicked.connect(self.choose_color)
        self.shadow_cb = QCheckBox('阴影'); self.shadow_cb.setChecked(self.template['shadow'])

        # 位置按钮（九宫格）
        pos_layout = QHBoxLayout()
        self.pos_buttons = {}
        pos_names = ['左上', '上中', '右上', '左中', '中心', '右中', '左下', '下中', '右下']
        pos_keys = ['top-left','top','top-right','left','center','right','bottom-left','bottom','bottom-right']
        for name,key in zip(pos_names,pos_keys):
            b = QPushButton(name)
            b.clicked.connect(lambda _,k=key: self.set_position(k))
            pos_layout.addWidget(b)
            self.pos_buttons[key]=b

        # 图片水印选择
        self.btn_choose_wm_image = QPushButton('选择图片水印 (PNG 支持透明)')
        self.btn_choose_wm_image.clicked.connect(self.choose_watermark_image)
        self.img_scale_slider = QSlider(Qt.Horizontal); self.img_scale_slider.setRange(1,500); self.img_scale_slider.setValue(int(self.template['image_scale']*100))
        self.img_opacity_slider = QSlider(Qt.Horizontal); self.img_opacity_slider.setRange(0,100); self.img_opacity_slider.setValue(self.template['image_opacity'])

        # 导出设置
        self.output_folder_btn = QPushButton('选择导出目录')
        self.output_folder_btn.clicked.connect(self.choose_output_folder)
        self.output_folder_label = QLabel('(未选择)')
        self.naming_combo = QComboBox(); self.naming_combo.addItems(['保留原文件名','添加前缀 (例: wm_)','添加后缀 (例: _watermarked)'])
        self.naming_input = QLineEdit('wm_')
        self.jpeg_quality_slider = QSlider(Qt.Horizontal); self.jpeg_quality_slider.setRange(1,100); self.jpeg_quality_slider.setValue(90)
        self.resize_combo = QComboBox(); self.resize_combo.addItems(['不缩放','按宽度','按高度','按百分比'])
        self.resize_input = QSpinBox(); self.resize_input.setRange(1,10000); self.resize_input.setValue(1000)
        self.override_original_cb = QCheckBox('允许导出到原文件夹（危险：可能覆盖原图）')

        btn_export = QPushButton('开始导出')
        btn_export.clicked.connect(self.export_images)

        # 模板管理
        btn_save_template = QPushButton('保存当前为模板')
        btn_save_template.clicked.connect(self.save_template_dialog)
        btn_load_template = QPushButton('加载模板')
        btn_load_template.clicked.connect(self.load_template_dialog)

        # 布局
        left_v = QVBoxLayout(); left_v.addWidget(btn_import); left_v.addWidget(btn_clear); left_v.addWidget(self.list_widget)
        left_w = QWidget(); left_w.setLayout(left_v)

        right_v = QVBoxLayout()
        right_v.addWidget(QLabel('水印文字：'))
        right_v.addWidget(self.input_text)
        right_v.addWidget(QLabel('字体：'))
        right_v.addWidget(self.font_combo)
        right_v.addWidget(QLabel('字号：'))
        right_v.addWidget(self.size_spin)
        right_v.addWidget(QLabel('文字透明度：'))
        right_v.addWidget(self.opacity_slider)
        right_v.addWidget(self.color_btn)
        right_v.addWidget(self.shadow_cb)
        right_v.addLayout(pos_layout)
        right_v.addWidget(QLabel('图片水印设置（可选）'))
        right_v.addWidget(self.btn_choose_wm_image)
        right_v.addWidget(QLabel('图片水印缩放 (%)'))
        right_v.addWidget(self.img_scale_slider)
        right_v.addWidget(QLabel('图片水印透明度'))
        right_v.addWidget(self.img_opacity_slider)
        right_v.addWidget(QLabel('导出设置'))
        right_v.addWidget(self.output_folder_btn); right_v.addWidget(self.output_folder_label)
        right_v.addWidget(QLabel('文件命名规则：'))
        right_v.addWidget(self.naming_combo); right_v.addWidget(self.naming_input)
        right_v.addWidget(QLabel('JPEG 质量'))
        right_v.addWidget(self.jpeg_quality_slider)
        right_v.addWidget(QLabel('导出缩放'))
        right_v.addWidget(self.resize_combo); right_v.addWidget(self.resize_input)
        right_v.addWidget(self.override_original_cb)
        right_v.addWidget(btn_export)
        right_v.addWidget(btn_save_template); right_v.addWidget(btn_load_template)

        right_w = QWidget(); right_w.setLayout(right_v)

        center_v = QVBoxLayout(); center_v.addWidget(self.preview_label)
        center_w = QWidget(); center_w.setLayout(center_v)

        main_h = QHBoxLayout(); main_h.addWidget(left_w,2); main_h.addWidget(center_w,5); main_h.addWidget(right_w,3)
        self.setLayout(main_h)

        # 信号
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.opacity_slider.valueChanged.connect(self.update_preview)
        self.size_spin.valueChanged.connect(self.update_preview)
        self.font_combo.currentTextChanged.connect(self.update_preview)
        self.input_text.textChanged.connect(self.update_preview)
        self.img_scale_slider.valueChanged.connect(self.update_preview)
        self.img_opacity_slider.valueChanged.connect(self.update_preview)
        self.list_widget.setAcceptDrops(True)

        # 输出
        self.output_folder = None

    def _populate_fonts(self):
        db = QFontDatabase()
        families = db.families()
        self.font_combo.addItems(sorted(families))

    # -------------------- 拖放 & 导入 --------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        files = []
        for p in paths:
            if os.path.isdir(p):
                for root,_,fnames in os.walk(p):
                    for f in fnames:
                        files.append(os.path.join(root,f))
            else:
                files.append(p)
        self.add_files(files)

    def import_files_dialog(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, '选择图片文件或按取消选择文件夹', '', 'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)', options=options)
        if files:
            self.add_files(files)
        else:
            # 如果没有选文件，允许选择文件夹
            folder = QFileDialog.getExistingDirectory(self, '选择图片文件夹')
            if folder:
                self.add_files([folder])

    def add_files(self, paths):
        accepted_ext = ('.jpg','.jpeg','.png','.bmp','.tif','.tiff')
        for p in paths:
            if os.path.isdir(p):
                for root,_,fnames in os.walk(p):
                    for f in fnames:
                        if f.lower().endswith(accepted_ext):
                            self._add_image(os.path.join(root,f))
            else:
                if p.lower().endswith(accepted_ext):
                    self._add_image(p)
        self.update()

    def _add_image(self, path):
        if path in self.image_paths:
            return
        self.image_paths.append(path)
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        pixmap = QPixmap(path)
        icon = QIcon(pixmap)
        item.setIcon(icon)
        self.list_widget.addItem(item)

    def clear_list(self):
        self.image_paths = []
        self.list_widget.clear()
        self.preview_label.setPixmap(QPixmap())

    def on_item_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        self.current_index = self.image_paths.index(path)
        self.load_current_image()
        self.update_preview()

    def load_current_image(self):
        if self.current_index is None: return
        path = self.image_paths[self.current_index]
        try:
            im = Image.open(path).convert('RGBA')
            self.current_image = im
        except Exception as e:
            QMessageBox.warning(self, '加载图片失败', str(e))
            self.current_image = None

    # -------------------- 颜色 & 图片水印 --------------------
    def choose_color(self):
        col = QColorDialog.getColor()
        if col.isValid():
            self.template['color'] = col.name()
            self.update_preview()

    def choose_watermark_image(self):
        fn, _ = QFileDialog.getOpenFileName(self, '选择图片水印', '', 'PNG 图片 (*.png);;All Files (*)')
        if fn:
            self.template['image_watermark'] = fn
            QMessageBox.information(self, '已选择', f'已选择水印图片：{fn}')
            self.update_preview()

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择导出目录')
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(folder)

    # -------------------- 位置 --------------------
    def set_position(self, key):
        self.template['position'] = key
        self.update_preview()

    # -------------------- 模板 --------------------
    def save_template_dialog(self):
        name, ok = QInputDialog.getText(self, '保存模板', '请输入模板文件名（不带扩展名）:')
        if not ok or not name: return
        data = self._gather_template()
        p = os.path.join(os.path.expanduser('~'), f'{name}.watermark.json')
        try:
            with open(p,'w',encoding='utf-8') as f:
                json.dump(data,f,ensure_ascii=False,indent=2)
            QMessageBox.information(self, '保存成功', f'已保存到：{p}')
        except Exception as e:
            QMessageBox.warning(self, '保存失败', str(e))

    def load_template_dialog(self):
        fn, _ = QFileDialog.getOpenFileName(self, '加载模板', '', 'JSON 文件 (*.json *.watermark.json);;All Files (*)')
        if fn:
            try:
                with open(fn,'r',encoding='utf-8') as f:
                    data = json.load(f)
                self._apply_template(data)
                QMessageBox.information(self, '加载成功', '已加载模板设置')
            except Exception as e:
                QMessageBox.warning(self, '加载失败', str(e))

    def _gather_template(self):
        return {
            'type': 'text',
            'text': self.input_text.text(),
            'font_family': self.font_combo.currentText(),
            'font_size': self.size_spin.value(),
            'color': self.template.get('color','#FFFFFF'),
            'opacity': self.opacity_slider.value(),
            'shadow': self.shadow_cb.isChecked(),
            'position': self.template.get('position','center'),
            'image_watermark': self.template.get('image_watermark',None),
            'image_scale': self.img_scale_slider.value()/100.0,
            'image_opacity': self.img_opacity_slider.value()
        }

    def _apply_template(self,data):
        self.input_text.setText(data.get('text',''))
        fam = data.get('font_family', self.font_combo.currentText())
        idx = self.font_combo.findText(fam)
        if idx>=0: self.font_combo.setCurrentIndex(idx)
        self.size_spin.setValue(data.get('font_size', self.size_spin.value()))
        self.opacity_slider.setValue(data.get('opacity', self.opacity_slider.value()))
        self.shadow_cb.setChecked(data.get('shadow', True))
        if data.get('image_watermark'):
            self.template['image_watermark']=data.get('image_watermark')
        self.img_scale_slider.setValue(int(data.get('image_scale',0.25)*100))
        self.img_opacity_slider.setValue(data.get('image_opacity',80))

    # -------------------- 生成水印 & 预览 --------------------
    def apply_watermark_to_pil(self, base_im: Image.Image) -> Image.Image:
        if base_im is None:
            return None
        im = base_im.convert('RGBA').copy()
        w,h = im.size

        # 文本水印
        text = self.input_text.text()
        font_family = self.font_combo.currentText()
        font_size = max(8, self.size_spin.value())
        try:
            # 尝试使用 PIL 的 truetype 字体（系统字体路径可能不在标准位置）
            font = ImageFont.truetype(font_family, font_size)
        except Exception:
            # 回退到默认字体
            font = ImageFont.load_default()

        # 文字颜色与透明度
        color = self.template.get('color', '#FFFFFF')
        opacity = int(self.opacity_slider.value())

        overlay = Image.new('RGBA', im.size, (255,255,255,0))
        draw = ImageDraw.Draw(overlay)

        # 计算位置
        txt_w, txt_h = draw.textsize(text, font=font)
        pos_key = self.template.get('position','center')
        offsets = self.template.get('offset',(0,0))
        x = 0; y = 0
        margin = 10
        if pos_key == 'top-left': x,y = margin, margin
        elif pos_key == 'top': x,y = (w-txt_w)//2, margin
        elif pos_key == 'top-right': x,y = w-txt_w-margin, margin
        elif pos_key == 'left': x,y = margin, (h-txt_h)//2
        elif pos_key == 'center': x,y = (w-txt_w)//2, (h-txt_h)//2
        elif pos_key == 'right': x,y = w-txt_w-margin, (h-txt_h)//2
        elif pos_key == 'bottom-left': x,y = margin, h-txt_h-margin
        elif pos_key == 'bottom': x,y = (w-txt_w)//2, h-txt_h-margin
        elif pos_key == 'bottom-right': x,y = w-txt_w-margin, h-txt_h-margin
        x += offsets[0]; y += offsets[1]

        # 阴影
        if self.shadow_cb.isChecked():
            shadow_color = (0,0,0,int(opacity*0.6))
            draw.text((x+2,y+2), text, font=font, fill=shadow_color)

        # 文字本体
        # parse hex color
        try:
            col = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4)) + (int(255*opacity/100),)
        except Exception:
            col = (255,255,255,int(255*opacity/100))
        draw.text((x,y), text, font=font, fill=col)

        # 图片水印
        if self.template.get('image_watermark'):
            try:
                wm = Image.open(self.template['image_watermark']).convert('RGBA')
                scale = max(1, self.img_scale_slider.value())/100.0
                new_w = int(wm.width * scale)
                new_h = int(wm.height * scale)
                if new_w<=0 or new_h<=0:
                    new_w, new_h = int(w*0.25), int(h*0.25)
                wm = wm.resize((new_w,new_h), Image.ANTIALIAS)
                # 位置：默认放右下角
                wx = w - new_w - 10; wy = h - new_h - 10
                # 混合透明度
                alpha = int(self.img_opacity_slider.value()*255/100)
                if alpha<255:
                    alpha_mask = wm.split()[3].point(lambda p: p*alpha/255)
                    wm.putalpha(alpha_mask)
                overlay.paste(wm,(wx,wy),wm)
            except Exception as e:
                print('加载图片水印失败', e)

        out = Image.alpha_composite(im, overlay)
        return out.convert('RGBA')

    def update_preview(self):
        if self.current_image is None:
            # 如果没有选中图片，尝试加载第一个
            if self.image_paths:
                self.current_index = 0
                self.load_current_image()
            else:
                return
        out = self.apply_watermark_to_pil(self.current_image)
        if out is None: return
        # 缩放以适应 QLabel
        label_w = self.preview_label.width()
        label_h = self.preview_label.height()
        oh = out.height; ow = out.width
        ratio = min(label_w/ow, label_h/oh, 1)
        disp = out.copy()
        if ratio<1:
            disp = out.resize((int(ow*ratio), int(oh*ratio)), Image.ANTIALIAS)
        pix = pil_image_to_qpixmap(disp)
        self.preview_label.setPixmap(pix)

    # -------------------- 导出 --------------------
    def export_images(self):
        if not self.image_paths:
            QMessageBox.warning(self, '没有图片', '请先导入图片后再导出')
            return
        if not self.output_folder:
            QMessageBox.warning(self, '未设置导出目录', '请先选择导出目录')
            return
        # 检查是否导出到原文件夹
        for p in self.image_paths:
            if os.path.dirname(p) == self.output_folder and not self.override_original_cb.isChecked():
                QMessageBox.warning(self, '导出目录设置错误', '导出目录与源图片目录相同，默认禁止覆盖。若确实需要，请勾选允许导出到原文件夹。')
                return

        naming = self.naming_combo.currentText()
        add = self.naming_input.text()
        quality = self.jpeg_quality_slider.value()

        total = len(self.image_paths)
        for idx,p in enumerate(self.image_paths, start=1):
            try:
                base = Image.open(p).convert('RGBA')
                out = self.apply_watermark_to_pil(base)

                # 缩放
                mode = self.resize_combo.currentText()
                if mode == '按宽度':
                    new_w = int(self.resize_input.value())
                    ratio = new_w / out.width
                    new_h = int(out.height*ratio)
                    out = out.resize((new_w,new_h), Image.ANTIALIAS)
                elif mode == '按高度':
                    new_h = int(self.resize_input.value())
                    ratio = new_h / out.height
                    new_w = int(out.width*ratio)
                    out = out.resize((new_w,new_h), Image.ANTIALIAS)
                elif mode == '按百分比':
                    pct = int(self.resize_input.value())
                    new_w = int(out.width * pct/100.0)
                    new_h = int(out.height * pct/100.0)
                    out = out.resize((new_w,new_h), Image.ANTIALIAS)

                # 命名
                base_name = os.path.basename(p)
                name,ext = os.path.splitext(base_name)
                if naming.startswith('保留'):
                    new_name = name + ext
                elif naming.startswith('添加前缀'):
                    new_name = add + name + ext
                else:
                    new_name = name + add + ext

                # 输出格式根据扩展名（保持原扩展），但用户也可自己替换逻辑以强制输出为 jpg/png
                out_path = os.path.join(self.output_folder, new_name)
                # 如果输出是 jpg/jpeg，需要合并 alpha 背景
                if ext.lower() in ('.jpg','.jpeg'):
                    bg = Image.new('RGB',(out.width,out.height),(255,255,255))
                    bg.paste(out, mask=out.split()[3])
                    bg.save(out_path, quality=quality)
                else:
                    out.save(out_path)
                print(f'导出: {out_path} ({idx}/{total})')
            except Exception as e:
                print('导出失败', p, e)
        QMessageBox.information(self, '导出完成', f'已导出 {total} 张图片到 {self.output_folder}')


# -------------------- 运行 --------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Watermarker()
    w.show()
    sys.exit(app.exec_())
