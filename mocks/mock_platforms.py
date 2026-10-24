"""Lightweight mock Discourse, Dev.to, and partner webhook for local certification."""

import hashlib
import hmac
import json
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="Mock Platforms")

_posts: dict[str, dict] = {}
_idempotency: dict[str, dict] = {}


@app.post("/posts.json")
async def discourse_create(request: Request, api_key: str = Header(default="", alias="Api-Key")):
    if not api_key:
        raise HTTPException(status_code=401, detail="auth required")
    body = await request.json()
    ext = body.get("external_id")
    if ext and ext in _idempotency:
        return _idempotency[ext]
    post_id = str(len(_posts) + 1)
    data = {
        "id": post_id,
        "topic_id": post_id,
        "url": f"http://mock-discourse/posts/{post_id}",
        "status": "live",
    }
    _posts[post_id] = data
    if ext:
        _idempotency[ext] = data
    return data


@app.get("/posts/{post_id}.json")
async def discourse_get(post_id: str):
    post = _posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404)
    return post


@app.delete("/posts/{post_id}.json")
async def discourse_delete(post_id: str):
    _posts.pop(post_id, None)
    return {"deleted": True}


@app.post("/api/articles")
async def devto_create(request: Request, api_key: str = Header(default="", alias="api-key")):
    if not api_key:
        raise HTTPException(status_code=401)
    body = await request.json()
    key = body.get("idempotency_key")
    if key and key in _idempotency:
        return _idempotency[key]
    post_id = str(len(_posts) + 100)
    data = {"id": post_id, "url": f"http://mock-devto/articles/{post_id}"}
    _posts[post_id] = data
    if key:
        _idempotency[key] = data
    return data


@app.get("/api/articles/{post_id}")
async def devto_get(post_id: str):
    if post_id not in _posts:
        raise HTTPException(status_code=404)
    return _posts[post_id]


@app.delete("/api/articles/{post_id}")
async def devto_delete(post_id: str):
    _posts.pop(post_id, None)
    return {"deleted": True}


@app.post("/")
async def webhook_receive(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-IncuBrix-Signature", "")
    expected = hmac.new(b"partner-secret", raw, hashlib.sha256).hexdigest()
    if sig != expected:
        raise HTTPException(status_code=401, detail="invalid signature")
    body = json.loads(raw)
    key = body.get("idempotency_key") or request.headers.get("Idempotency-Key")
    if key and key in _idempotency:
        return _idempotency[key]
    post_id = str(uuid4())
    data = {"id": post_id, "platform_post_id": post_id, "live_url": f"http://mock-webhook/posts/{post_id}"}
    _posts[post_id] = data
    if key:
        _idempotency[key] = data
    return data


@app.get("/posts/{post_id}")
async def webhook_get(post_id: str):
    post = _posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404)
    return {"status": "live", "live_url": post.get("live_url")}


@app.delete("/posts/{post_id}")
async def webhook_delete(post_id: str):
    _posts.pop(post_id, None)
    return {"deleted": True}


@app.post("/api/v3/post")
async def lemmy_create(request: Request):
    body = await request.json()
    key = body.get("custom_id")
    if key and key in _idempotency:
        return _idempotency[key]
    post_id = str(len(_posts) + 200)
    data = {
        "post_view": {
            "post": {"id": int(post_id), "ap_id": f"http://mock-lemmy/post/{post_id}"},
        }
    }
    _posts[post_id] = data
    if key:
        _idempotency[key] = data
    return data


@app.get("/api/v3/post")
async def lemmy_get(id: int):
    post_id = str(id)
    if post_id not in _posts:
        raise HTTPException(status_code=404)
    return _posts[post_id]


@app.delete("/api/v3/post")
async def lemmy_delete(request: Request):
    await request.json()
    return {"success": True}


@app.post("/ghost/api/admin/posts/")
async def ghost_create(request: Request):
    body = await request.json()
    posts = body.get("posts", [])
    post_id = str(len(_posts) + 300)
    slug = f"cert-{post_id}"
    data = {
        "posts": [
            {
                "id": post_id,
                "slug": slug,
                "url": f"http://mock-ghost/{slug}",
                "status": "published",
            }
        ]
    }
    _posts[post_id] = data["posts"][0]
    return data


@app.get("/ghost/api/admin/posts/{post_id}/")
async def ghost_get(post_id: str):
    post = _posts.get(post_id)
    if not post:
        raise HTTPException(status_code=404)
    return {"posts": [post]}


@app.delete("/ghost/api/admin/posts/{post_id}/")
async def ghost_delete(post_id: str):
    _posts.pop(post_id, None)
    return {"deleted": True}


@app.get("/rules/community-guidelines.txt")
async def community_rules():
    return (
        "Community guidelines\n"
        "No self-promotion is allowed in top-level posts.\n"
        "Limit: 2 posts per week.\n"
        "AI-generated content must include clear disclosure in the post body.\n"
        "Links are allowed in comments only.\n"
    )


@app.get("/posts/{post_id}/metrics.json")
async def discourse_metrics(post_id: str):
    return {
        "views": 120,
        "likes": 8,
        "comments": 3,
        "shares": 1,
        "saves": 2,
        "watch_time_s": 0,
        "clicks": 5,
    }


@app.get("/api/articles/{post_id}/metrics")
async def devto_metrics(post_id: str):
    return {
        "page_views_count": 340,
        "public_reactions_count": 22,
        "comments_count": 6,
        "views": 340,
        "likes": 22,
        "comments": 6,
        "shares": 4,
        "clicks": 11,
    }


@app.get("/ghost/api/admin/posts/{post_id}/metrics/")
async def ghost_metrics(post_id: str):
    return {
        "metrics": {
            "views": 90,
            "likes": 4,
            "comments": 1,
            "shares": 0,
            "clicks": 2,
        },
        "views": 90,
        "likes": 4,
        "comments": 1,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
