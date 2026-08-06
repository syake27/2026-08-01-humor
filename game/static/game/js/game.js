"use strict";

const answerForm = document.querySelector(".answer-form");
const answerInput = document.getElementById("answer-input");
const clearAnswerButton = document.getElementById("clear-answer");
const gameMessage = document.getElementById("game-message");
const gameMenuButton = document.getElementById("game-menu-button");
const gameMenu = document.getElementById("game-menu");
const gameMenuWrap = document.querySelector(".game-menu-wrap");
const playersStrip = document.querySelector(".players-strip");
const aliveCount = document.querySelector(".alive-count");
const turnNumber = document.querySelector(".turn-number");
const turnTime = document.querySelector(".turn-time");
const currentLetterCard = document.querySelector(".current-letter-card");
const currentWord = document.querySelector(".current-word");
const currentLetterPrompt = document.querySelector(".current-letter-prompt");
const wordHistory = document.querySelector(".word-history");
const sendAnswerButton = document.querySelector(".send-answer");
const historyOpenButton = document.getElementById("history-open");
const historyModal = document.getElementById("history-modal");
const historyCloseButton = document.getElementById("history-close");
const modalHistoryList = document.querySelector(".modal-history-list");
const modalCurrentLetter = document.querySelector(".modal-current-letter");
const roomRulesOpenButton = document.getElementById("room-rules-open");
const roomRulesModal = document.getElementById("room-rules-modal");
const roomRulesCloseButton = document.getElementById("room-rules-close");
const babaDebugLetter = document.querySelector(".baba-debug-letter");
const PLAYER_POLL_INTERVAL = 1500;
let focusedPlayerId = null;
let isComposingAnswer = false;
let isMovingToResult = false;
let renderedHistorySignature = JSON.stringify(
  Array.from(modalHistoryList.querySelectorAll("li:not(.history-empty)")).map((row) => ({
    turn_number: row.querySelector("span")?.textContent || "",
    word: row.querySelector("strong")?.textContent || "",
    player_name: row.querySelector("small")?.textContent || "",
  }))
);

function fitCurrentWord() {
  const wordLength = Math.max(Array.from(currentWord.textContent.trim()).length, 1);
  const availableWidth = currentWord.clientWidth;
  if (!availableWidth) return;

  const fittedSize = Math.max(
    10,
    Math.min(64, Math.floor(availableWidth / (wordLength * 1.04)))
  );
  currentWord.style.fontSize = `${fittedSize}px`;
}

function showMessage(title, detail, isSuccess = false) {
  gameMessage.classList.toggle("is-success", isSuccess);
  gameMessage.querySelector(".message-icon").textContent = isSuccess ? "✓" : "!";
  gameMessage.querySelector("strong").textContent = title;
  gameMessage.querySelector("small").textContent = detail;
}

function moveToResult(game) {
  if (!game.is_finished || !game.result_url || isMovingToResult) return false;
  isMovingToResult = true;
  window.location.replace(game.result_url);
  return true;
}

clearAnswerButton.addEventListener("click", () => {
  answerInput.value = "";
  answerInput.focus();
});

function keepHiraganaOnly() {
  const hiraganaOnly = answerInput.value
    .normalize("NFKC")
    .replace(/[^ぁ-ゖー]/g, "");

  if (answerInput.value !== hiraganaOnly) {
    answerInput.value = hiraganaOnly;
    showMessage("ひらがなで入力してください", "カタカナ・漢字・英数字は入力できません");
  }
}

answerInput.addEventListener("compositionstart", () => {
  isComposingAnswer = true;
});

answerInput.addEventListener("compositionend", () => {
  isComposingAnswer = false;
  keepHiraganaOnly();
});

answerInput.addEventListener("input", () => {
  if (!isComposingAnswer) {
    keepHiraganaOnly();
  }
});

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const answer = answerInput.value.trim();

  if (!answer) {
    showMessage("言葉を入力してください", `「${currentLetterCard.dataset.currentLetter}」からはじまる言葉を考えよう`);
    return;
  }

  const couldAnswer = !answerInput.disabled;
  sendAnswerButton.disabled = true;

  try {
    const response = await fetch(answerForm.dataset.answerUrl, {
      method: "POST",
      body: new FormData(answerForm),
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const game = await response.json();

    if (moveToResult(game)) return;

    if (!response.ok) {
      showMessage("送信できませんでした", game.error || "もう一度お試しください");
      return;
    }

    answerInput.value = "";
    applyGameState(game);
    showMessage(
      game.baba_hit ? "ババでした！" : "送信しました！",
      game.message,
      !game.baba_hit
    );
  } catch (error) {
    showMessage("通信できませんでした", "接続を確認してもう一度お試しください");
  } finally {
    if (couldAnswer && !answerInput.disabled) {
      sendAnswerButton.disabled = false;
    }
  }
});

function closeGameMenu() {
  gameMenu.hidden = true;
  gameMenuButton.setAttribute("aria-expanded", "false");
}

historyOpenButton.addEventListener("click", () => {
  historyModal.showModal();
});

historyCloseButton.addEventListener("click", () => {
  historyModal.close();
  historyOpenButton.focus();
});

historyModal.addEventListener("click", (event) => {
  if (event.target === historyModal) {
    historyModal.close();
  }
});

roomRulesOpenButton.addEventListener("click", () => {
  closeGameMenu();
  roomRulesModal.showModal();
});

roomRulesCloseButton.addEventListener("click", () => {
  roomRulesModal.close();
});

roomRulesModal.addEventListener("click", (event) => {
  if (event.target === roomRulesModal) {
    roomRulesModal.close();
  }
});

roomRulesModal.addEventListener("close", () => {
  roomRulesOpenButton.focus();
});

gameMenuButton.addEventListener("click", () => {
  const willOpen = gameMenu.hidden;
  gameMenu.hidden = !willOpen;
  gameMenuButton.setAttribute("aria-expanded", String(willOpen));
});

document.addEventListener("click", (event) => {
  if (!gameMenuWrap.contains(event.target)) {
    closeGameMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeGameMenu();
    if (!historyModal.open && !roomRulesModal.open) {
      gameMenuButton.focus();
    }
  }
});

async function updatePlayers() {
  if (!playersStrip || document.hidden) {
    schedulePlayerUpdate();
    return;
  }

  try {
    const response = await fetch(playersStrip.dataset.statusUrl, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      cache: "no-store",
    });

    if (response.ok) {
      const game = await response.json();
      applyGameState(game);
    }
  } catch (error) {
    // 通信が一時的に切れた場合は表示を保ち、次回の取得で復帰する。
  }

  schedulePlayerUpdate();
}

function applyGameState(game) {
  if (moveToResult(game)) return;

  const playerStates = new Map(
    game.players.map((player) => [String(player.id), player])
  );
  let livingPlayers = 0;
  let currentSeconds = 0;
  let currentPlayerCard = null;

  playersStrip.querySelectorAll(".battle-player").forEach((card) => {
    const player = playerStates.get(card.dataset.playerId);
    if (!player) return;

    card.classList.toggle("is-active", player.is_current);
    card.classList.toggle("is-eliminated", !player.is_alive);
    card.tabIndex = player.is_current ? 0 : -1;
    if (player.is_current) {
      card.setAttribute("aria-current", "true");
      currentPlayerCard = card;
    } else {
      card.removeAttribute("aria-current");
    }
    if (player.is_alive) livingPlayers += 1;
    if (player.is_current) currentSeconds = player.remaining_seconds;

    const name = card.querySelector(".player-display-name");
    const title = card.querySelector(".player-name small");
    const time = card.querySelector(".player-time");
    const placement = card.querySelector(".player-placement");
    if (name) {
      name.textContent = player.is_self ? "あなた" : player.name;
      name.classList.toggle("is-self", player.is_self);
    }
    if (title) title.textContent = player.title;
    if (time) time.textContent = `残り ${player.remaining_seconds}秒`;
    if (placement) {
      placement.hidden = !player.placement;
      placement.textContent = player.placement ? `${player.placement}位` : "";
    }

  });

  if (currentPlayerCard && focusedPlayerId !== currentPlayerCard.dataset.playerId) {
    focusedPlayerId = currentPlayerCard.dataset.playerId;
    const currentIndex = game.players.findIndex((player) => player.is_current);
    const turnOrder = [
      ...game.players.slice(currentIndex),
      ...game.players.slice(0, currentIndex),
    ];

    turnOrder.forEach((player) => {
      const card = playersStrip.querySelector(`[data-player-id="${player.id}"]`);
      if (card) playersStrip.append(card);
    });

    window.requestAnimationFrame(() => {
      playersStrip.scrollTo({
        left: 0,
        behavior: "smooth",
      });
    });
  }

  const me = game.players.find((player) => player.is_self);
  const canAnswer = Boolean(me && me.is_alive && me.is_current);
  const acceptedLetterDisplay = game.accepted_start_letters.join("・");
  answerInput.disabled = !canAnswer;
  sendAnswerButton.disabled = !canAnswer;
  answerInput.placeholder = canAnswer
    ? `「${acceptedLetterDisplay}」から始まる言葉`
    : "あなたの番を待っています";

  aliveCount.textContent = livingPlayers;
  turnNumber.textContent = game.turn_number;
  turnTime.textContent = currentSeconds;
  currentLetterCard.dataset.currentLetter = game.current_letter;
  babaDebugLetter.textContent = game.baba_letter;
  currentWord.textContent = game.current_word;
  fitCurrentWord();
  currentLetterPrompt.textContent = `次は「${acceptedLetterDisplay}」からはじまる言葉を入力！`;
  renderHistory(game.words, game.current_letter);
  renderModalHistory(game.words, game.current_letter);
}

function renderHistory(words, nextLetter) {
  wordHistory.replaceChildren();

  const start = document.createElement("span");
  start.className = "history-start";
  start.textContent = "スタート";
  wordHistory.append(start);

  words.forEach((item) => {
    const arrow = document.createElement("b");
    arrow.textContent = "›";
    const word = document.createElement("span");
    word.textContent = item.word;
    wordHistory.append(arrow, word);
  });

  const arrow = document.createElement("b");
  arrow.textContent = "›";
  const current = document.createElement("span");
  current.className = "history-current";
  current.textContent = nextLetter;
  wordHistory.append(arrow, current);
  wordHistory.scrollLeft = wordHistory.scrollWidth;
}

function renderModalHistory(words, nextLetter) {
  const nextSignature = JSON.stringify(
    words.map((item) => ({
      turn_number: String(item.turn_number),
      word: item.word,
      player_name: item.player_name,
    }))
  );

  modalCurrentLetter.textContent = nextLetter;
  if (nextSignature === renderedHistorySignature) {
    return;
  }

  const previousScrollTop = modalHistoryList.scrollTop;
  const wasNearBottom =
    modalHistoryList.scrollHeight -
      modalHistoryList.clientHeight -
      modalHistoryList.scrollTop <
    36;

  modalHistoryList.replaceChildren();

  if (words.length === 0) {
    const empty = document.createElement("li");
    empty.className = "history-empty";
    empty.textContent = "まだ言葉は送信されていません";
    modalHistoryList.append(empty);
  } else {
    words.forEach((item) => {
      const row = document.createElement("li");
      const turn = document.createElement("span");
      const word = document.createElement("strong");
      const player = document.createElement("small");
      turn.textContent = item.turn_number;
      word.textContent = item.word;
      player.textContent = item.player_name;
      row.append(turn, word, player);
      modalHistoryList.append(row);
    });
  }

  renderedHistorySignature = nextSignature;
  if (wasNearBottom) {
    modalHistoryList.scrollTop = modalHistoryList.scrollHeight;
  } else {
    modalHistoryList.scrollTop = previousScrollTop;
  }
}

function schedulePlayerUpdate() {
  window.setTimeout(updatePlayers, PLAYER_POLL_INTERVAL);
}

schedulePlayerUpdate();
window.requestAnimationFrame(fitCurrentWord);
window.addEventListener("resize", fitCurrentWord);
