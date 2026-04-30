const APP_VERSION = "v1.1.0";

const VERSION_HISTORY = [
  {
    version: "v1.1.0",
    date: "2026-04-30",
    changes: [
      "Google 토큰 DB 저장 (재배포 후 재연동 불필요)",
      "통화 분석 완료 시 Google Calendar 자동 등록",
      "약속 정보 없을 시 캘린더 버튼 자동 숨김"
    ]
  },
  {
    version: "v1.0.0",
    date: "2026-04-30",
    changes: [
      "홈 대시보드 (이번 주 통화, 오늘 일정, 후속 연락, 고객 수)",
      "통화 녹음 파일 업로드 (MP3, M4A, WAV 지원)",
      "Whisper STT 음성 → 텍스트 변환",
      "GPT-4o-mini AI 통화 분석 (요약, 핵심내용, 약속, 금액, 이름 추출)",
      "SQLite DB 자동 저장 (통화 이력, 고객 자동 등록)",
      "고객관리 화면 (통화 이력, 진행 상태)",
      "Google Calendar 연동 (OAuth)",
      "Android PWA 자동 업로드",
      "Render 배포 완료"
    ]
  }
];

// 버전 뱃지 + 모달 동적 생성
document.addEventListener("DOMContentLoaded", () => {
  // ── 모달 ──────────────────────────────────────────────
  const modalHtml = `
<div class="modal fade" id="versionModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title fw-bold">
          <i class="bi bi-clock-history me-2 text-primary"></i>버전 히스토리
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        ${VERSION_HISTORY.map(v => `
          <div class="mb-4">
            <div class="d-flex align-items-center mb-2">
              <span class="badge bg-primary me-2 fs-6">${v.version}</span>
              <span class="text-muted small">${v.date}</span>
            </div>
            <ul class="list-unstyled mb-0 ps-1">
              ${v.changes.map(c => `
                <li class="d-flex align-items-start mb-1">
                  <i class="bi bi-check-circle-fill text-success me-2 mt-1 flex-shrink-0" style="font-size:0.75rem"></i>
                  <span class="small">${c}</span>
                </li>
              `).join("")}
            </ul>
          </div>
        `).join('<hr class="my-3">')}
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">닫기</button>
      </div>
    </div>
  </div>
</div>`;

  document.body.insertAdjacentHTML("beforeend", modalHtml);

  // ── 고정 뱃지 ─────────────────────────────────────────
  const badge = document.createElement("button");
  badge.className = "btn btn-primary btn-sm shadow";
  badge.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:1040;font-size:0.75rem;padding:4px 10px;border-radius:20px;opacity:0.85;";
  badge.innerHTML = `<i class="bi bi-tag-fill me-1"></i>${APP_VERSION}`;
  badge.setAttribute("data-bs-toggle", "modal");
  badge.setAttribute("data-bs-target", "#versionModal");
  badge.title = "버전 히스토리 보기";
  document.body.appendChild(badge);
});
