import asyncio
import os
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from facebook_client import FacebookClient
from ai_handler import AIHandler
from database import Database
from analyze_trends import analyze_and_draft
from telegram_reader import fetch_todays_posts

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Facebook pages relevant to food/HoReCa in Ukraine — add page IDs here
PAGES_TO_MONITOR: list[str] = [
    # "123456789",  # example: food retailer page ID
]


def make_client() -> FacebookClient:
    return FacebookClient(
        page_id=os.environ["FB_PAGE_ID"],
        access_token=os.environ["FB_PAGE_ACCESS_TOKEN"],
    )


def evening_check():
    """
    19:00 job:
    1. Read today's posts from both TG channels.
    2. Save all of them to reserve (always).
    3. If FB already has a post today → do nothing more.
    4. If no FB post today → publish: retail first, else wholesale, else pending reserve, else AI.
    """
    log.info("=== Evening check ===")
    db = Database()
    fb = make_client()
    ai = AIHandler(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        tg = asyncio.run(fetch_todays_posts())
        retail = tg.get("retail", [])
        wholesale = tg.get("wholesale", [])

        # Always save all relevant TG posts to reserve
        for post in retail + wholesale:
            if ai.is_still_relevant(post["caption"]):
                db.save_pending_wholesale(post["caption"], post["photo"])
                log.info("Saved TG post to reserve.")

        # Check if SMM already posted today
        if fb.posted_today():
            log.info("FB already has a post today — skipping publish.")
            return

        # Decide what to publish
        relevant_retail = [p for p in retail if ai.is_still_relevant(p["caption"])]
        relevant_wholesale = [p for p in wholesale if ai.is_still_relevant(p["caption"])]

        if relevant_retail:
            to_post = relevant_retail[0]
            source = "retail"
        elif relevant_wholesale:
            to_post = relevant_wholesale[0]
            source = "wholesale"
        else:
            pending = db.pop_pending_wholesale()
            if pending:
                to_post = pending
                source = "reserve"
            else:
                to_post = None
                source = "AI"

        if to_post:
            log.info(f"Publishing from {source}.")
            success = fb.post_photo(to_post["photo"], to_post["caption"])
            if success:
                db.mark_daily_post()
        else:
            # Fallback: AI post with photo from local library
            log.info("No TG content — publishing AI post with photo.")
            photo_path = ai.pick_suitable_photo()
            if photo_path:
                post_text = ai.generate_post_with_photo(photo_path)
                if fb.post_photo(photo_path.read_bytes(), post_text):
                    db.mark_daily_post()
            else:
                post_text = ai.generate_daily_post()
                if fb.create_post(post_text):
                    db.mark_daily_post()

    except Exception as e:
        log.error(f"evening_check error: {e}")
    finally:
        db.close()

    log.info("=== Evening check done ===")


def daily_post():
    log.info("=== Daily post run ===")
    db = Database()

    if db.posted_today():
        log.info("Already posted today, skipping.")
        db.close()
        return

    try:
        ai = AIHandler(api_key=os.environ["ANTHROPIC_API_KEY"])
        client = make_client()

        own_posts = client.get_own_posts(limit=10)
        posts_with_stats = [
            {
                "message": p.get("message", ""),
                "likes": p.get("likes", {}).get("summary", {}).get("total_count", 0),
                "comments": p.get("comments", {}).get("summary", {}).get("total_count", 0),
            }
            for p in own_posts if p.get("message")
        ]

        if posts_with_stats:
            result = analyze_and_draft(posts_with_stats, os.environ["ANTHROPIC_API_KEY"])
            post_text = result.split("ПОСТ:")[-1].strip() if "ПОСТ:" in result else ""

        if not posts_with_stats or not post_text:
            post_text = ai.generate_daily_post()

        log.info(f"Post text: {post_text}")
        success = client.create_post(post_text)

        if success:
            db.mark_daily_post()
            log.info("Post published.")
        else:
            log.error("Failed to publish post.")
    except Exception as e:
        log.error(f"Daily post error: {e}")
    finally:
        db.close()

    log.info("=== Daily post done ===")


def reply_to_own_comments():
    log.info("=== Reply to own comments ===")
    db = Database()

    try:
        ai = AIHandler(api_key=os.environ["ANTHROPIC_API_KEY"])
        client = make_client()

        own_posts = client.get_own_posts(limit=5)
        replied_count = 0

        for post in own_posts:
            if replied_count >= 5:
                break
            post_id = post["id"]
            comments = client.get_post_comments(post_id)

            for comment in comments:
                if replied_count >= 5:
                    break
                comment_id = comment["id"]
                text = comment.get("message", "")
                if not text or db.already_processed(comment_id):
                    continue

                response = ai.generate_reply(text)
                if not response:
                    db.mark_skipped(comment_id)
                    continue

                log.info(f"Replying to comment {comment_id}: {response}")
                success = client.reply_to_comment(comment_id, response)
                if success:
                    db.mark_replied(comment_id)
                    replied_count += 1
                else:
                    db.mark_skipped(comment_id)
    except Exception as e:
        log.error(f"Reply error: {e}")
    finally:
        db.close()

    log.info("=== Reply done ===")


def comment_on_other_pages():
    if not PAGES_TO_MONITOR:
        log.info("No pages to monitor, skipping.")
        return

    log.info("=== Comment on other pages ===")
    db = Database()

    try:
        ai = AIHandler(api_key=os.environ["ANTHROPIC_API_KEY"])
        client = make_client()

        for page_id in PAGES_TO_MONITOR:
            posts = client.get_page_posts(page_id, limit=5)
            for post in posts:
                post_id = post["id"]
                text = post.get("message", "")
                if not text or db.already_processed(post_id):
                    continue

                reply = ai.generate_reply(text)
                if not reply:
                    db.mark_skipped(post_id)
                    continue

                log.info(f"Commenting on {post_id}: {reply}")
                success = client.comment_on_post(post_id, reply)
                if success:
                    db.mark_replied(post_id)
                else:
                    db.mark_skipped(post_id)
                return  # one comment per run
    except Exception as e:
        log.error(f"Comment error: {e}")
    finally:
        db.close()

    log.info("=== Comment done ===")


def main():
    scheduler = BlockingScheduler(
        executors={"default": ThreadPoolExecutor(1)},
        timezone="Europe/Kyiv",
    )
    scheduler.add_job(evening_check, "cron", hour=19, minute=0, id="evening_check")
    scheduler.add_job(reply_to_own_comments, "cron", hour="8-21", minute="0,30", id="own_replies")
    scheduler.add_job(comment_on_other_pages, "cron", hour="9,12,15,18", minute=0, id="other_pages")

    log.info("Scheduler started: evening check 19:00, replies every 30min (8-21), comments 4x/day.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Stopped.")


if __name__ == "__main__":
    main()
