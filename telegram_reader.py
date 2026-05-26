import os
import logging
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

log = logging.getLogger(__name__)

# Retail = private channel, Wholesale = public channel
RETAIL_CHANNEL = "https://t.me/+MTqIH-AFFjNmNTUy"
WHOLESALE_CHANNEL = "svitkovbas"


async def _fetch_yesterday_posts(client: TelegramClient, channel) -> list[dict]:
    """Return list of {photo_bytes, caption} from yesterday in the channel."""
    kyiv = timezone(timedelta(hours=3))
    today = datetime.now(kyiv).date()
    yesterday = today - timedelta(days=1)

    posts = []
    async for msg in client.iter_messages(channel, limit=50):
        if not msg.date:
            continue
        msg_date = msg.date.astimezone(kyiv).date()
        if msg_date < yesterday:
            break
        if msg_date != yesterday:
            continue
        if not msg.photo:
            continue
        photo_bytes = await client.download_media(msg.photo, bytes)
        posts.append({
            "caption": msg.text or "",
            "photo": photo_bytes,
            "date": msg.date,
        })

    return posts


async def fetch_posts_for_today() -> dict:
    """
    Returns:
        {
            "retail": [...],    # posts from retail (private) channel
            "wholesale": [...], # posts from wholesale (@svitkovbas) channel
        }
    """
    api_id = int(os.environ["TG_API_ID"])
    api_hash = os.environ["TG_API_HASH"]
    session_string = os.environ["TG_SESSION_STRING"]

    result = {"retail": [], "wholesale": []}

    async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
        try:
            result["retail"] = await _fetch_yesterday_posts(client, RETAIL_CHANNEL)
            log.info(f"Retail posts yesterday: {len(result['retail'])}")
        except Exception as e:
            log.error(f"Error reading retail channel: {e}")

        try:
            result["wholesale"] = await _fetch_yesterday_posts(client, WHOLESALE_CHANNEL)
            log.info(f"Wholesale posts yesterday: {len(result['wholesale'])}")
        except Exception as e:
            log.error(f"Error reading wholesale channel: {e}")

    return result
