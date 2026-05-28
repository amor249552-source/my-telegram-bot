web: gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 bot:app
worker: python -c "
import asyncio
from bot import run_telegram
asyncio.run(run_telegram()) if callable(run_telegram) else None
"
