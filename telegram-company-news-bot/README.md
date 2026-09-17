# Telegram 기업 뉴스 데일리 봇

여러 기업의 최근 뉴스를 네이버 뉴스 검색 API로 모아 중복을 제거하고, 중요 키워드 순으로 정리해 매일 Telegram으로 보내는 봇입니다.

- 초기 등록기업: 메디트, 오스템임플란트, SLL중앙, 딜라이브, 야놀자,
  강남언니(힐링페이퍼), 셀렌진, 럭스로보, 룩시드랩스, Securitize,
  Oura Health, 에이스테크, 셀비온
- 발송시각: 매일 한국시간 오전 7시 30분
- 비용: OpenAI API 불필요. GitHub Actions 무료 사용량 범위에서는 별도 서버비 없음
- 보안: 인증키는 코드가 아니라 GitHub Actions Secrets에 저장

## 1. 준비할 네 가지 값

### Telegram Bot Token

1. Telegram에서 `@BotFather`를 검색합니다.
2. `/newbot`을 보내고 안내에 따라 봇을 만듭니다.
3. 발급된 Token을 보관합니다. 이것이 `TELEGRAM_TOKEN`입니다.

### Telegram Chat ID

1. 방금 만든 봇과의 채팅창을 열고 아무 메시지나 보냅니다.
2. 브라우저에서 아래 주소를 열되 `<TOKEN>`을 실제 토큰으로 바꿉니다.

   `https://api.telegram.org/bot<TOKEN>/getUpdates`

3. 결과에서 `"chat":{"id":숫자}`의 숫자를 보관합니다. 이것이 `TELEGRAM_CHAT_ID`입니다.

그룹으로 받고 싶다면 봇을 그룹에 추가하고 그룹에서 메시지를 보낸 뒤 같은 방법으로 확인합니다. 그룹 Chat ID는 음수일 수 있습니다.

### Naver Client ID / Secret

1. [네이버 개발자센터](https://developers.naver.com/apps/#/register)에서 애플리케이션을 등록합니다.
2. 사용 API에서 `검색`을 선택합니다.
3. 발급된 `Client ID`와 `Client Secret`을 보관합니다.

## 2. GitHub에 올리기

1. GitHub에서 새 Private repository를 만듭니다.
2. 이 폴더의 파일과 폴더를 전부 repository 최상위에 올립니다.
3. GitHub repository에서 `Settings → Secrets and variables → Actions`로 이동합니다.
4. `New repository secret`을 눌러 아래 4개를 각각 등록합니다.

| Secret 이름 | 넣을 값 |
|---|---|
| `NAVER_CLIENT_ID` | 네이버 Client ID |
| `NAVER_CLIENT_SECRET` | 네이버 Client Secret |
| `TELEGRAM_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |

인증키는 `companies.json`, 소스코드, GitHub 커밋에 직접 적지 마십시오.

## 3. 첫 시험 발송

1. GitHub repository의 `Actions` 탭으로 이동합니다.
2. 왼쪽에서 `Daily Company News`를 선택합니다.
3. `Run workflow`를 눌러 실행합니다.
4. Telegram에 메시지가 도착하는지 확인합니다.

이후에는 매일 오전 7시 30분(KST)에 자동 실행됩니다. GitHub 사정에 따라 실제 발송이 수분 정도 늦어질 수 있습니다.

## 4. 기업 추가하기

`config/companies.json`의 `companies` 배열에 아래 형식으로 항목을 추가합니다.

```json
{
  "name": "메디트",
  "queries": [
    "메디트 치과",
    "Medit 치과"
  ],
  "include_any": [
    "메디트",
    "Medit"
  ],
  "exclude_any": [],
  "priority_keywords": [
    "실적",
    "매출",
    "EBITDA",
    "인수금융",
    "재무약정",
    "i900"
  ]
}
```

- `queries`: 네이버 뉴스에 실제로 검색할 문구입니다. 너무 짧은 영문 약어만 넣으면 무관한 기사가 늘어납니다.
- `include_any`: 제목 또는 네이버 요약문에 이 중 하나가 있어야 포함됩니다.
- `exclude_any`: 이 중 하나가 있으면 제외됩니다.
- `priority_keywords`: 포함된 기사를 위쪽에 배치합니다.

JSON에서는 마지막 항목 뒤에 쉼표를 붙이지 않도록 주의하십시오.

## 5. 설정 변경

`config/companies.json` 상단에서 변경합니다.

| 항목 | 의미 |
|---|---|
| `lookback_hours` | 몇 시간 전까지 조회할지 지정. 기본 26시간 |
| `max_articles_per_company` | 기업별 최대 발송 기사 수. 기본 5건 |
| `digest_title` | Telegram 메시지 제목 |

발송시각을 바꾸려면 `.github/workflows/daily-news.yml`의 cron을 수정합니다. GitHub cron은 UTC 기준이며 한국시간은 UTC보다 9시간 빠릅니다.

예: 오전 8시 KST는 전날 23시 UTC이므로 `0 23 * * *`입니다.

## 6. 로컬 시험 실행(선택)

Python 3.12 환경에서 다음을 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export NAVER_CLIENT_ID="..."
export NAVER_CLIENT_SECRET="..."
python newsbot.py --dry-run
```

실제 Telegram 발송까지 시험하려면 `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`도 환경변수로 등록한 뒤 `--dry-run` 없이 실행합니다.

## 7. 아이콘 의미

- 🔴: 기업명과 중요 키워드가 강하게 포착된 기사
- 🟠: 기업 관련성이 높거나 중요 키워드가 포함된 기사
- ⚪: 일반 관련 기사

이는 규칙 기반 우선순위이며 투자판단이나 AI 신용평가 결과가 아닙니다.

## 문제 해결

- `401/403`: 네이버 Client ID 또는 Secret, 검색 API 선택 여부를 확인합니다.
- Telegram `chat not found`: 먼저 봇에게 메시지를 보냈는지, Chat ID가 정확한지 확인합니다.
- Telegram `Unauthorized`: Bot Token을 다시 확인합니다.
- 무관한 기사가 많음: `queries`를 더 구체적으로 하고 `exclude_any`에 제외어를 추가합니다.
- 기사가 누락됨: `include_any`에 회사의 다른 표기나 자회사명을 추가합니다.
