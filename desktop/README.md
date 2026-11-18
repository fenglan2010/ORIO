# OIRO Desktop Shell

Electron 壳层启动本机 FastAPI（SQLite 在用户数据目录），加载既有 Vue 前端。

## 开发

```bash
# 终端 1 — 后端（源码模式，无安装密钥）
cd /workspace
make dev

# 终端 2 — 仅 Electron 窗口（指向 Vite）
cd desktop && npm install && OIRO_DEV_URL=http://127.0.0.1:5173 npm start
```

测试**正式包安装密钥门闩**：

```bash
OIRO_DISTRIBUTION=packaged OIRO_INSTALL_KEY_ACCEPT=OIRO-TEST-0000-0000-0000 bash scripts/dev.sh
```

## Windows 安装包

在 **Windows** 上执行 `scripts/build-windows.ps1`。本 Linux CI 环境不产出已签名的 `.exe`，仅提供可复现脚本与 `electron-builder` 配置。

正式安装包设置 `OIRO_DISTRIBUTION=packaged`；开源从源码运行保持默认 `source`，无需安装密钥。