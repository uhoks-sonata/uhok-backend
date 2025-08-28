// services/homeshopping/static/js/live_player.js

/**
 * """HLS 플레이어 초기화(템플릿용)
 * - window.__LIVE_SRC__로 주입된 m3u8 URL을 받아 Hls.js로 재생
 * - Safari(iOS)는 네이티브 HLS로 처리
 * - 자동재생 실패는 무시하고 사용자 상호작용을 대기
 * """
 */
(async function initLivePlayer() {
    const src = window.__LIVE_SRC__;
    const video = document.getElementById("video");
    if (!src || !video) return;
  
    // 모바일 자동재생 정책 대응
    video.muted = true;
    video.setAttribute("playsinline", "");
  
    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls();
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        const p = video.play();
        if (p && p.catch) p.catch(() => {});
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
      video.addEventListener("loadedmetadata", () => {
        const p = video.play();
        if (p && p.catch) p.catch(() => {});
      });
    } else {
      document.body.insertAdjacentHTML(
        "beforeend",
        '<p style="text-align:center;">이 브라우저는 HLS를 지원하지 않습니다.</p>'
      );
    }
  })();
  