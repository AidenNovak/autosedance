# AutoSedance

AI视频生成Agent系统，基于LangGraph实现从文本到视频的自动化闭环生产。

当前默认工作方式为 **人工上传视频片段**：
系统负责生成剧本/分镜（in0/inN），并在你上传每个片段视频后进行视频理解（inNB）与连续性传递，最后拼接输出完整视频。

## 功能

- 🎬 **智能编剧**：根据用户需求自动生成完整剧本
- 🎞️ **自动分片**：将剧本分解为片段
- 🎥 **多模型支持**：支持通义万相Wan2.6和火山引擎Seedance
- 👁️ **视频理解**：多模态模型分析视频内容
- 🔗 **闭环控制**：自动保持片段间的连续性
- 📼 **自动拼接**：将所有片段合并为完整视频

## 支持的视频模型

| 模型 | 提供商 | 片段时长 | 特点 |
|------|--------|----------|------|
| `wan` | 阿里云通义万相 | 15秒 | 支持音频生成 |
| `seedance` | 火山引擎 | 15秒 | 支持参考图片 |

## 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/autosedance.git
cd autosedance

# 安装依赖 (使用 uv)
uv pip install -e .

# 或使用 pip
pip install -e .
```

## 配置

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入API Key：
```bash
# 火山引擎 (用于豆包LLM)
VOLCENGINE_API_KEY=your_volcengine_api_key

# 阿里云 DashScope (可选；用于 Wan 视频生成)
DASHSCOPE_API_KEY=your_dashscope_api_key

# 默认视频模型
VIDEO_MODEL=wan  # 可选: wan 或 seedance

# (可选) Server 数据库存储
# DATABASE_URL=sqlite:///output/autosedance.sqlite3
# OUTPUT_DIR=output
```

## 使用

### Web UI（推荐：交互式、可恢复）

1) 启动后端 API：

```bash
autosedance server --reload
# 或（未安装 entrypoint 时）
python3 -m autosedance.main server --reload
```

2) 启动前端：

```bash
cd apps/web
npm install
npm run dev
```

打开 `http://localhost:3000`，按页面流程生成 in0/inN，上传每段视频，点击 Analyze 进入下一段，最后 Assemble。

### CLI（当前会在等待视频时结束）

```bash
# 使用通义万相生成60秒视频 (默认)
autosedance -p "一个城市夜行者的赛博朋克故事" -d 60

# 使用Seedance生成60秒视频
autosedance -p "森林中的小鹿在晨光中醒来" -d 60 -m seedance

# 生成30秒视频
autosedance -p "小猫在花园里玩耍" -d 30 -m wan
```

### Archive / Legacy

一些历史脚本与说明文档已归档到 `archive/`，不影响 Web UI 使用。

## 工作流程

```
START → 编剧 → 分片 → 视频生成 → 视频理解 → [判断]
                                          ↓
                              继续生成 → 递增索引 → 分片 (循环)
                              全部完成 → 拼接 → END
```

## 技术栈

- **框架**: LangGraph
- **语言模型**: 豆包 seed 2.0 pro
- **视频生成**: 通义万相 Wan2.6 / 火山引擎 Seedance
- **视频处理**: ffmpeg

## 项目结构

```
autosedance/
├── apps/web/            # Next.js 前端
├── src/autosedance/
│   ├── config/          # 配置管理
│   ├── state/           # 状态定义
│   ├── nodes/           # LangGraph节点
│   ├── clients/         # API客户端
│   │   ├── doubao.py    # 豆包LLM客户端
│   │   ├── wan.py       # 通义万相客户端
│   │   └── seedance.py  # Seedance客户端
│   ├── prompts/         # Prompt模板
│   ├── utils/           # 工具函数
│   └── graph/           # 工作流定义
│   └── server/          # FastAPI + SQLite 后端
└── output/              # 输出目录
```

## License

MIT
