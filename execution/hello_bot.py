"""
Simplest possible Teams bot - Hello World test
"""

from aiohttp import web


async def health(request):
    return web.Response(text="OK", status=200)


async def messages(request):
    return web.Response(text="Bot is alive!", status=200)


app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    # PORT configuration - can be overridden via command line args if needed
    PORT = 8000
    print(f"Starting Hello Bot on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)  # nosec B104 - Required for Azure App Service containerized deployment
