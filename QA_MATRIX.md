# 文序 FileDesk V1.0.0 · 测试矩阵

| 类别 | 核心目标 | 自动化/人工依据 |
|---|---|---|
| 基础格式 | PDF 合并、拆分、提取、旋转、图片导出 | `tests/test_engine.py` |
| Office | 文字型 PDF → Word、Word → PDF、Excel/CSV → Word/PDF | `test_v053.py`、`test_v054.py`、`test_smart_excel.py`、`test_v056.py` |
| 大文件 | 真实采购清单分册回归、CSV 完整数据、取消和排队 | `test_v055.py`、`test_v056.py`、`test_v060.py`；部分真实样本未随包分发 |
| 预览 | PDF 页数、加密/异常、缩略图、TTL 清理、文件顺序同步 | `test_v070.py` + `browser_smoke_v070.py` |
| 交互 | 新任务、操作推荐、下载、历史、取消任务 | `browser_smoke_v060.py` |
| 本机安全 | Host/Origin、CSP、X-Frame、Referrer、缓存 | `test_v100.py` |
| 版本与启动 | 服务探测、跨进程锁、版本一致性、诊断脚本 | `test_v100.py` |
| 发布质量 | 不含历史/临时文件、源码 SHA256 清单和校验 | `test_release_bundle_v100.py` + `scripts/make_release.py` |

> 测试环境不是 macOS，因此 Apple 系统字体、LibreOffice 本地实例、脚本双击权限仍须按 `RELEASE_CHECKLIST.md` 进行 Mac 实机验收。PyMuPDF 的布局增强提示不是转换异常。

运行：

```bash
PYTHONPATH=. python -m pytest -q
python tests/browser_smoke_v060.py
python tests/browser_smoke_v070.py
python -m filedesk.diagnostics
```
