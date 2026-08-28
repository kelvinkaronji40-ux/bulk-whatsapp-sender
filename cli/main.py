import typer
from pathlib import Path
import uvicorn


app = typer.Typer()


@app.command()
def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False, open: bool = False):
    """Run the Bulk WhatsApp Sender web UI."""
    import os
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{Path.home()}/.bulk_whatsapp/bulk.db")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command()
def init():
    """Initialize the local database."""
    import asyncio
    from app.database import init_db
    asyncio.run(init_db())
    typer.echo("Database initialized.")


if __name__ == "__main__":
    app()
