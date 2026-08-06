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
const gamePickerModal = document.getElementById("game-picker-modal");
const gamePickerTitle = document.getElementById("game-picker-title");
const gamePickerCloseButton = document.getElementById("game-picker-close");
const gamePickerButtons = document.querySelectorAll("[data-picker]");
const gamePickerPanels = document.querySelectorAll("[data-picker-panel]");
const gamePickerOptions = document.querySelectorAll(".game-picker-option");
const babaButton = document.getElementById("baba-button");
const babaGuessModal = document.getElementById("baba-guess-modal");
const babaGuessForm = document.getElementById("baba-guess-form");
const babaGuessInput = document.getElementById("baba-guess-input");
const babaGuessError = document.getElementById("baba-guess-error");
const babaGuessCancelButton = document.getElementById("baba-guess-cancel");
const babaGuessSubmitButton = document.getElementById("baba-guess-submit");
const babaChallengeStartButton = document.getElementById("baba-challenge-start");
const babaConfirmStep = document.getElementById("baba-confirm-step");
const babaInputStep = document.getElementById("baba-input-step");
const babaChallengeNotice = document.getElementById("baba-challenge-notice");
const babaChallengerName = document.getElementById("baba-challenger-name");
const babaPreviewLetter = document.getElementById("baba-preview-letter");
const babaChallengeCaption = document.getElementById("baba-challenge-caption");
const babaChallengeStatus = document.getElementById("baba-challenge-status");
const babaRoulette = document.getElementById("baba-roulette");
const babaRouletteLabel = document.getElementById("baba-roulette-label");
const babaRouletteValue = document.getElementById("baba-roulette-value");
const babaSlotTrack = document.getElementById("baba-slot-track");
const babaExplosion = document.getElementById("baba-explosion");
const PLAYER_POLL_INTERVAL = 750;
const BABA_RESULT_HOLD_MS = 2600;
const BABA_EXPLOSION_DELAY_MS = 1000;
let focusedPlayerId = null;
let isComposingAnswer = false;
let isComposingBaba = false;
let isMovingToResult = false;
let babaChallengeLocked = babaGuessModal.dataset.selfChallenging === "true";
const initialBabaRevealActive = babaGuessModal.dataset.revealActive === "true";
let babaPreviewTimer = null;
let babaRouletteTimeout = null;
let babaSlowdownTimers = [];
let babaExplosionTimer = null;
let babaExplosionEndTimer = null;
let babaWordExplosionTimer = null;
let babaRevealSignature = "";
let lastRenderedStampId = Number(playersStrip.dataset.lastStampId || 0);
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

function resetBabaRoulette() {
  window.clearTimeout(babaRouletteTimeout);
  babaSlowdownTimers.forEach((timer) => window.clearTimeout(timer));
  window.clearTimeout(babaExplosionTimer);
  window.clearTimeout(babaExplosionEndTimer);
  window.clearTimeout(babaWordExplosionTimer);
  babaSlowdownTimers = [];
  babaExplosionTimer = null;
  babaExplosionEndTimer = null;
  babaWordExplosionTimer = null;
  babaRouletteTimeout = null;
  babaRevealSignature = "";
  babaRoulette.hidden = true;
  babaRoulette.classList.remove(
    "is-spinning",
    "is-slow",
    "is-stopping",
    "is-correct",
    "is-wrong"
  );
  babaSlotTrack.hidden = false;
  babaRouletteValue.hidden = true;
  if (babaExplosion.open) babaExplosion.close();
  babaChallengeNotice.classList.remove("is-shaking");
  babaChallengeCaption.hidden = false;
}

function showBabaExplosion() {
  if (babaExplosion.open) babaExplosion.close();
  babaChallengeNotice.classList.remove("is-shaking");
  void babaExplosion.offsetWidth;
  babaExplosion.showModal();
  babaChallengeNotice.classList.add("is-shaking");
  babaExplosionEndTimer = window.setTimeout(() => {
    if (babaExplosion.open) babaExplosion.close();
    babaChallengeNotice.classList.remove("is-shaking");
  }, 950);
}

function startBabaWordExplosion(reveal) {
  const signature = `${reveal.mode}:${reveal.ends_at}`;
  if (signature === babaRevealSignature) return;
  resetBabaRoulette();
  babaRevealSignature = signature;
  babaChallengeCaption.hidden = true;
  babaRoulette.hidden = true;
  if (babaChallengeNotice.open) babaChallengeNotice.close();
  babaWordExplosionTimer = window.setTimeout(showBabaExplosion, 60);
}

function startBabaRoulette(reveal) {
  const signature = `${reveal.ends_at}:${reveal.correct}`;
  if (signature === babaRevealSignature) return;
  resetBabaRoulette();
  babaRevealSignature = signature;
  babaChallengeCaption.hidden = true;
  babaRoulette.hidden = false;
  babaRoulette.classList.add("is-spinning");
  babaRouletteLabel.textContent = "判定中";
  babaSlotTrack.hidden = false;
  babaRouletteValue.hidden = true;

  const remaining = Math.max(Date.parse(reveal.ends_at) - Date.now(), 0);
  const settleDelay = Math.max(350, remaining - BABA_RESULT_HOLD_MS);
  const slowDelay = Math.max(0, settleDelay - 1450);
  const stoppingDelay = Math.max(slowDelay + 250, settleDelay - 650);
  babaSlowdownTimers.push(
    window.setTimeout(() => {
      babaRoulette.classList.add("is-slow");
    }, slowDelay),
    window.setTimeout(() => {
      babaRoulette.classList.remove("is-slow");
      babaRoulette.classList.add("is-stopping");
    }, stoppingDelay)
  );
  babaRouletteTimeout = window.setTimeout(() => {
    babaRoulette.classList.remove(
      "is-spinning",
      "is-slow",
      "is-stopping",
      "is-correct",
      "is-wrong"
    );
    babaRoulette.classList.add(reveal.correct ? "is-correct" : "is-wrong");
    babaRouletteLabel.textContent = "判定結果";
    babaSlotTrack.hidden = true;
    babaRouletteValue.hidden = false;
    babaRouletteValue.textContent = reveal.correct ? "正解！" : "不正解";
    if (!reveal.correct) {
      babaExplosionTimer = window.setTimeout(
        showBabaExplosion,
        BABA_EXPLOSION_DELAY_MS
      );
    }
  }, settleDelay);
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

babaButton.addEventListener("click", () => {
  if (babaChallengeLocked) return;
  babaGuessInput.value = "";
  babaGuessError.textContent = "";
  babaConfirmStep.hidden = false;
  babaInputStep.hidden = true;
  babaGuessModal.showModal();
});

babaGuessCancelButton.addEventListener("click", () => {
  if (!babaChallengeLocked) babaGuessModal.close();
});

function showBabaInputStep() {
  babaConfirmStep.hidden = true;
  babaInputStep.hidden = false;
  if (!babaGuessModal.open) babaGuessModal.showModal();
  window.setTimeout(() => babaGuessInput.focus(), 50);
}

babaChallengeStartButton.addEventListener("click", async () => {
  babaChallengeStartButton.disabled = true;
  const formData = new FormData();
  formData.append("room_id", babaGuessModal.dataset.roomId);
  formData.append("csrfmiddlewaretoken", answerForm.querySelector("[name=csrfmiddlewaretoken]").value);

  try {
    const response = await fetch(babaGuessModal.dataset.startUrl, {
      method: "POST",
      body: formData,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const game = await response.json();
    if (!response.ok) {
      showMessage("挑戦を開始できませんでした", game.error || "もう一度お試しください");
      return;
    }
    babaChallengeLocked = true;
    applyGameState(game);
    showBabaInputStep();
  } catch (error) {
    showMessage("挑戦を開始できませんでした", "通信を確認してもう一度お試しください");
  } finally {
    babaChallengeStartButton.disabled = false;
  }
});

babaGuessModal.addEventListener("click", (event) => {
  if (event.target === babaGuessModal && !babaChallengeLocked) {
    babaGuessModal.close();
  }
});

babaGuessModal.addEventListener("cancel", (event) => {
  if (babaChallengeLocked) event.preventDefault();
});

if (babaChallengeLocked && !initialBabaRevealActive) {
  showBabaInputStep();
}

if (
  babaGuessModal.dataset.challengeActive === "true" &&
  (babaGuessModal.dataset.selfChallenging !== "true" || initialBabaRevealActive) &&
  babaGuessModal.dataset.revealMode !== "word" &&
  !babaChallengeNotice.open
) {
  babaChallengeNotice.showModal();
}

if (initialBabaRevealActive) {
  const initialReveal = {
    correct: babaGuessModal.dataset.revealCorrect === "true",
    ends_at: babaGuessModal.dataset.revealUntil,
    mode: babaGuessModal.dataset.revealMode,
  };
  if (["word", "timeout"].includes(initialReveal.mode)) {
    startBabaWordExplosion(initialReveal);
  } else {
    startBabaRoulette(initialReveal);
  }
}

babaChallengeNotice.addEventListener("cancel", (event) => {
  event.preventDefault();
});

babaExplosion.addEventListener("cancel", (event) => {
  event.preventDefault();
});

async function sendBabaPreview() {
  if (!babaChallengeLocked) return;
  const normalizedPreview = babaGuessInput.value.normalize("NFKC").trim();
  const preview = /^[ぁ-ゖー]$/.test(normalizedPreview) ? normalizedPreview : "";
  const formData = new FormData();
  formData.append("room_id", babaGuessModal.dataset.roomId);
  formData.append("preview", preview);
  formData.append("csrfmiddlewaretoken", answerForm.querySelector("[name=csrfmiddlewaretoken]").value);
  try {
    await fetch(babaGuessModal.dataset.previewUrl, {
      method: "POST",
      body: formData,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (error) {
    // 判定送信は止めず、次の入力更新または状態取得で復帰する。
  }
}

function scheduleBabaPreview() {
  window.clearTimeout(babaPreviewTimer);
  babaPreviewTimer = window.setTimeout(sendBabaPreview, 160);
}

babaGuessInput.addEventListener("compositionstart", () => {
  isComposingBaba = true;
});

babaGuessInput.addEventListener("compositionend", () => {
  isComposingBaba = false;
  scheduleBabaPreview();
});

babaGuessInput.addEventListener("input", () => {
  if (!isComposingBaba) scheduleBabaPreview();
});

babaGuessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const guessedLetter = babaGuessInput.value.normalize("NFKC").trim();
  if (!/^[ぁ-ゖ]$/.test(guessedLetter)) {
    babaGuessError.textContent = "ひらがな1文字を入力してください";
    babaGuessInput.focus();
    return;
  }

  babaGuessSubmitButton.disabled = true;
  babaGuessError.textContent = "";
  const formData = new FormData();
  formData.append("room_id", babaGuessModal.dataset.roomId);
  formData.append("baba_letter", guessedLetter);
  formData.append("csrfmiddlewaretoken", answerForm.querySelector("[name=csrfmiddlewaretoken]").value);

  try {
    const response = await fetch(babaGuessModal.dataset.guessUrl, {
      method: "POST",
      body: formData,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const game = await response.json();
    if (!response.ok) {
      babaGuessError.textContent = game.error || "もう一度お試しください";
      if (moveToResult(game)) return;
      return;
    }

    babaGuessModal.close();
    if (moveToResult(game)) return;
    applyGameState(game);
  } catch (error) {
    babaGuessError.textContent = "通信できませんでした。もう一度お試しください";
  } finally {
    babaGuessSubmitButton.disabled = false;
  }
});

gamePickerButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const picker = button.dataset.picker;
    gamePickerTitle.textContent = picker === "stamp" ? "スタンプを選ぶ" : "アイテムを選ぶ";
    gamePickerPanels.forEach((panel) => {
      panel.hidden = panel.dataset.pickerPanel !== picker;
    });
    gamePickerModal.showModal();
  });
});

gamePickerCloseButton.addEventListener("click", () => {
  gamePickerModal.close();
});

gamePickerModal.addEventListener("click", (event) => {
  if (event.target === gamePickerModal) {
    gamePickerModal.close();
  }
});

function renderStamp(stamp) {
  if (!stamp || stamp.id <= lastRenderedStampId) return;
  lastRenderedStampId = stamp.id;

  const playerCard = playersStrip.querySelector(`[data-player-id="${stamp.player_id}"]`);
  const avatarFrame = playerCard?.querySelector(".player-avatar-frame");
  if (!avatarFrame) return;

  const previousStamp = avatarFrame.querySelector(".player-stamp-pop");
  if (previousStamp) previousStamp.remove();

  const bubble = document.createElement("span");
  bubble.className = "player-stamp-pop";
  const icon = document.createElement("strong");
  const label = document.createElement("small");
  icon.textContent = stamp.icon || "☺";
  label.textContent = stamp.name;
  bubble.append(icon, label);
  avatarFrame.append(bubble);
  bubble.addEventListener("animationend", () => bubble.remove(), { once: true });
}

gamePickerOptions.forEach((option) => {
  option.addEventListener("click", async () => {
    const name = option.dataset.optionName;
    const kind = option.dataset.optionKind;
    if (kind !== "スタンプ") {
      gamePickerModal.close();
      showMessage(`${kind}を選びました`, `「${name}」を選択しています`, true);
      return;
    }

    option.disabled = true;
    const formData = new FormData();
    formData.append("room_id", gamePickerModal.dataset.roomId);
    formData.append("stamp_code", option.dataset.itemCode);
    formData.append("csrfmiddlewaretoken", answerForm.querySelector("[name=csrfmiddlewaretoken]").value);

    try {
      const response = await fetch(gamePickerModal.dataset.stampUrl, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await response.json();
      if (!response.ok) {
        showMessage("スタンプを送れませんでした", data.error || "もう一度お試しください");
        return;
      }
      gamePickerModal.close();
      renderStamp(data.stamp);
      showMessage("スタンプを送りました", `「${name}」`, true);
    } catch (error) {
      showMessage("スタンプを送れませんでした", "接続を確認してもう一度お試しください");
    } finally {
      option.disabled = false;
    }
  });
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
  const babaChallenge = game.baba_challenge;
  const babaReveal = game.baba_reveal;
  const canAnswer = Boolean(
    me && me.is_alive && me.is_current && !babaChallenge
  );
  babaButton.disabled = !(me && me.is_alive) || Boolean(babaChallenge);
  if (babaChallenge) {
    babaChallengerName.textContent = babaChallenge.player_name;
    babaPreviewLetter.textContent = babaChallenge.preview || "？";
    babaChallengeStatus.textContent = "がBABAに挑戦中！";
  }
  if (babaReveal) {
    if (["word", "timeout"].includes(babaReveal.mode)) {
      startBabaWordExplosion(babaReveal);
    } else {
      startBabaRoulette(babaReveal);
    }
  } else {
    resetBabaRoulette();
  }
  const isWordExplosion = ["word", "timeout"].includes(babaReveal?.mode);
  if (babaChallenge && (!babaChallenge.is_self || babaReveal) && babaGuessModal.open) {
    babaGuessModal.close();
  }
  if (
    babaChallenge &&
    !isWordExplosion &&
    (!babaChallenge.is_self || babaReveal)
  ) {
    if (!babaChallengeNotice.open) babaChallengeNotice.showModal();
  } else if (babaChallengeNotice.open) {
    babaChallengeNotice.close();
  }
  if (babaChallenge?.is_self && !babaChallengeLocked && !babaReveal) {
    babaChallengeLocked = true;
    showBabaInputStep();
  }
  if (!babaChallenge) babaChallengeLocked = false;
  const acceptedLetterDisplay = game.accepted_start_letters.join("・");
  answerInput.disabled = !canAnswer;
  clearAnswerButton.disabled = !canAnswer;
  sendAnswerButton.disabled = !canAnswer;
  answerInput.placeholder = babaChallenge
    ? "BABAの判定を待っています"
    : canAnswer
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
  game.stamps.forEach(renderStamp);
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
