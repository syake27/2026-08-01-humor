"use strict";

const waitingScreen = document.querySelector(".waiting-screen");
const currentCount = document.querySelector(".current-player-count");
const maxCount = document.querySelector(".max-player-count");
const playerCount = document.querySelector(".player-count");
const POLL_INTERVAL = 1500;

async function updateParticipantCount() {
  if (!waitingScreen || document.hidden) {
    scheduleNextUpdate();
    return;
  }

  try {
    const response = await fetch(waitingScreen.dataset.roomStatusUrl, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store",
    });

    if (response.ok) {
      const room = await response.json();
      if (room.is_started && room.game_url) {
        window.location.assign(room.game_url);
        return;
      }
      currentCount.textContent = room.current_players;
      maxCount.textContent = room.max_players;
      playerCount.setAttribute(
        "aria-label",
        `現在の参加人数 ${room.current_players}人、定員${room.max_players}人`
      );
    }
  } catch (error) {
    // 一時的に通信できない場合は、現在の表示を保って次回に再試行する。
  }

  scheduleNextUpdate();
}

function scheduleNextUpdate() {
  window.setTimeout(updateParticipantCount, POLL_INTERVAL);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    updateParticipantCount();
  }
});

scheduleNextUpdate();
