import requests
import logging

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v19.0"


class FacebookClient:
    def __init__(self, page_id: str, access_token: str):
        self.page_id = page_id
        self.token = access_token

    def _get(self, path: str, params: dict = None) -> dict | None:
        params = params or {}
        params["access_token"] = self.token
        try:
            r = requests.get(f"{GRAPH_URL}/{path}", params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"GET /{path} error: {e}")
            return None

    def _post(self, path: str, data: dict = None) -> dict | None:
        data = data or {}
        data["access_token"] = self.token
        try:
            r = requests.post(f"{GRAPH_URL}/{path}", data=data, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"POST /{path} error: {e}")
            return None

    def create_post(self, text: str) -> bool:
        result = self._post(f"{self.page_id}/feed", {"message": text})
        if result and "id" in result:
            log.info(f"Post created: {result['id']}")
            return True
        return False

    def get_own_posts(self, limit: int = 10) -> list[dict]:
        data = self._get(
            f"{self.page_id}/posts",
            {"fields": "id,message,created_time,likes.summary(true),comments.summary(true)", "limit": limit},
        )
        return data.get("data", []) if data else []

    def get_post_comments(self, post_id: str, limit: int = 25) -> list[dict]:
        data = self._get(
            f"{post_id}/comments",
            {"fields": "id,message,from,created_time", "limit": limit},
        )
        return data.get("data", []) if data else []

    def comment_on_post(self, post_id: str, text: str) -> bool:
        result = self._post(f"{post_id}/comments", {"message": text})
        if result and "id" in result:
            log.info(f"Commented on {post_id}: {result['id']}")
            return True
        return False

    def reply_to_comment(self, comment_id: str, text: str) -> bool:
        result = self._post(f"{comment_id}/comments", {"message": text})
        if result and "id" in result:
            log.info(f"Replied to comment {comment_id}: {result['id']}")
            return True
        return False

    def post_photo(self, photo: bytes, caption: str) -> bool:
        try:
            r = requests.post(
                f"{GRAPH_URL}/{self.page_id}/photos",
                data={"caption": caption, "access_token": self.token},
                files={"source": ("photo.jpg", photo, "image/jpeg")},
                timeout=30,
            )
            r.raise_for_status()
            result = r.json()
            if "id" in result:
                log.info(f"Photo posted: {result['id']}")
                return True
            return False
        except Exception as e:
            log.error(f"post_photo error: {e}")
            return False

    def get_page_posts(self, page_id: str, limit: int = 10) -> list[dict]:
        """Get recent posts from another public page."""
        data = self._get(
            f"{page_id}/posts",
            {"fields": "id,message,created_time", "limit": limit},
        )
        return data.get("data", []) if data else []
