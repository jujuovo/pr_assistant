# -*- coding: utf-8 -*-
"""
验证码生成模块 - 简化修正版
"""

import random
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 验证码字符集
CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

# 验证码默认参数
DEFAULT_WIDTH = 160  # 增加宽度
DEFAULT_HEIGHT = 60  # 增加高度
DEFAULT_LENGTH = 4
DEFAULT_BG_COLOR = (255, 255, 255)
DEFAULT_FONT_SIZE = 40  # 调整字体大小

# 尝试使用系统字体
def get_system_font(font_size=DEFAULT_FONT_SIZE):
    """尝试获取系统字体，如果失败则使用默认字体"""
    # 常见系统字体路径
    font_paths = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/times.ttf",
        # macOS
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Times.ttf",
        # Linux
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except:
                continue
    
    # 如果都失败，使用默认字体（但会很小）
    print("警告：未找到系统字体，使用默认小字体")
    return ImageFont.load_default()

def generate_captcha(length=DEFAULT_LENGTH, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                    font_size=DEFAULT_FONT_SIZE, bg_color=DEFAULT_BG_COLOR):
    """
    生成验证码图片 - 简化版本
    
    Args:
        length: 验证码字符长度
        width: 图片宽度
        height: 图片高度
        font_size: 字体大小
        bg_color: 背景颜色
    
    Returns:
        tuple: (验证码图片对象, 验证码字符串)
    """
    # 创建空白图片
    image = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(image)
    
    # 生成随机验证码文本
    captcha_text = ''.join(random.choices(CHARS, k=length))
    
    # 获取字体
    font = get_system_font(font_size)
    
    # 简单计算字符位置 - 每个字符平均分配空间
    char_width = width // length
    
    # 绘制每个字符
    for i, char in enumerate(captcha_text):
        # 随机颜色
        char_color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
        
        # 计算字符位置 - 居中显示
        x = i * char_width + (char_width - font_size) // 3
        y = (height - font_size) // 3 + random.randint(-5, 5)  # 轻微随机偏移
        
        draw.text((x, y), char, font=font, fill=char_color)
    
    # 添加干扰线
    for _ in range(5):
        line_color = (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))
        line_x1 = random.randint(0, width)
        line_y1 = random.randint(0, height)
        line_x2 = random.randint(0, width)
        line_y2 = random.randint(0, height)
        draw.line(((line_x1, line_y1), (line_x2, line_y2)), fill=line_color, width=1)
    
    # 添加干扰点
    for _ in range(100):
        point_color = (random.randint(0, 180), random.randint(0, 180), random.randint(0, 180))
        point_x = random.randint(0, width)
        point_y = random.randint(0, height)
        draw.point((point_x, point_y), fill=point_color)
    
    # 轻微模糊处理
    image = image.filter(ImageFilter.SMOOTH_MORE)
    
    return image, captcha_text