# ⚾ KBO 선발 매치업 분석기 — 기획안

## 핵심 포지셔닝

> **"statiz는 확률을 보여주고, 이 도구는 이유를 설명한다"**

statiz.co.kr/prediction 이 이미 승률 % 예측을 제공하고 있음.  
이 도구는 statiz와 경쟁하지 않고, **statiz 데이터 위에 Claude AI 해설 레이어를 얹는 구조**.

---

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | KBO 선발 매치업 분석기 |
| 실행 방법 | `streamlit run app.py` → 브라우저에서 UI 조작 |
| 자동화 | cron 등록 시 매일 오전 10시 자동 실행 (경기 없는 날 자동 스킵) |
| 기술 난이도 | ★★★☆☆ (웹 파싱 + Claude API + Streamlit UI) |
| 예상 소요 | 1~5단계 완성까지 약 2~3주 (주말 기준) |

---

## statiz vs 이 도구 비교

| 비교 항목 | statiz.co.kr/prediction | 이 도구 (Claude 해설) |
|-----------|--------------------------|----------------------|
| 핵심 결과물 | 승률 % 숫자 (예: 64.4% vs 35.6%) | 왜 유리한지 자연어 해설 3줄 |
| 데이터 해석 | 스탯 나열 — 해석은 사용자 몫 | 투수 약점 × 타선 성향 교차 해석 |
| 좌/우 매치업 | 없음 | 투수 좌/우 × 타선 좌/우 상대 OPS 조합 분석 |
| 최근 폼 반영 | 시즌 누적 스탯 위주 | 최근 5경기 ERA·피안타율 별도 가중 반영 |
| 팬 시각 커스터마이징 | 없음 | 사이드바에서 내 팀 선택 → 해당 팀 기준 필터링 |
| 팔로업 질문 | 불가 (정적 페이지) | 채팅 입력창으로 추가 질문 가능 |
| 불확실성 설명 | 없음 | 예측이 틀릴 수 있는 변수 명시 |
| 사용 환경 | 웹 브라우저 | Streamlit 웹 UI (로컬 or 배포 모두 가능) |

---

## 기술 스택 결정

### 왜 Streamlit인가

| | Streamlit | FastAPI + React |
|--|-----------|-----------------|
| 난이도 | ★☆☆☆☆ | ★★★★☆ |
| Python 비중 | 100% | 백엔드 50% |
| 이 프로젝트 적합도 | ★★★★★ | ★★★☆☆ |
| 확장성 | 중간 | 높음 |

- 스크래핑 + AI 분석 결과를 **보여주는** 게 핵심 → Streamlit이 최적
- Python만으로 UI 완성, 별도 프론트 코드 없음
- `streamlit run app.py` 한 줄로 실행
- 나중에 FastAPI + React로 이식할 때도 **비즈니스 로직(스크래핑 + Claude)은 그대로 재사용** 가능

---

## 화면 구성 (Streamlit UI)

```
┌─────────────────────────────────────────────────┐
│  ⚾ KBO 선발 매치업 분석기                         │
│                                                   │
│  [사이드바]          [메인 화면]                   │
│  - 날짜 선택         오늘의 경기 목록 카드          │
│  - 내 팀 선택        ┌──────────┐ ┌──────────┐   │
│  - 분석 실행 버튼    │ 두산 vs  │ │ KIA vs   │   │
│                      │  LG      │ │  삼성    │   │
│                      └──────────┘ └──────────┘   │
│                                                   │
│                      [경기 선택 시]               │
│                      투수 스탯 테이블              │
│                      타선 성향 테이블              │
│                      ─────────────────            │
│                      🤖 Claude 해설               │
│                      "오늘은 LG가 유리합니다.      │
│                       이유는..."                  │
│                                                   │
│                      [추가 질문 입력창]            │
│                      "불펜 포함하면?"  [전송]      │
└─────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
KBOSearch/
│
├── app.py                  # Streamlit 진입점
│
├── crawlers/               # 크롤링 담당 (1~3단계)
│   ├── __init__.py
│   ├── schedule.py         # 오늘 경기 일정 + 선발 투수 (statiz)
│   ├── pitcher.py          # 투수 스탯 수집 (statiz)
│   └── lineup.py           # 팀 타선 성향 수집 (statiz)
│
├── analysis/               # Claude 연동 담당 (4단계)
│   ├── __init__.py
│   ├── prompt.py           # 프롬프트 템플릿 관리
│   └── claude.py           # Claude API 호출
│
├── cache/                  # 로컬 캐시 저장소 (자동 생성)
│   └── .gitkeep
│
├── requirements.txt        # 의존성
└── .env.example            # API 키 예시 (ANTHROPIC_API_KEY)
```

- `crawlers/` — 데이터 수집만 담당, 각 파일이 독립적
- `analysis/` — Claude 호출만 담당, crawlers 결과를 받아서 처리
- `app.py` — 위 두 모듈을 조립해서 Streamlit UI로 보여줌
- `cache/` — statiz 파싱 결과를 JSON으로 저장 (1일 유지)

---

## 단계별 구현 계획

### 1단계 — 데이터 수집 (경기 일정) ★★☆☆☆

**세부 작업**
- KBO 오늘 경기 일정 파싱
- 선발 투수 이름 추출

**구현 방법**
- `statiz.co.kr/prediction` HTML 파싱 (BeautifulSoup)
- 경기 목록 + 선발 투수 한 번에 추출

**결과물** : 오늘 경기 목록 + 선발 투수명 JSON

---

### 2단계 — 투수 스탯 수집 ★★★☆☆

**세부 작업**
- ERA, WHIP, K/9, BB/9, 피안타율, 이닝 소화량
- 최근 5경기 ERA (현재 폼)

**구현 방법**
- `statiz.co.kr` 선수 페이지 HTML 파싱 (BeautifulSoup)
- 로컬 JSON 캐싱 (1일 유지)

**결과물** : 투수별 스탯 JSON

---

### 3단계 — 타선 성향 수집 ★★★☆☆

**세부 작업**
- 팀 타율, OPS, wRC+
- 좌/우 투수 상대 성적 별도 수집
- 최근 10경기 득점력

**구현 방법**
- `statiz.co.kr` 팀 스탯 페이지 파싱
- 좌/우 분리 스탯 별도 수집

**결과물** : 팀별 타선 성향 JSON

---

### 4단계 — Claude API 연동 ★★☆☆☆

**세부 작업**
- 수집 데이터 → 프롬프트 구성
- "오늘 유리한 팀 + 이유" 분석 리포트 생성
- 추가 질문 대화 처리

**구현 방법**
- Anthropic Python SDK (`claude-opus-4-6` 모델)
- 프롬프트 템플릿에 투수 스탯 + 타선 성향 삽입

**프롬프트 예시**
```
다음은 오늘 KBO 경기의 선발 투수와 상대 타선 데이터입니다.

[A팀 선발] 투수명 / ERA: X.XX / WHIP: X.XX / K/9: X.X / 최근5경기 ERA: X.XX
[B팀 타선] 팀 OPS: .XXX / wRC+: XXX / 우투 상대 OPS: .XXX

[B팀 선발] 투수명 / ERA: X.XX / WHIP: X.XX / K/9: X.X / 최근5경기 ERA: X.XX
[A팀 타선] 팀 OPS: .XXX / wRC+: XXX / 좌투 상대 OPS: .XXX

위 데이터를 바탕으로:
1. 오늘 더 유리한 팀과 그 이유를 3줄로 설명해줘
2. 주목할 매치업 포인트 1가지
3. 예상 스코어 범위 (예: 3~5점 경기)
```

**결과물** : 분석 리포트 텍스트

---

### 5단계 — Streamlit UI 구성 ★★☆☆☆

**세부 작업**
- 사이드바: 날짜 선택, 내 팀 선택, 분석 실행 버튼
- 메인: 오늘 경기 카드 목록
- 경기 선택 시 투수/타선 스탯 테이블 출력
- Claude 해설 텍스트 스트리밍 출력
- 추가 질문 입력창 (채팅 형태)

**구현 방법**
```python
import streamlit as st

st.sidebar.selectbox("내 팀", KBO_TEAMS)
if st.sidebar.button("오늘 분석 실행"):
    games = fetch_today_games()
    for game in games:
        with st.expander(f"{game['home']} vs {game['away']}"):
            st.dataframe(get_pitcher_stats(game))
            st.write_stream(claude_analyze(game))  # 스트리밍 출력

# 추가 질문
if question := st.chat_input("추가 질문"):
    st.chat_message("user").write(question)
    st.chat_message("assistant").write_stream(claude_followup(question))
```

**결과물** : 브라우저에서 동작하는 웹 UI

---

### 6단계 — 자동화 (선택) ★☆☆☆☆

**세부 작업**
- 매일 오전 10시 데이터 자동 수집 & 캐싱
- 경기 있는 날만 실행

**구현 방법**
```bash
# crontab -e
0 10 * * * cd ~/claudeCoding && python3 fetch_data.py
```

**결과물** : 앱 실행 시 이미 데이터가 준비된 상태

---

## 향후 확장 아이디어

### 바로 붙일 수 있는 것들

| 아이디어 | 내용 | 난이도 |
|---------|------|--------|
| **분석 캐싱** | `cache/` 폴더 활용, 같은 경기 재분석 시 API 호출 없이 저장 결과 반환 | ★☆☆☆☆ |
| **전체 경기 일괄 분석** | 버튼 하나로 오늘 경기 전부 순서대로 분석 | ★★☆☆☆ |
| **결과 저장/복사** | 분석 결과를 텍스트 파일로 내보내거나 클립보드 복사 | ★☆☆☆☆ |

### 조금 더 손 봐야 하는 것들

| 아이디어 | 내용 | 난이도 |
|---------|------|--------|
| **최근 N경기 흐름 추가** | statiz 게임로그에서 팀 최근 5경기 성적 크롤링 후 프롬프트에 반영 | ★★★☆☆ |
| **불펜 상황 반영** | 선발 외 불펜 피로도/ERA 포함해 더 정밀한 분석 | ★★★☆☆ |
| **경기장 정보 반영** | 홈/원정 구장 (돔/야외) 환경 변수 추가 | ★★☆☆☆ |

### 재밌는 확장

| 아이디어 | 내용 | 난이도 |
|---------|------|--------|
| **예측 적중률 트래킹** | 분석 결과 저장 후 경기 결과와 비교해 AI 적중률 기록 | ★★★★☆ |
| **카카오톡/이메일 알림** | 매일 오전 9시 오늘 경기 분석 자동 발송 (cron 연동) | ★★★☆☆ |

---

## 데이터 소스

| 데이터 종류 | 출처 | 수집 방법 | 업데이트 주기 |
|-------------|------|-----------|--------------|
| 오늘 경기 일정 & 선발 투수 | statiz.co.kr/prediction | BeautifulSoup HTML 파싱 | 당일 실시간 |
| 투수 스탯 (ERA·WHIP 등) | statiz.co.kr | BeautifulSoup 파싱, 로컬 캐싱 | 매일 갱신 |
| 팀 타선 성향 (OPS·wRC+) | statiz.co.kr 팀 스탯 | 동일 파싱, 좌/우 구분 | 매일 갱신 |
| 최근 폼 (최근 N경기) | statiz.co.kr 게임로그 | 게임로그 페이지 파싱 | 당일 기준 |
| 분석 리포트 생성 | Claude API (Anthropic) | Anthropic Python SDK | 실시간 호출 |

---

## 기술 스택

| 라이브러리 | 용도 | 설치 |
|-----------|------|------|
| `requests` | HTTP 요청, JSON/HTML 수집 | `pip install requests` |
| `beautifulsoup4` | HTML 파싱 (statiz 스탯 추출) | `pip install beautifulsoup4` |
| `anthropic` | Claude API 호출 | `pip install anthropic` |
| `streamlit` | 웹 UI 전체 구성 | `pip install streamlit` |
| cron | 데이터 자동 수집 스케줄링 | OS 내장 |
