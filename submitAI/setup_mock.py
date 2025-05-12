import os
import sys
import shutil
from pathlib import Path

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 创建browser_use软链接到mock_browser_use
if not os.path.exists('browser_use'):
    if os.path.exists('mock_browser_use'):
        # 在Linux/macOS上创建软链接
        try:
            os.symlink('mock_browser_use', 'browser_use')
            print("已创建browser_use软链接指向mock_browser_use")
        except:
            # 如果软链接失败，尝试复制目录
            try:
                shutil.copytree('mock_browser_use', 'browser_use')
                print("已复制mock_browser_use到browser_use")
            except Exception as e:
                print(f"错误：无法创建browser_use目录: {e}")
    else:
        print("错误：mock_browser_use目录不存在")
else:
    print("browser_use目录已存在")

print("设置完成") 