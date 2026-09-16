# Asset Management Dashboard Publisher

## Purpose

사용자가 자산운용 Dashboard 관련 HTML을 업로드하고 `대시보드 발행해줘`, `현재화해서 GitHub에 올려줘`, `이 HTML 최신화해줘` 등으로 요청하면 아래 절차를 일관되게 수행한다.

대상 저장소: `iambaesm/hw`

이 스킬은 **업로드된 HTML을 원본 기준으로 유지하면서 공개적으로 검증 가능한 시장 데이터만 현재화하고, 암호화·검증 후 GitHub Pages용 파일로 발행**한다.

## Supported dashboards

| kind | 판별 키워드 예시 | 기본 GitHub 파일 |
|---|---|---|
| corporate | 기업금융 투자현황, 기업금융 | `pepdpc.html` / 필요 시 `pepd.html` |
| pevc | 한화 PE/VC 현황, PE/VC | `pevc.html` |
| infra | 한화 부동산/인프라 현황, 부동산/인프라 | `infra.html` |
| fxrisk | 환리스크 관리, 환헤지, FX | `fxrisk.html` |
| listed | 재간접 상장주식 익스포져, 상장주식 익스포져 | `listed.html` |
| quarterly | 분기심사 대상 실적 현황, 분기심사 | `quarterly.html` |

파일명보다 **HTML 내부 제목·헤더를 우선**하여 판별한다.

## Core rule: preserve internal data

업로드된 HTML은 사용자가 제공한 내부자료의 기준본이다. 다음 값은 웹 검색 결과로 임의 수정하지 않는다.

- 장부가, 투자금액, Exposure
- IRR, TVPI, DPI, MOIC
- 내부등급, 심사의견, 회수예상액
- 펀드 약정액/납입액
- 내부 분류 및 판단
- 사용자가 작성한 비공개 설명

공개 시장 데이터와 내부 원자료를 명확하게 구분한다. 내부 숫자를 변경해야 한다면 사용자가 새 HTML에서 직접 변경한 값만 반영한다.

## Fresh public data rules

### 1. 상장주식 익스포져 (`listed`)
- 현재가 또는 가장 최근 종가
- 가격 기준시각
- 거래소/통화
- 시세 출처
- 거래정지·저유동성 종목은 마지막 체결가임을 표시
- 조회 실패 시 업로드 HTML의 기존 값을 유지하고 `기존값` 또는 `조회 실패` 표시
- 보유 종목 목록을 공개 저장소의 평문 설정파일에 새로 노출하지 않는다.

### 2. 환리스크 (`fxrisk`)
HTML에 존재하는 대상 통화·헤지 관련 항목만 현재화한다. 주요 환율, 관련 국채/스왑/금리 지표, 조회시각, 출처를 반영할 수 있다. 내부 헤지비율, 계약환율, 내부 Exposure는 변경하지 않는다.

### 3. 분기심사 (`quarterly`)
각 자산별 최근 45일을 기본 검색구간으로 하고 자산/차주/GP/프로젝트의 직접 이벤트, 매각·리파이낸싱·구조조정·회생·디폴트, 신용등급/대주단/CMBS/대출, 임대율·운영실적·통행량 등 직접 관련 이벤트를 우선한다. 자산당 최대 3건, 기사 제목·출처·날짜·2~3문장 요약을 넣는다. 관련성이 약한 기사는 억지로 채우지 않는다.

### 4. PE/VC (`pevc`)
GP/운용사 주요 기사, 펀드 결성/회수/세컨더리/IPO/M&A, 주요 포트폴리오 이벤트, 규제/법적 이벤트를 현재화 후보로 본다. 내부 펀드 성과수치는 변경하지 않는다.

### 5. 부동산/인프라 (`infra`)
자산 매각, 리파이낸싱, 임대/공실, 신용 이벤트, 구조조정, 프로젝트 운영실적, 규제/인허가/요금 등 자산가치에 직접 영향 있는 이벤트를 현재화 후보로 본다.

### 6. 기업금융 (`corporate`)
차주 실적/신용등급, 회사채/대출 리파이낸싱, M&A/지배구조, 유동성·재무구조 관련 공시, 디폴트/워크아웃/회생 등 신용 이벤트를 현재화 후보로 본다.

## Web research standard
- 최신 정보가 필요한 경우 반드시 웹 검색으로 검증한다.
- 기사/시장정보는 기준일과 출처를 표시한다.
- 같은 사실은 가능하면 1차 출처 또는 신뢰도 높은 출처를 우선한다.
- 검색결과만 보고 사실을 단정하지 말고 본문을 확인한다.
- 유료기사로 본문 확인이 불가능하면 확인 가능한 범위까지만 작성한다.
- 검색에서 찾지 못한 내용을 추정해 채우지 않는다.
- 현재가/종가는 통화와 기준시각을 반드시 함께 다룬다.

## HTML rewriting rules
1. 원본 레이아웃을 최대한 유지한다.
2. 기존 CSS 클래스와 JS를 불필요하게 재작성하지 않는다.
3. 현재화 데이터는 원래 표/카드의 의미를 훼손하지 않는 범위에서 삽입한다.
4. 동적 데이터에는 가능하면 `기준시각`, `출처`를 포함한다.
5. 모바일/PC 분기 로직이 있으면 유지한다.
6. 외부 스크립트 의존성을 새로 만들지 않는 것을 기본으로 한다.
7. 내부 데이터가 평문으로 별도 JSON에 노출되지 않도록 한다.

## Encryption
개별 대시보드 완성본은 `publisher.py`로 암호화한다.
- AES-256-GCM
- PBKDF2-SHA256 250,000 iterations
- random 16-byte salt, 12-byte IV
- 브라우저 Web Crypto 복호화
- 입력 비밀번호 앞뒤 공백 제거 + NFKC normalize
- 암호화 직후 Python에서 다시 복호화하여 바이트 단위 검증

비밀번호는 저장소에 커밋하지 않는다. 실행 환경의 `DASHBOARD_PASSWORD` 또는 현재 대화에서 사용자가 지정한 비밀번호를 일회성으로 사용한다. **SKILL.md, config, 소스코드, 로그, commit message에 비밀번호를 기록하지 않는다.**

## Publishing
GitHub 대상: `iambaesm/hw`

1. 현재 대상 파일의 GitHub blob SHA 확인
2. 새 HTML 암호화 및 로컬 복호화 검증
3. 대상 파일 1개씩 순차 업데이트
4. `index.html`은 사용자가 명시적으로 메뉴 변경을 요청하지 않는 한 절대 수정하지 않음
5. GitHub Pages deployment `success` 확인
6. 필요하면 캐시 우회 URL `?v=<commit short sha>` 제공
7. 실패 시 이전 blob/commit으로 복구 가능하도록 commit SHA 기록

### Critical safety
- `index.html`은 개별 대시보드 발행 시 건드리지 않는다.
- GitHub Secret 값을 읽거나 출력하려고 하지 않는다.
- 원본 평문 HTML을 공개 저장소에 별도 백업파일로 올리지 않는다.
- 비공개 키 파일을 저장소에 올리지 않는다.
- 여러 파일을 동시에 같은 경로에 쓰지 않는다.
- 새 자동화가 기존 `update-news.yml`, `update-prices.yml`을 덮어쓰지 않도록 한다.

## Existing runtime automation
현재 저장소의 `update_news.py`/`news.enc.json`, `update_prices.py`/`prices.enc.json`, `.github/workflows/update-news.yml`, `.github/workflows/update-prices.yml`을 가능한 한 유지한다. 보유종목이나 분기심사 대상 자산이 바뀌면 HTML의 데이터 키와 자동화 설정이 맞는지 확인하고, 내부 목록을 평문으로 공개하지 않는다.

## Invocation behavior
사용자가 HTML을 올리고 `대시보드 발행해줘`, `현재화해서 올려줘`, `GitHub에 반영해줘`, `이 HTML 최신 기사와 종가 반영해서 다시 발행해줘`라고 하면 이 스킬을 적용한다. 여러 파일이면 각 파일을 개별 판별 후 순차 처리한다.

완료 보고에는 판별된 페이지 종류, 최신화한 공개 데이터 항목, 유지한 내부자료 범위, GitHub 대상 파일, 암호화 검증 결과, Pages 배포 결과, 조회 실패/fallback 항목만 간결하게 포함한다.
