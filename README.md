# AutoSedance (Manual Upload)

AutoSedance is an interactive AI video workflow: the system generates scripts/storyboards and maintains continuity, while you manually generate/upload each video segment.

AutoSedance 是一个交互式 AI 视频工作流：系统负责剧本/分镜与连续性控制，你负责手动生成并上传每个片段视频。

## Live Demo / 在线体验

- Web UI: `https://autosedance.vercel.app/new`
- Health check: `https://autosedance.vercel.app/api/health` should return `{"ok":true}`.

Notes / 说明:

- The demo is public and invite-gated. Please do not upload sensitive content.
- 该 Demo 为公开环境且需要邀请码注册，请勿上传敏感内容。

## Theme / 主题

- Default: Light (anime / kawaii UI).
- Alternate: Dark.
- Saved in cookie: `autos_theme=light|dark` (legacy values `anime`/`default` are still accepted).

## Workflow / 工作流程

1. Create a project, the system generates the full script and the first segment prompt.
2. You generate the segment video with any external tool and upload it.
3. The system analyzes the uploaded segment and carries continuity into the next segment.
4. Repeat until done, then the system assembles the final video.

1. 创建项目，系统生成完整剧本与第一个片段的提示词。
2. 你用任意外部工具生成该片段视频并上传。
3. 系统理解视频内容并将连续性传递给下一个片段。
4. 循环直到完成，最后自动拼接输出成片。

## Local Development / 本地运行

### 1) Backend API / 后端 API

```bash
cp .env.example .env
# edit .env and set at least:
# - VOLCENGINE_API_KEY
# - AUTH_SECRET_KEY (recommended)

uv pip install -e .
# or:
# pip install -e .
autosedance server --reload
```

The API runs on `http://127.0.0.1:8000`.

### 2) Frontend Web / 前端 Web

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3612`.

## Login / 登录

- Register: invite code + email + password (+ optional profile fields).
- Login: username + password.
- After registering, you will receive 5 new invite codes (see `/invites`).

- 注册：邀请码 + 邮箱 + 密码（以及可选的来源/国家/意见等字段）。
- 登录：用户名 + 密码。
- 注册成功后会获得 5 个新的邀请码（见 `/invites`）。

Local seed invite codes are written to `output/invite_seed_codes.txt` after the backend starts.

本地首次邀请码会在后端启动后写入 `output/invite_seed_codes.txt`。

## Deployment / 部署

### Frontend (Vercel) / 前端（Vercel）

Set the Vercel Project Root Directory to `apps/web`.

Set `BACKEND_INTERNAL_URL` on Vercel and redeploy:

- Preview: `http://<ECS_IP>/api-staging`
- Production: `http://<ECS_IP>/api`

Do not set `NEXT_PUBLIC_BACKEND_URL` on Vercel, keep the browser on same-origin `/api/*`.

Custom domain (e.g. `aiden-novak.com`): add it in Vercel Project → Domains and follow the DNS instructions.

### Backend (ECS/VM) / 后端（ECS/云服务器）

Run Uvicorn on `127.0.0.1` and expose only Nginx `:80/:443`, proxy `/api/*` to the backend.

See templates in `deploy/ecs/`.

## License

Apache-2.0
