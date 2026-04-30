const CACHE_NAME = 'ai-call-assistant-v1';
const STATIC_ASSETS = [
  '/',
  '/upload',
  '/customers',
  '/auto-upload',
  '/static/css/style.css',
  '/static/js/main.js',
];

// 설치: 정적 자산 캐시
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// 활성화: 이전 캐시 정리
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: API/업로드는 네트워크 우선, 나머지는 캐시 우선
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // POST 요청 (업로드, 캘린더) → 항상 네트워크
  if (event.request.method !== 'GET') return;

  // API 경로 → 네트워크 우선
  if (url.pathname.startsWith('/calendar') || url.pathname.startsWith('/result')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  // 정적 자산 → 캐시 우선
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (!response || response.status !== 200) return response;
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
