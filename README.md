# 🍱 Lunch Buddy (점심 밥친구)

직장 동료들과 점심 약속 유무를 공유하고, 같이 먹을 사람을 찾는 간단한 대시보드입니다.

## 🚀 설치 및 실행 방법

1. **필요한 라이브러리 설치**
   ```bash
   pip install streamlit requests
   ```

2. **텔레그램 봇 토큰 설정 (필수)**
   - 텔레그램에서 `@BotFather` 검색 -> `/newbot` 입력 -> 봇 이름 설정 -> **Token** 복사.
   - 아래 둘 중 하나로 토큰을 넣어주세요(코드에 하드코딩 금지):
     - (권장) 환경변수: `export TELEGRAM_BOT_TOKEN="<token>"`
     - Streamlit secrets: `.streamlit/secrets.toml`에 `TELEGRAM_BOT_TOKEN = "<token>"`
   - 봇에게 `/start` 메시지를 한 번 보내두세요 (필수).
   - 본인의 Chat ID를 알아내려면 `@userinfobot`에게 아무 메시지나 보내면 알려줍니다.

3. **앱 실행**
   ```bash
   streamlit run app.py
   ```

4. **사용 방법**
   - 웹 브라우저가 열리면 본인의 이름(닉네임)과 Chat ID를 입력하고 **등록** 버튼을 누릅니다.
   - 자신의 상태(🟢 점약 없어요 불러주세요 / 🟠 점약을 잡는 중이에요)를 선택합니다.
   - 동료들의 상태를 확인하고, **🟢 점약 없음**인 동료에게 "밥 먹자고 찌르기!" 버튼을 누릅니다.
   - 상대방에게 텔레그램 알림이 전송됩니다.

## 🛠 구조
- `app.py`: 메인 화면 (Streamlit)
- `db.py`: 데이터베이스 처리 (SQLite)
- `bot.py`: 텔레그램 알림 발송

---
Happy Lunch! 🍚
