# Photo Meta Organizer

一键式照片整理工具：按时间归档、修复元数据、批量重命名及清理垃圾文件。

## ✨ 核心功能
*   **Organize**: 自动按 `年份/月份` 归档照片 (支持 EXIF/文件时间，含 HEIC)。
*   **Fix**: 修复老照片 EXIF/PNG/HEIC 与 MP4/MOV 拍摄时间元数据 (基于文件夹名称)。
*   **Rename**: 标准化重命名 (`YYYYMMDD_HHMMSS_原名`).
*   **Clean Junk**: 清理小文件。

## 🚀 快速开始

### 1. 配置
复制示例配置并修改（推荐设定 `input_dirs` 和 `output_dir`）：
```bash
cp params/examples/organize.json params/my_run.json
vim params/my_run.json
```

### 2. 运行
默认开启演习模式 (`dry_run: true`)，安全无忧：
```bash
make run config=params/my_run.json
```

### 3. 帮助
查看所有命令和任务说明：
```bash
make help
```

## 📖 文档与结构
详细说明请参阅 [用户手册](docs/user_manual.md)。

*   `params/` - 配置文件 (含 `examples/` 模板)
*   `src/` - 源代码
*   `Makefile` - 项目入口

## 📄 许可证
MIT License
