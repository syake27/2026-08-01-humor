(() => {
  const screen = document.querySelector(".rank-match-screen");
  if (!screen) return;

  const countElement = screen.querySelector(".matching-count-current");
  const titleElement = screen.querySelector(".matching-title");
  const messageElement = screen.querySelector(".matching-message");
  const countdownPanel = screen.querySelector(".rank-countdown");
  const countdownElement = screen.querySelector(".rank-countdown-number");
  const slots = [...screen.querySelectorAll(".player-slot")];
  let redirected = false;

  const updateSlots = (count) => {
    const safeCount = Math.max(0, Math.min(4, Number(count) || 0));
    countElement.textContent = String(safeCount);
    slots.forEach((slot, index) => slot.classList.toggle("is-filled", index < safeCount));
  };

  const showMatched = (countdown) => {
    screen.classList.add("is-matched");
    titleElement.textContent = "対戦相手が見つかりました！";
    messageElement.textContent = "まもなくゲームを開始します";
    countdownPanel.classList.remove("is-hidden");
    countdownElement.textContent = countdown > 0 ? String(countdown) : "GO";
  };

  const poll = async () => {
    try {
      const response = await fetch(screen.dataset.statusUrl, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        cache: "no-store",
      });
      if (!response.ok) return;
      const state = await response.json();
      updateSlots(state.waiting_count);

      if (state.matched) showMatched(state.countdown);
      if (state.is_started && state.game_url && !redirected) {
        redirected = true;
        countdownElement.textContent = "GO";
        window.setTimeout(() => window.location.assign(state.game_url), 250);
      }
    } catch (_error) {
      // 一時的な通信失敗では待機画面を維持し、次のポーリングで再試行する。
    }
  };

  updateSlots(screen.dataset.initialCount);
  if (screen.classList.contains("is-matched")) {
    showMatched(Number(screen.dataset.initialCountdown));
  }
  window.setInterval(poll, 500);
  poll();
})();
