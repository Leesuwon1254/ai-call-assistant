import os
import json
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
UPLOAD_FOLDER = "uploads"
DB_PATH = "calls.db"
ALLOWED_EXTENSIONS = {"mp3", "m4a", "wav", "ogg", "webm"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ── DB 초기화 ─────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            transcript TEXT,
            summary TEXT,
            important_points TEXT,
            appointment TEXT,
            extracted TEXT,
            followups TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── GPT 분석 ─────────────────────────────────────────────
GPT_PROMPT = """다음은 영업 통화 내용입니다. 아래 항목을 분석해서 반드시 JSON 형식으로만 응답하세요.

{
  "summary": "전체 요약 (3~4문장)",
  "important_points": ["핵심내용1", "핵심내용2"],
  "appointment": {
    "title": "일정명",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "location": "장소"
  },
  "extracted": {
    "name": "고객 이름",
    "company": "회사명",
    "phone": "전화번호",
    "amount": "금액",
    "date": "날짜",
    "time": "시간",
    "location": "장소"
  },
  "followups": ["후속조치1", "후속조치2"]
}

항목을 찾을 수 없으면 빈 문자열 또는 빈 배열로 채워줘.

통화 내용:
"""


def analyze_with_gpt(transcript):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 영업 통화 분석 전문가입니다. 반드시 JSON 형식으로만 응답하세요."},
            {"role": "user", "content": GPT_PROMPT + transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    return json.loads(raw)


# ── 홈 화면 ──────────────────────────────────────────────
@app.route("/")
def index():
    # TODO: DB에서 최근 통화 목록 가져오기
    recent_calls = []
    today_schedules = []
    followups = []
    return render_template("index.html",
                           recent_calls=recent_calls,
                           today_schedules=today_schedules,
                           followups=followups)


# ── 업로드 화면 ───────────────────────────────────────────
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            flash("파일을 선택해주세요.", "danger")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("파일을 선택해주세요.", "danger")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("지원하지 않는 파일 형식입니다. (mp3, m4a, wav, ogg, webm)", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # 25MB 초과 체크
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            os.remove(filepath)
            flash("파일 크기가 25MB를 초과합니다. 더 작은 파일을 업로드해주세요.", "danger")
            return redirect(request.url)

        # Whisper STT 호출
        try:
            with open(filepath, "rb") as audio_file:
                transcript_result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                )
            transcript = transcript_result.text
        except Exception as e:
            flash(f"음성 변환 중 오류가 발생했습니다: {str(e)}", "danger")
            return redirect(request.url)

        # GPT 분석 호출
        try:
            analysis = analyze_with_gpt(transcript)
        except json.JSONDecodeError:
            flash("GPT 응답 파싱에 실패했습니다. 다시 시도해주세요.", "danger")
            return redirect(request.url)
        except Exception as e:
            flash(f"GPT 분석 중 오류가 발생했습니다: {str(e)}", "danger")
            return redirect(request.url)

        # DB 저장
        db = get_db()
        cursor = db.execute(
            """INSERT INTO calls (file_name, transcript, summary, important_points, appointment, extracted, followups)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                filename,
                transcript,
                analysis.get("summary", ""),
                json.dumps(analysis.get("important_points", []), ensure_ascii=False),
                json.dumps(analysis.get("appointment", {}), ensure_ascii=False),
                json.dumps(analysis.get("extracted", {}), ensure_ascii=False),
                json.dumps(analysis.get("followups", []), ensure_ascii=False),
            ),
        )
        call_id = cursor.lastrowid
        db.commit()
        db.close()

        flash("분석이 완료되었습니다!", "success")
        return redirect(url_for("result", call_id=call_id))

    return render_template("upload.html")


# ── 분석 결과 화면 ─────────────────────────────────────────
@app.route("/result/<int:call_id>")
def result(call_id):
    db = get_db()
    row = db.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    db.close()

    if row is None:
        flash("분석 결과를 찾을 수 없습니다.", "danger")
        return redirect(url_for("upload"))

    data = {
        "filename": row["file_name"],
        "summary": row["summary"],
        "important_points": json.loads(row["important_points"]),
        "appointment": json.loads(row["appointment"]),
        "extracted": json.loads(row["extracted"]),
        "followups": json.loads(row["followups"]),
    }
    return render_template("result.html", data=data, transcript=row["transcript"])


# ── 고객관리 화면 ─────────────────────────────────────────
@app.route("/customers")
def customers():
    # TODO: DB에서 고객 목록 가져오기
    dummy_customers = [
        {
            "id": 1,
            "name": "김철수",
            "company": "ABC컴퍼니",
            "phone": "010-1234-5678",
            "last_call": "2025-01-21",
            "status": "협의중",
            "next_action": "견적서 발송",
            "call_count": 3,
        },
        {
            "id": 2,
            "name": "이영희",
            "company": "XYZ코리아",
            "phone": "010-9876-5432",
            "last_call": "2025-01-19",
            "status": "계약완료",
            "next_action": "착수금 확인",
            "call_count": 5,
        },
        {
            "id": 3,
            "name": "박민준",
            "company": "테크스타트업",
            "phone": "010-5555-7777",
            "last_call": "2025-01-15",
            "status": "검토중",
            "next_action": "2주 후 재연락",
            "call_count": 1,
        },
    ]
    return render_template("customers.html", customers=dummy_customers)


# ── 고객 상세 화면 ─────────────────────────────────────────
@app.route("/customers/<int:customer_id>")
def customer_detail(customer_id):
    # TODO: DB에서 고객 상세 + 통화 이력 가져오기
    dummy = {
        "id": customer_id,
        "name": "김철수",
        "company": "ABC컴퍼니",
        "phone": "010-1234-5678",
        "status": "협의중",
        "next_action": "견적서 발송",
        "calls": [
            {"date": "2025-01-21", "summary": "프로젝트 예산 및 일정 논의", "amount": "1,500만원"},
            {"date": "2025-01-10", "summary": "초기 요구사항 파악 미팅", "amount": "-"},
            {"date": "2024-12-28", "summary": "신규 프로젝트 문의 접수", "amount": "-"},
        ],
    }
    return render_template("customer_detail.html", customer=dummy)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
