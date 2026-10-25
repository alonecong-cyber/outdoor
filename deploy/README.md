# 部署（macOS launchd，无 Docker）

按研发计划，本项目在 Intel Mac 上用 launchd 常驻，不使用容器。

## 前置

```bash
# 后端：uv 管理的虚拟环境已就绪（backend/.venv）
cd backend && uv sync && uv run python scripts/seed_dev.py   # 可选：灌演示数据

# 前端：已构建产物
cd frontend && pnpm install && pnpm build
```

## 安装服务

两个 plist 已写好本机绝对路径（`/Users/lance/Documents/pi/outdoordeal`）：

```bash
mkdir -p ~/Library/LaunchAgents frontend/var backend/var
cp deploy/com.outdoordeal.backend.plist deploy/com.outdoordeal.frontend.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.outdoordeal.backend.plist
launchctl load ~/Library/LaunchAgents/com.outdoordeal.frontend.plist
```

- 后端：`http://127.0.0.1:8000`（uvicorn，`KeepAlive` 自动拉起，日志在 `~/Library/Logs/outdoordeal/`）
- 前端：`http://127.0.0.1:3000`（`next start`，`/api/*` 同源反代到后端）

## macOS 注意事项（踩过的坑）

- plist 里不要写 `WorkingDirectory` 指向 `~/Documents` 下目录：macOS TCC 会拒绝
  launchd 子进程预执行 chdir，job 反复以 `EX_CONFIG (78)` 失败。工作目录改为在
  `zsh -lc` 命令内 `cd`（两个 plist 均已如此）。
- 后端日志放 `~/Library/Logs/outdoordeal/`（launchd 对 Documents 内日志文件的
  创建行为不可靠）；前端日志在 `frontend/var/`。
- `SCHEDULER_ENABLED=true` 已写入 `backend/.env`，定时采集/线报/关注检查默认开启。

## 日常操作

```bash
launchctl list | grep outdoordeal          # 查看状态
launchctl kickstart -k gui/$UID/com.outdoordeal.backend   # 重启后端
tail -f ~/Library/Logs/outdoordeal/backend.err.log        # 排错
launchctl unload ~/Library/LaunchAgents/com.outdoordeal.frontend.plist  # 停止
```

## 提醒渠道

编辑 `backend/.env`（参照 `backend/.env.example`）配置 TELEGRAM / WECOM / SMTP，
并设 `SCHEDULER_ENABLED=true` 开启定时采集与提醒推送。
