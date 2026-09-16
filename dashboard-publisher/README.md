# 자산운용 Dashboard Publisher

업로드 HTML을 현재화한 뒤 암호화·검증·GitHub 발행하는 재사용 패키지입니다.

## 로컬 사용

```bash
pip install -r requirements.txt
export DASHBOARD_PASSWORD='(비밀번호)'
python publisher.py --input enriched.html --kind auto --output output.html
```

## 선택적 GitHub 직접 발행

`GH_TOKEN`에 contents write 권한이 있으면:

```bash
export DASHBOARD_PASSWORD='(비밀번호)'
export GH_TOKEN='(token)'
python publisher.py --input enriched.html --kind listed --publish
```

ChatGPT 프로젝트에서는 GitHub connector를 우선 사용합니다.

중요: 비밀번호/토큰, 원본 평문 HTML, 비공개 키 파일은 공개 저장소에 커밋하지 않습니다. 개별 대시보드 발행 시 `index.html`을 수정하지 않습니다.
