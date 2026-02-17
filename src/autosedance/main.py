"""CLI 入口"""

import asyncio
from typing import Optional

import click

from .config import get_settings
from .graph.workflow import build_workflow
from .state.schema import GraphState


@click.group(invoke_without_command=True)
@click.option("--prompt", "-p", required=False, help="视频内容描述 (生成模式必填)")
@click.option(
    "--duration", "-d", default=60, help="视频总时长（秒），默认60秒"
)
@click.option(
    "--model",
    "-m",
    type=click.Choice(["wan", "seedance"]),
    default=None,
    help="视频生成模型: wan(通义万相) 或 seedance(火山引擎)",
)
@click.option("--output", "-o", default="output/final/output.mp4", help="输出路径")
@click.pass_context
def main(ctx: click.Context, prompt: Optional[str], duration: int, model: Optional[str], output: str):
    """AutoSedance - AI视频生成系统

    支持的视频模型:
    - wan: 阿里云通义万相Wan2.6 (每段10秒)
    - seedance: 火山引擎Seedance (每段15秒)

    示例:
        autosedance -p "一个城市夜行者的赛博朋克故事" -d 60
        autosedance -p "森林中的小鹿" -d 30 -m wan
    """
    if ctx.invoked_subcommand is not None:
        return

    if not prompt:
        raise click.UsageError("Missing --prompt/-p. Example: autosedance -p \"...\" -d 60")

    settings = get_settings()

    # 命令行参数优先，否则使用配置文件
    video_model = model or settings.video_model

    # 根据模型确定片段时长（两者都支持15秒）
    segment_duration = 15

    # 计算片段数
    num_segments = duration // segment_duration
    if duration % segment_duration > 0:
        num_segments += 1

    click.echo(f"开始生成 {duration} 秒视频...")
    click.echo(f"视频模型: {video_model}")
    click.echo(f"片段时长: {segment_duration}秒")
    click.echo(f"提示词: {prompt}")
    click.echo(f"将生成 {num_segments} 个片段")

    # 初始化状态
    initial_state: GraphState = {
        "user_prompt": prompt,
        "total_duration_seconds": duration,
        "segment_duration": segment_duration,
        "full_script": None,
        "segments": [],
        "current_segment_index": 0,
        "canon_summaries": "",
        "last_frame_path": None,
        "final_video_path": None,
        "error": None,
    }

    # 构建工作流
    workflow = build_workflow()

    # 运行工作流
    async def run():
        result = await workflow.ainvoke(initial_state)
        return result

    try:
        result = asyncio.run(run())

        if result.get("error"):
            click.echo(f"错误: {result['error']}", err=True)
            return 1

        click.echo(f"\n视频生成完成!")
        click.echo(f"输出文件: {result.get('final_video_path', output)}")

        # 打印片段信息
        segments = result.get("segments", [])
        click.echo(f"\n生成了 {len(segments)} 个片段:")
        for seg in segments:
            click.echo(f"  - 片段{seg.index}: {seg.status}")

        return 0

    except KeyboardInterrupt:
        click.echo("\n用户中断")
        return 130
    except Exception as e:
        click.echo(f"运行错误: {str(e)}", err=True)
        return 1


@main.command("server")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, type=int, show_default=True)
@click.option("--reload/--no-reload", default=False, show_default=True)
def server(host: str, port: int, reload: bool):
    """Run the local FastAPI server for the web UI."""
    import uvicorn

    uvicorn.run(
        "autosedance.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
