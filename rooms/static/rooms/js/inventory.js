"use strict";

const itemCards = document.querySelectorAll(".inventory-item");
const itemModal = document.getElementById("item-detail-modal");
const itemModalClose = document.getElementById("item-modal-close");
const itemModalType = document.getElementById("item-modal-type");
const itemModalName = document.getElementById("item-modal-name");
const itemModalPreview = document.getElementById("item-modal-preview");
const itemModalImage = document.getElementById("item-modal-image");
const itemModalIcon = document.getElementById("item-modal-icon");
const itemModalAcquisition = document.getElementById("item-modal-acquisition");
const itemLockState = document.getElementById("item-lock-state");
const itemEquipForm = document.getElementById("item-equip-form");
const equipItemCode = document.getElementById("equip-item-code");
const itemEquipButton = document.getElementById("item-equip-button");
const itemModalMessage = document.getElementById("item-modal-message");
let activeItemCard = null;

function restoreEquipButton() {
  const isStampEquipped =
    activeItemCard?.dataset.itemType === "stamp" &&
    activeItemCard.dataset.isEquipped === "true";
  itemEquipButton.disabled =
    activeItemCard?.dataset.isEquipped === "true" && !isStampEquipped;
  itemEquipButton.textContent = isStampEquipped ? "装備解除" : "装備する";
}

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
  const canEquip = card.dataset.canEquip === "true";
  const itemType = card.dataset.itemType;
  const itemImage = card.dataset.itemImage;

  itemModalType.textContent = card.dataset.itemTypeLabel;
  itemModalName.textContent = card.dataset.itemName;
  itemModalAcquisition.textContent = card.dataset.acquisitionMethod;
  itemModalPreview.className = `item-modal-preview is-${itemType}`;
  itemModalImage.hidden = !itemImage;
  itemModalImage.src = itemImage || "";
  itemModalIcon.hidden = Boolean(itemImage);
  itemModalIcon.textContent = itemType === "frame" ? "" : card.dataset.itemIcon;
  itemLockState.hidden = isOwned;
  itemEquipForm.hidden = !isOwned || !canEquip;
  equipItemCode.value = card.dataset.itemCode;
  const canUnequip = itemType === "stamp" && isEquipped;
  itemEquipButton.disabled = isEquipped && !canUnequip;
  itemEquipButton.textContent = canUnequip
    ? "装備解除"
    : isEquipped
      ? "装備中"
      : "装備する";
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
      restoreEquipButton();
      itemModalMessage.textContent = result.error || "装備を変更できませんでした";
      return;
    }

    itemCards.forEach((card) => {
      if (
        card.dataset.itemType === result.item_type &&
        card.dataset.isOwned === "true"
      ) {
        // Stamps occupy six independent slots; equipping one must not
        // clear the other equipped stamps. Other customization types remain
        // single-select as before.
        if (result.item_type === "stamp") {
          if (card.dataset.itemCode === result.item_code) {
            updateCardBadge(card, result.is_equipped);
          }
        } else {
          updateCardBadge(card, card.dataset.itemCode === result.item_code);
        }
      }
    });
    if (result.item_type === "stamp") {
      itemEquipButton.disabled = false;
      itemEquipButton.textContent = result.is_equipped ? "装備解除" : "装備する";
    } else {
      itemEquipButton.textContent = "装備中";
    }
    itemModalMessage.textContent = result.message;
  } catch (error) {
    restoreEquipButton();
    itemModalMessage.textContent = "通信を確認してもう一度お試しください";
  }
});
