# AI 통화비서

영업/비즈니스 통화를 자동으로 기록·요약하고, 중요한 약속과 후속 업무를 일정/고객관리 데이터로 바꿔주는 AI 개인비서 앱

## 로컬 실행

```bash
# 1. 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 입력

# 4. 실행
python app.py
```

브라우저에서 http://localhost:5000 접속

## Render 배포

1. GitHub에 push
2. Render → New Web Service → GitHub 레포 연결
3. Environment Variables에 `OPENAI_API_KEY`, `SECRET_KEY` 추가
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`

## 개발 단계

- [x] Phase 1: UI 화면 구성 (홈, 업로드, 결과, 고객관리)
- [ ] Phase 2: Whisper STT + GPT 분석 연동
- [ ] Phase 3: Google Calendar 연동
- [ ] Phase 4: 고객 DB 자동화
- [ ] Phase 5: 모바일 PWA
