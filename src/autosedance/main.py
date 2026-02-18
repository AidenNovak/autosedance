"""CLI entrypoint."""

import click

@click.group()
def main():
    """AutoSedance - manual-upload video workflow.

    Start the backend for the web UI:
        autosedance server --reload
    """


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
