"""
Velog 자동 포스팅 (refresh_token으로 자동 인증)

사용법:
    python3 velog.py --title "제목" --file post.md
    python3 velog.py --title "제목" --content "내용" --tags "KBO,야구,개발"

.env 필요 항목:
    VELOG_REFRESH_TOKEN=...   # 브라우저 쿠키에서 복사 (수명 30일)
    VELOG_USERNAME=...        # @ 없이, 예: skyla_gksmf_00
"""
import os
import re
import argparse
import requests
from pathlib import Path

# .env 로드
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split("#")[0].strip()
        os.environ.setdefault(k.strip(), v)

REFRESH_TOKEN = os.getenv("VELOG_REFRESH_TOKEN")
USERNAME      = os.getenv("VELOG_USERNAME")
API_URL       = "https://v3.velog.io/graphql"


def get_access_token() -> str:
    """refresh_token으로 새 access_token 발급"""
    if not REFRESH_TOKEN:
        raise EnvironmentError(".env에 VELOG_REFRESH_TOKEN이 없습니다.")

    resp = requests.post(
        API_URL,
        json={"query": "{ currentUser { id username } }"},
        headers={
            "Content-Type": "application/json",
            "Cookie": f"refresh_token={REFRESH_TOKEN}",
        },
        timeout=10,
    )
    # Set-Cookie 헤더에서 직접 access_token 추출
    token = None
    for cookie_part in resp.headers.get("set-cookie", "").split(";"):
        cookie_part = cookie_part.strip()
        if cookie_part.startswith("access_token="):
            token = cookie_part.split("=", 1)[1]
            break

    if not token:
        raise Exception("access_token 발급 실패. refresh_token이 만료됐을 수 있습니다.\n브라우저에서 refresh_token을 다시 복사해 .env에 저장하세요.")

    print("  access_token 갱신 성공")
    return token


def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-") or "untitled"


def post(title: str, content: str, tags: list = None, is_private: bool = False) -> str:
    """Velog에 글 포스팅 후 URL 반환"""
    print("  토큰 갱신 중...")
    token = get_access_token()

    mutation = """
    mutation WritePost($input: WritePostInput!) {
        writePost(input: $input) {
            id
            title
            url_slug
            user { username }
        }
    }
    """
    variables = {
        "input": {
            "title": title,
            "body": content,
            "tags": tags or [],
            "is_markdown": True,
            "is_temp": False,
            "is_private": is_private,
            "url_slug": slugify(title),
            "meta": {},
        }
    }

    resp = requests.post(
        API_URL,
        json={"query": mutation, "variables": variables},
        headers={
            "Content-Type": "application/json",
            "Cookie": f"access_token={token}; refresh_token={REFRESH_TOKEN}",
        },
        timeout=15,
    )
    print(f"  응답: {resp.text[:300]}")
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise Exception(f"GraphQL 에러: {data['errors']}")

    result = data["data"]["writePost"]
    if result is None:
        raise Exception("writePost null — 인증 실패. refresh_token을 다시 확인하세요.")

    return f"https://velog.io/@{result['user']['username']}/{result['url_slug']}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Velog 자동 포스팅")
    parser.add_argument("--title",   required=True)
    parser.add_argument("--content", default=None)
    parser.add_argument("--file",    default=None)
    parser.add_argument("--tags",    default="")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()

    content = Path(args.file).read_text(encoding="utf-8") if args.file else args.content
    # 첫 번째 # 제목 줄 제거 (제목은 --title로 별도 전달)
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:]).lstrip("\n")
    if not content:
        print("--content 또는 --file 을 입력하세요.")
        exit(1)

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    print("포스팅 중...")
    url = post(args.title, content, tags, is_private=args.private)
    print(f"\n완료: {url}")
