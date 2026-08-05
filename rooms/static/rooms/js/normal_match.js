"use strict";

const roomListScreen = document.querySelector(".room-list-screen");
const POLL_INTERVAL = 1500;

async function updateRoomCounts() {
  if (!roomListScreen || document.hidden) {
    scheduleNextUpdate();
    return;
  }

  try {
    const response = await fetch(roomListScreen.dataset.statusUrl, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store",
    });

    if (response.ok) {
      const data = await response.json();
      const rooms = new Map(data.rooms.map((room) => [room.room_id, room]));

      document.querySelectorAll(".available-room[data-room-id]").forEach((card) => {
        const room = rooms.get(card.dataset.roomId);
        if (!room) return;

        const count = card.querySelector(".live-participant-count");
        if (count) {
          count.textContent = `${room.current_players}/${room.max_players}人`;
        }
      });
    }
  } catch (error) {
    // 一時的に通信できない場合は、現在の表示を保って次回に再試行する。
  }

  scheduleNextUpdate();
}

function scheduleNextUpdate() {
  window.setTimeout(updateRoomCounts, POLL_INTERVAL);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    updateRoomCounts();
  }
});

scheduleNextUpdate();
