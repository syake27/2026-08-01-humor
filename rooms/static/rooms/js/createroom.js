"use strict";

const MIN_MEMBERS = 2;
const MAX_MEMBERS = 4;

const membersInput = document.getElementById("members");
const decreaseButton = document.getElementById("decrease-members");
const increaseButton = document.getElementById("increase-members");
const babaCharactersInput = document.getElementById("baba-characters");
const babaCharacterCount = document.getElementById("baba-character-count");
const timeSlider = document.getElementById("time-slider");
const timeValue = document.getElementById("time-value");

function updateTimeSlider() {
  const minimum = Number(timeSlider.min);
  const maximum = Number(timeSlider.max);
  const current = Number(timeSlider.value);
  const progress = ((current - minimum) / (maximum - minimum)) * 100;

  timeValue.textContent = `${current}秒`;
  timeSlider.parentElement.style.setProperty(
    "--time-progress",
    `${progress}%`
  );
}

timeSlider.addEventListener("input", updateTimeSlider);
updateTimeSlider();

/**
 * 人数を2〜4人の範囲に調整する
 *
 * @param {number} amount 増減させる人数
 */
function changeMembers(amount) {
  const currentValue = Number(membersInput.value) || MIN_MEMBERS;
  const newValue = currentValue + amount;

  membersInput.value = Math.min(
    MAX_MEMBERS,
    Math.max(MIN_MEMBERS, newValue)
  );

  updateMemberButtons();
}

/**
 * 最小値・最大値に達したボタンを無効化する
 */
function updateMemberButtons() {
  const currentValue = Number(membersInput.value);

  decreaseButton.disabled = currentValue <= MIN_MEMBERS;
  increaseButton.disabled = currentValue >= MAX_MEMBERS;
}

/**
 * 入力欄に範囲外の数値が入った場合に修正する
 */
function validateMemberValue() {
  const currentValue = Number(membersInput.value);

  if (!Number.isFinite(currentValue)) {
    membersInput.value = MIN_MEMBERS;
  } else {
    membersInput.value = Math.min(
      MAX_MEMBERS,
      Math.max(MIN_MEMBERS, currentValue)
    );
  }

  updateMemberButtons();
}

decreaseButton.addEventListener("click", () => {
  changeMembers(-1);
});

increaseButton.addEventListener("click", () => {
  changeMembers(1);
});

membersInput.addEventListener("change", validateMemberValue);

membersInput.addEventListener("input", updateMemberButtons);

updateMemberButtons();

function updateBabaCharacterCount() {
  const allowedCharacters = new Set(
    Array.from(babaCharactersInput.dataset.allowedCharacters)
  );
  const selectedCharacters = new Set(
    Array.from(babaCharactersInput.value).filter((character) =>
      allowedCharacters.has(character)
    )
  );

  babaCharacterCount.textContent = selectedCharacters.size;
}

babaCharactersInput.addEventListener("input", updateBabaCharacterCount);
updateBabaCharacterCount();
