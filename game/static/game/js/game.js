"use strict";

const answerForm = document.querySelector(".answer-form");
const answerInput = document.getElementById("answer-input");
const clearAnswerButton = document.getElementById("clear-answer");
const gameMessage = document.getElementById("game-message");
const gameMenuButton = document.getElementById("game-menu-button");
const gameMenu = document.getElementById("game-menu");
const gameMenuWrap = document.querySelector(".game-menu-wrap");

function showMessage(title, detail, isSuccess = false) {
  gameMessage.classList.toggle("is-success", isSuccess);
  gameMessage.querySelector(".message-icon").textContent = isSuccess ? "✓" : "!";
  gameMessage.querySelector("strong").textContent = title;
  gameMessage.querySelector("small").textContent = detail;
}

clearAnswerButton.addEventListener("click", () => {
  answerInput.value = "";
  answerInput.focus();
});

answerForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const answer = answerInput.value.trim();

  if (!answer) {
    showMessage("言葉を入力してください", "「き」からはじまる言葉を考えよう");
    return;
  }

  if (!answer.startsWith("き")) {
    showMessage("その文字ではつながりません", "「き」からはじまる言葉を入力してください");
    return;
  }

  showMessage("送信しました！", `${answer} を回答として受け付けました`, true);
  answerInput.value = "";
});

function closeGameMenu() {
  gameMenu.hidden = true;
  gameMenuButton.setAttribute("aria-expanded", "false");
}

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
    gameMenuButton.focus();
  }
});
