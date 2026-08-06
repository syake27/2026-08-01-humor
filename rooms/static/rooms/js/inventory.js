"use strict";

const itemCards = document.querySelectorAll(".inventory-item");
const itemModal = document.getElementById("item-detail-modal");
const itemModalClose = document.getElementById("item-modal-close");
const itemModalType = document.getElementById("item-modal-type");
const itemModalName = document.getElementById("item-modal-name");
const itemModalPreview = document.getElementById("item-modal-preview");
const itemModalIcon = document.getElementById("item-modal-icon");
const itemModalAcquisition = document.getElementById("item-modal-acquisition");
const itemLockState = document.getElementById("item-lock-state");
const itemEquipForm = document.getElementById("item-equip-form");
const equipItemCode = document.getElementById("equip-item-code");
const itemEquipButton = document.getElementById("item-equip-button");
const itemModalMessage = document.getElementById("item-modal-message");
let activeItemCard = null;

function updateCardBadge(card, isEquipped) {
  const badge = card.querySelector(
    ".equipped-badge, .owned-badge, .locked-badge"
  );
  if (!badge || card.dataset.isOwned !== "true") return;

  card.dataset.isEquipped = String(isEquipped);
  badge.className = isEquipped ? "equipped-badge" : "owned-badge";
  badge.textContent = isEquipped ? "装備中" : "所持中";
}

function openItemModal(card) {
  activeItemCard = card;
  const isOwned = card.dataset.isOwned === "true";
  const isEquipped = card.dataset.isEquipped === "true";
  const itemType = card.dataset.itemType;

  itemModalType.textContent = card.dataset.itemTypeLabel;
  itemModalName.textContent = card.dataset.itemName;
  itemModalAcquisition.textContent = card.dataset.acquisitionMethod;
  itemModalPreview.className = `item-modal-preview is-${itemType}`;
  itemModalIcon.textContent = itemType === "frame" ? "" : card.dataset.itemIcon;
  itemLockState.hidden = isOwned;
  itemEquipForm.hidden = !isOwned;
  equipItemCode.value = card.dataset.itemCode;
  itemEquipButton.disabled = isEquipped;
  itemEquipButton.textContent = isEquipped ? "装備中" : "装備する";
  itemModalMessage.textContent = "";
  itemModal.showModal();
}

itemCards.forEach((card) => {
  card.addEventListener("click", () => openItemModal(card));
});

itemModalClose.addEventListener("click", () => itemModal.close());

itemModal.addEventListener("click", (event) => {
  if (event.target === itemModal) itemModal.close();
});

itemModal.addEventListener("close", () => {
  if (activeItemCard) activeItemCard.focus();
});

itemEquipForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activeItemCard || itemEquipButton.disabled) return;

  itemEquipButton.disabled = true;
  itemEquipButton.textContent = "変更中…";
  itemModalMessage.textContent = "";

  try {
    const response = await fetch(itemEquipForm.action, {
      method: "POST",
      body: new FormData(itemEquipForm),
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    const result = await response.json();

    if (!response.ok) {
      itemEquipButton.disabled = false;
      itemEquipButton.textContent = "装備する";
      itemModalMessage.textContent = result.error || "装備を変更できませんでした";
      return;
    }

    itemCards.forEach((card) => {
      if (
        card.dataset.itemType === result.item_type &&
        card.dataset.isOwned === "true"
      ) {
        updateCardBadge(card, card.dataset.itemCode === result.item_code);
      }
    });
    itemEquipButton.textContent = "装備中";
    itemModalMessage.textContent = result.message;
  } catch (error) {
    itemEquipButton.disabled = false;
    itemEquipButton.textContent = "装備する";
    itemModalMessage.textContent = "通信を確認してもう一度お試しください";
  }
});
