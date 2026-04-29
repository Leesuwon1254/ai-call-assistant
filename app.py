import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp3", "m4a", "wav", "ogg", "webm"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            flash("파일 업로드 완료! 분석을 시작합니다.", "success")
            # TODO: Phase 1 — STT + GPT 분석 호출
            return redirect(url_for("result", filename=filename))
        else:
            flash("지원하지 않는 파일 형식입니다. (mp3, m4a, wav, ogg, webm)", "danger")
    return render_template("upload.html")


# ── 분석 결과 화면 ─────────────────────────────────────────
@app.route("/result/<filename>")
def result(filename):
    # TODO: DB에서 분석 결과 가져오기
    # 지금은 더미 데이터로 UI 확인
    dummy = {
        "filename": filename,
        "summary": "김철수 부장님과 신규 프로젝트 견적 및 미팅 일정을 논의했습니다. 총 예산 1,500만원 규모의 웹 개발 프로젝트이며, 다음 주 화요일 오전 10시에 대면 미팅을 확정했습니다.",
        "important_points": [
            "프로젝트 예산: 1,500만원",
            "납기일: 3개월 (2월 말)",
            "기술 스택: React + Node.js 요청",
            "추가 요구사항: 모바일 앱 연동 가능 여부 확인 필요",
            "결제 조건: 착수금 30%, 중도금 40%, 잔금 30%",
        ],
        "appointment": {
            "title": "ABC컴퍼니 프로젝트 미팅",
            "date": "2025-01-28",
            "time": "10:00",
            "location": "ABC컴퍼니 본사 3층 회의실",
        },
        "extracted": {
            "name": "김철수",
            "company": "ABC컴퍼니",
            "phone": "010-1234-5678",
            "amount": "1,500만원",
            "date": "2025-01-28",
            "time": "오전 10시",
            "location": "ABC컴퍼니 본사 3층 회의실",
        },
        "followups": [
            "모바일 앱 연동 가능 여부 내부 검토 후 회신",
            "React + Node.js 기반 견적서 재작성",
            "계약서 초안 준비",
        ],
    }
    return render_template("result.html", data=dummy)


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
