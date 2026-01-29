"""Custom server for uptop web interface.

Extends textual-serve Server to add favicon route support.
"""

from pathlib import Path

from aiohttp import web
from textual_serve.server import Server


class UptopServer(Server):
    """Extended Server with favicon support."""

    async def _make_app(self) -> web.Application:
        """Make the aiohttp web.Application with favicon route.

        Returns:
            New aiohttp web application with favicon support.
        """
        # Get the base app from parent
        app = await super()._make_app()

        # Add favicon route
        app.router.add_get("/favicon.ico", self.handle_favicon)

        return app

    async def handle_favicon(self, request: web.Request) -> web.Response:
        """Serve favicon.ico from static directory.

        Args:
            request: Request object.

        Returns:
            Favicon file response.
        """
        # Try to find favicon in static directory
        favicon_path = Path(__file__).parent.parent.parent / "static" / "favicon.ico"

        if favicon_path.exists():
            return web.FileResponse(
                favicon_path, headers={"Content-Type": "image/x-icon"}
            )

        # If not found, return 404
        raise web.HTTPNotFound()
