// AI 통화비서 — main.js
// Phase 1: 기본 UI 동작만 포함. STT/GPT 연동은 app.py에서 처리.

document.addEventListener('DOMContentLoaded', () => {
  // Bootstrap 툴팁 초기화
  const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltips.forEach(el => new bootstrap.Tooltip(el));
});
