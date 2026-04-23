# blog-write 사용 가이드

Velog에 블로그 글을 자동으로 포스팅하는 스크립트.

---

## 사전 준비

### 1. 의존성 설치

```bash
pip install requests playwright
playwright install chromium
```

### 2. .env 설정

`blog-write/` 폴더의 **한 단계 위 폴더**에 `.env` 파일 추가:

```
프로젝트폴더/
├── .env              ← 여기
├── blog-write/
│   └── velog.py
└── venv/
```

```
VELOG_REFRESH_TOKEN=브라우저에서_복사한_값
VELOG_USERNAME=벨로그아이디  # @ 없이, 예: skyla00
```

**VELOG_REFRESH_TOKEN 복사 방법:**
1. https://velog.io 에서 로그인
2. F12 → Application → Cookies → `https://velog.io`
3. `refresh_token` 값 복사

> refresh_token은 **30일** 유효. 만료되면 동일한 방법으로 재발급.

---

## 사용법

### 기본 포스팅

```bash
cd 프로젝트폴더
source venv/bin/activate
python3 blog-write/velog.py --title "제목" --content "내용"
```

### 파일로 포스팅 (권장)

```bash
python3 blog-write/velog.py --title "제목" --file blog-write/drafts/2026-04-21.md --tags "개발,Python"
```

### 비공개로 올리기

```bash
python3 blog-write/velog.py --title "제목" --file blog-write/drafts/날짜.md --private
```

### 옵션 정리

| 옵션 | 설명 | 필수 |
|------|------|------|
| `--title` | 글 제목 | ✅ |
| `--content` | 글 내용 직접 입력 | content 또는 file 중 하나 |
| `--file` | 내용 파일 경로 (.md) | content 또는 file 중 하나 |
| `--tags` | 태그 (쉼표 구분) | ❌ |
| `--private` | 비공개 발행 | ❌ |

---

## /blog 자동화 워크플로우 (Claude Code 사용 시)

Claude Code에서 `/blog` 커맨드를 사용하면 초안 작성부터 포스팅까지 자동화된다.

### /blog 커맨드 만들기

`~/.claude/commands/blog.md` 파일 생성:

```bash
mkdir -p ~/.claude/commands
```

아래 내용을 `~/.claude/commands/blog.md`에 저장:

```markdown
# /blog — Velog 블로그 포스팅 자동화

오늘 작업을 마무리할 때 블로그 초안을 파일로 작성하고 Velog에 포스팅한다.

## 순서

1. **초안 파일 작성**
   - 오늘 대화 내용을 바탕으로 아래 구조로 초안 작성
   - 파일 경로: `blog-write/drafts/YYYY-MM-DD.md` (오늘 날짜)
   - `blog-write/template.md` 참고해서 동일한 구조와 말투로 작성
   - 작성 완료 후: "파일 확인해줘. 수정 후 '확정'이라고 하면 Velog에 올릴게."

2. **사용자 확정**
   - 파일을 열어서 직접 수정
   - "확정" 메시지 받으면 다음 단계 진행

3. **Velog 포스팅**
   - 파일에서 제목(첫 번째 # 헤더) 추출
   - velog.py로 자동 포스팅
   - 완료 후 URL 전달

## 주의사항
- 초안은 반드시 사용자 확인을 받은 후 포스팅한다
- 코드 스니펫은 마크다운 코드블록으로 포함
```

### /blog 사용 흐름

```
Claude Code 터미널에서 /blog 입력
  → drafts/YYYY-MM-DD.md 자동 생성
  → 파일 열어서 수정
  → "확정" 입력
  → Velog 자동 포스팅 + URL 반환
```

> drafts/ 폴더는 .gitignore에 등록되어 있어 git에 올라가지 않음.

---

## 파일 구조

```
blog-write/
├── velog.py        # 포스팅 메인 스크립트
├── template.md     # 블로그 초안 템플릿
├── guide.md        # 이 파일
└── drafts/         # 초안 저장 폴더 (gitignore)
    └── YYYY-MM-DD.md
```

---

## 트러블슈팅

**`access_token 발급 실패` 에러**
→ refresh_token 만료. 브라우저에서 새 refresh_token 복사 후 `.env` 업데이트.

**`writePost null` 에러**
→ refresh_token이 잘못됐거나 만료됨. 위와 동일하게 처리.
