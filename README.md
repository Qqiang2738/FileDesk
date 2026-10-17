# 文序 · FileDesk V1.0.0

**状态：V1.0 正式版候选发布（macOS 本地网页版）。** V0.7.0 已经由实际使用者在 macOS 上验收通过；V1.0.0 沿用已认可的智能文件工作台与转换引擎，重点完成发布质量、安全、启动、诊断与文档。V1.0.0 本身还需要在目标 Mac 上最终验收。

**产品主张：文件决定操作。** 将 PDF、Word、Excel、CSV 或图片放进工作台，系统按文件类型和数量推荐操作；可以先预览 PDF/图片，确认后处理并下载。没有常驻工具菜单，也没有桌面 WebView 外壳。

## 立即开始（macOS）

1. 将 V1.0 ZIP 解压至**新的** `FileDesk-v1.0.0` 文件夹；保留 V0.7.0 作为已验收回退版本。
2. 先结束旧版终端中的服务（`Control + C`）。V1.0 会主动检测并阻止旧、新服务同时运行。
3. 安装 Python **3.11 或更新版本**。旧 `.xls` / 部分 Office 任务还需要独立安装 LibreOffice。
4. 双击 `start-mac.command`。首次启动会在项目目录的 `.venv` 中安装 Python 依赖；无须另开桌面 APP。
5. 浏览器会自动打开本机网址（通常为 `http://127.0.0.1:8765`），页脚应显示 **V1.0.0**。把文件拖进窗口即可。
6. 关闭文序时，在启动它的终端按 `Control + C`。只关闭浏览器标签页并不会停止本机服务。

更详细的排障与升级说明见 [`QUICKSTART_MAC.md`](QUICKSTART_MAC.md)。如果发现启动或中文转换异常，可双击 `doctor-mac.command` 生成不读取工作文件的环境自检结果。

## 已有能力（保持稳定基线）

| 场景 | 现有能力 |
|---|---|
| PDF | 合并、拆分、提取、删除与旋转页面、优化压缩、转图片、转可编辑 Word |
| Word / Office | Word、PPT 和部分 Office 文件转 PDF；部分 DOCX 使用清晰重排模式 |
| Excel / CSV | 智能排版 PDF、可编辑 Word、Excel 导出 CSV、CSV 导入与转换；大表格分册处理并保留完整字段 CSV |
| 图片 | PNG、JPG、WebP 等图片转换与图片合成 PDF；正确的下载扩展名 |
| PDF / 图片预览 | PDF 按页翻看及缩略图；PDF 合并文件先后排序；常见图片预览 |
| 文件工作流 | 拖拽批量导入、智能推荐、进度显示、取消任务、另存为新文件、完成后返回工作台、历史重新下载 |

**不保证所有格式 100% 保真。** PDF 转 Word 的可编辑表格重建依赖能检测到的表格线和文本；扫描型 PDF 不包含通用 OCR。Word 清晰排版模式优先保证可读内容，复杂版式可能改变。Excel 分册时，Word 只放便于编辑的核心列，其余原始数据值在同包 CSV 里供核对。

## V1.0 新增的发布加固

- **防重复启动：** 检查已有的 FileDesk 本机服务；同版本已启动则使用现有网址，遇到旧版时提示先退出。额外使用跨进程文件锁，降低历史记录并发写入风险。
- **环境检查：** `doctor-mac.command` / `python -m filedesk.diagnostics` 检查 Python、转换依赖、LibreOffice 和本地文件夹可写性；不访问业务文件内容。
- **浏览器安全：** 保持服务器只监听 `127.0.0.1`，保留 Origin/Host 校验，增加 CSP、禁止嵌入及无引用来源等响应头。项目不提供云端服务。
- **版本一致性：** 后端版本统一读取 `filedesk/version.py`，前端页面、JS 与 CSS 使用同版本标识，并通过自动化测试防止缓存错配。
- **规范发布：** 项目包附 `SHA256SUMS.txt` 文件校验清单、测试矩阵、许可注意事项、Mac 安装排障和正式版发布说明；不打包用户上传的业务文件、历史库或开发虚拟环境。

## 数据与服务边界

- 仅监听本机回环地址；工作文件不会传到第三方文件转换网站。首次安装依赖可能通过 pip 联网下载程序包，但不上传工作文件。
- 上传的临时副本在任务结束后清理；结果历史保存在本机，默认最多 **20 条、7 天、总计 600 MB**，可随时通过 UI 清空。历史中不永久存储源文档，输出结果可能含原文件敏感信息。
- 单个上传文件不超过 **65 MB**；每批最多 **35 文件 / 200 MB**；单次结果不超过 **450 MB**。超大表格还受行列、非空单元格及资源安全边界约束。
- 当前**不是**公网 SaaS、macOS 原生客户端、已签名 `.app`、自动更新产品；不要将此服务绑定至公网地址。

## 测试、打包和项目结构

```bash
PYTHONPATH=. python -m pytest -q              # 需自行安装 pytest、httpx 等测试依赖
python tests/browser_smoke_v060.py            # 需 Playwright 和 Chromium
python tests/browser_smoke_v070.py
python -m filedesk.diagnostics
python scripts/make_release.py                # 生成带 SHA256SUMS.txt 的 ZIP
```

核心目录：`filedesk/`（服务、转换、预览、历史与任务管理）、`web/`（极简工作台）、`tests/`（合成测试用例）、`docs/`（界面截图）、`scripts/`（打包）、`main.py`（本机启动）。`QA_MATRIX.md` 对应测试清单；`RELEASE_CHECKLIST.md` 记录目标 Mac 上需要验收的项目。

## 许可证与产品化限制

**V1.0 面向当前本机工作流验收，不能仅凭这个 ZIP 直接认定为允许闭源商用分发的版本。** PyMuPDF / MuPDF 有 AGPLv3 和商业许可证路线；LibreOffice 与 PDFium 相关组件也各有再分发要求。若后续对外提供下载、收费服务或部署到服务器，须先完成依赖许可证及代码权利核查。具体依据见 [`PRIVACY_AND_LICENSE.md`](PRIVACY_AND_LICENSE.md)。

终端提示 `Consider using the pymupdf_layout package for a greatly improved page layout analysis.` 仅是可选布局分析建议，不是错误；目前无需安装此插件。
