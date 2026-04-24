# KBOSearch 데이터 수집 성능 분석 및 캐싱 개선

> 기록 일자: 2026-04-24

---

## 1. 현황 파악 — 왜 느렸나?

Streamlit 앱에서 경기 버튼을 누를 때 세 함수가 순차 실행됨:

| 함수 | 동작 | 소요 시간 | 캐시 여부 |
|------|------|-----------|-----------|
| `fetch_pitcher_stats(game_id)` | Playwright 브라우저 기동 → START_PIT 페이지 1개 수집 | **~4.0s** | ❌ 없음 |
| `fetch_lineup(away, home)` | Playwright 브라우저 기동 → 팀 스탯 페이지 4개 순차 수집 | **~9–15s** (첫 호출) | 🔺 lru_cache (두 번째부터 0s) |
| `load_recent_games(team, date)` | Playwright 브라우저 기동 → 월별 일정 페이지 수집 | ~5s (첫 호출) | ✅ st.cache_data |

**경기 선택 시 총 대기 시간 (최초 클릭 기준): 18–24초**

### 핵심 문제

1. **`fetch_pitcher_stats`에 캐시 없음** — 버튼을 누를 때마다 Playwright가 새 브라우저를 기동해 START_PIT 페이지를 재수집. 그런데 `load_games`가 이미 같은 페이지를 수집해 투수 이름만 추출하고 HTML을 버리고 있었음 → 같은 페이지를 두 번 fetch하는 낭비.

2. **`fetch_lineup`은 lru_cache만 있음** — 프로세스 내 첫 호출은 항상 느림. Streamlit이 재실행될 때 lru_cache는 유지되지만, Streamlit 자체 캐시(`@st.cache_data`)가 없어 함수 결과가 Streamlit 레이어에서 공유되지 않음.

---

## 2. 개선 방법

### A. Pitcher stats 사전 캐시 (가장 큰 효과)

`schedule.fetch_game_list()`가 START_PIT HTML을 이미 수집하는 시점에,
`pitcher._cache_stats(game_id, html)`를 호출해 파싱 결과를 모듈 레벨 딕셔너리에 저장.

```
load_games() 실행 중
  └─ fetch_game_list()
       ├─ 경기 일정 페이지 수집
       └─ 5개 START_PIT 페이지 수집
            └─ pitcher._cache_stats(game_id, html)  ← 이 시점에 스탯 파싱 완료
                  ↓
            _stats_cache = {"20260424LGOB0": {...}, ...}

경기 버튼 클릭 시
  └─ fetch_pitcher_stats(game_id)
       └─ _stats_cache에 있으면 즉시 반환 ← Playwright 호출 없음
```

### B. Streamlit 캐시 추가 (`app.py`)

`fetch_pitcher_stats`와 `fetch_lineup`을 `@st.cache_data(ttl=3600)` 래퍼로 감쌈.
동일한 `(game_id)` 또는 `(away, home)` 조합은 Streamlit 세션 내에서 재실행 없이 반환.

---

## 3. 실측 결과

> 환경: MacBook, Playwright Chromium headless, koreabaseball.com

| 시나리오 | 개선 전 | 개선 후 | 단축 |
|---------|--------|--------|------|
| `fetch_pitcher_stats` (경기 선택 시) | **4.00s** | **0.0000s** | 100% ↓ |
| `fetch_lineup` 첫 호출 | 9.68s | 9.68s | 변화 없음 (첫 호출은 동일) |
| `fetch_lineup` 두 번째 이상 | 0.00s (lru_cache) | 0.00s | 동일 |
| 같은 경기 재선택 | 4.0s + lineup | 0.00s (st.cache_data) | 100% ↓ |

### 전체 흐름 시간 비교

| 단계 | 개선 전 | 개선 후 |
|------|--------|--------|
| 앱 초기 로드 (`load_games`) | ~22s | ~22s (동일, 이미 캐시) |
| 첫 경기 선택 (데이터 수집 중) | **18–24s** | **9–10s** (lineup만 대기) |
| 같은 경기 재선택 | **4s** | **< 0.1s** |
| 다른 경기 선택 (lineup 캐시 후) | **4s** | **< 0.1s** |
| Gemini API 분석 | 5–15s | 5–15s (변화 없음) |

---

## 4. 캐시 구조 요약

```
프로세스 메모리 (lru_cache / 모듈 딕셔너리)
  ├─ pitcher._stats_cache      → game_id → 스탯 dict (load_games에서 채워짐)
  ├─ lineup._fetch_all_raw()   → lru_cache, 전체 팀 스탯 (첫 호출 후 고정)
  └─ recent_games._fetch_month_games() → lru_cache, 월별 경기 결과

Streamlit 캐시 (@st.cache_data, 세션 내 공유)
  ├─ load_games(date_str)        ttl=300s
  ├─ load_pitcher_stats(game_id) ttl=3600s
  ├─ load_lineup(away, home)     ttl=3600s
  └─ load_recent_games(team, date) ttl=3600s
```

---

## 5. 남은 병목

- **`fetch_lineup` 첫 호출**: 팀 스탯 4개 페이지를 순차 수집 (~10s). Playwright 멀티탭 병렬 수집으로 2–3배 단축 가능 (현재 미구현).
- **Gemini API**: 5–15s. 스트리밍으로 체감 대기시간은 줄어있으나 모델 응답 속도에 의존.
