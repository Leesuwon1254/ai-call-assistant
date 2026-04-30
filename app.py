import os
import json
import sqlite3
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "calls.db")
ALLOWED_EXTENSIONS = {"mp3", "m4a", "wav", "ogg", "webm"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError as e:
    print(f"[WARNING] uploads 폴더 생성 실패: {e}")


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
    db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            company TEXT,
            phone TEXT,
            status TEXT DEFAULT '신규',
            next_action TEXT,
            last_call_date TEXT,
            call_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


try:
    init_db()
except Exception as e:
    print(f"[ERROR] DB 초기화 실패: {e}")


# ── Google Calendar ────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")


def _google_client_config():
    return {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ.get("GOOGLE_REDIRECT_URI", "")],
        }
    }


def get_google_credentials():
    if not os.path.exists(TOKEN_PATH):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception:
            return None
    return creds if creds and creds.valid else None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upsert_customer(name, company, phone, next_action, call_date):
    if not name:
        return
    db = get_db()
    existing = db.execute(
        "SELECT id, call_count FROM customers WHERE name = ? AND company = ?",
        (name, company or ""),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE customers SET last_call_date = ?, call_count = ?, phone = ?, next_action = ? WHERE id = ?",
            (call_date, existing["call_count"] + 1, phone, next_action, existing["id"]),
        )
    else:
        db.execute(
            """INSERT INTO customers (name, company, phone, next_action, last_call_date, call_count)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (name, company or "", phone or "", next_action or "", call_date),
        )
    db.commit()
    db.close()


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


def transcribe_audio(filepath):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    with open(filepath, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ko",
        )
    return result.text


def analyze_with_gpt(transcript):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
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
    today = datetime.date.today().isoformat()
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    db = get_db()

    # 최근 통화 5건
    raw_calls = db.execute(
        "SELECT id, file_name, summary, extracted, created_at FROM calls ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    recent_calls = []
    for row in raw_calls:
        ext = json.loads(row["extracted"])
        recent_calls.append({
            "id": row["id"],
            "customer_name": ext.get("name") or row["file_name"],
            "summary": row["summary"],
            "created_at": row["created_at"][:10],
        })

    # 오늘 약속
    raw_today = db.execute(
        "SELECT appointment FROM calls WHERE json_extract(appointment, '$.date') = ?", (today,)
    ).fetchall()
    today_schedules = []
    for row in raw_today:
        appt = json.loads(row["appointment"])
        if appt.get("title"):
            today_schedules.append(appt)

    # 후속 연락 필요 (next_action 있는 고객)
    raw_followups = db.execute(
        "SELECT name, next_action FROM customers WHERE next_action != '' AND next_action IS NOT NULL ORDER BY last_call_date DESC LIMIT 5"
    ).fetchall()
    followups = [{"name": r["name"], "action": r["next_action"]} for r in raw_followups]

    # 통계
    total_customers = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    week_calls = db.execute(
        "SELECT COUNT(*) FROM calls WHERE created_at >= ?", (week_ago,)
    ).fetchone()[0]

    db.close()
    return render_template("index.html",
                           recent_calls=recent_calls,
                           today_schedules=today_schedules,
                           followups=followups,
                           total_customers=total_customers,
                           week_calls=week_calls)


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
            transcript = transcribe_audio(filepath)
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

        # 고객 자동 upsert
        ext = analysis.get("extracted", {})
        followups_list = analysis.get("followups", [])
        upsert_customer(
            name=ext.get("name", ""),
            company=ext.get("company", ""),
            phone=ext.get("phone", ""),
            next_action=followups_list[0] if followups_list else "",
            call_date=ext.get("date", "") or datetime.date.today().isoformat(),
        )

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
    db = get_db()
    rows = db.execute(
        "SELECT *, last_call_date AS last_call FROM customers ORDER BY last_call_date DESC"
    ).fetchall()
    db.close()
    return render_template("customers.html", customers=rows)


# ── 고객 상세 화면 ─────────────────────────────────────────
@app.route("/customers/<int:customer_id>")
def customer_detail(customer_id):
    db = get_db()
    row = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        flash("고객을 찾을 수 없습니다.", "danger")
        return redirect(url_for("customers"))

    # 해당 고객의 통화 이력 (extracted JSON name+company 일치)
    call_rows = db.execute(
        """SELECT id, summary, extracted, created_at FROM calls
           WHERE json_extract(extracted, '$.name') = ?
             AND json_extract(extracted, '$.company') = ?
           ORDER BY created_at DESC""",
        (row["name"], row["company"]),
    ).fetchall()
    db.close()

    calls = []
    for c in call_rows:
        ext = json.loads(c["extracted"])
        calls.append({
            "id": c["id"],
            "date": c["created_at"][:10],
            "summary": c["summary"],
            "amount": ext.get("amount") or "-",
        })

    customer = dict(row)
    customer["calls"] = calls
    return render_template("customer_detail.html", customer=customer)


# ── 자동 업로드 안내 ──────────────────────────────────────
@app.route("/auto-upload")
def auto_upload():
    return render_template("auto_upload.html")


# ── Google Calendar 라우트 ────────────────────────────────
@app.route("/calendar/auth")
def calendar_auth():
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "")
    if not redirect_uri:
        flash("GOOGLE_REDIRECT_URI 환경변수가 설정되지 않았습니다.", "danger")
        return redirect(url_for("index"))
    flow = Flow.from_client_config(
        _google_client_config(), scopes=SCOPES, redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/calendar/callback")
def calendar_callback():
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "")
    flow = Flow.from_client_config(
        _google_client_config(),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=session.get("oauth_state"),
    )
    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        flash("Google Calendar 연동이 완료되었습니다!", "success")
    except Exception as e:
        flash(f"Google 인증 실패: {str(e)}", "danger")
    return redirect(url_for("index"))


@app.route("/calendar/add", methods=["POST"])
def calendar_add():
    creds = get_google_credentials()
    if not creds:
        return jsonify({"ok": False, "auth_url": url_for("calendar_auth")})

    title = request.form.get("title", "일정")
    date = request.form.get("date", "")
    time_val = request.form.get("time", "")
    location = request.form.get("location", "")

    if not date:
        return jsonify({"ok": False, "error": "날짜 정보가 없습니다."})

    try:
        service = build("calendar", "v3", credentials=creds)
        if time_val:
            start_dt = datetime.datetime.fromisoformat(f"{date}T{time_val}:00")
            end_dt = start_dt + datetime.timedelta(hours=1)
            start = {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Seoul"}
            end = {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Seoul"}
        else:
            start = {"date": date}
            end = {"date": date}

        event = {"summary": title, "location": location, "start": start, "end": end}
        result = service.events().insert(calendarId="primary", body=event).execute()
        return jsonify({"ok": True, "event_id": result.get("id")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
