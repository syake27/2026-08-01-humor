(() => {
  const shop = document.querySelector(".shop");
  const tabs = [...document.querySelectorAll(".shop-tab")];
  if (!shop || !tabs.length) return;

  const items = [...shop.querySelectorAll(".item[data-categories]")];
  const config = document.getElementById("shop-purchase-config");
  const message = document.getElementById("shop-purchase-message");
  const coinBalance = document.querySelector(".coin-balance");
  const buyButtons = [...shop.querySelectorAll(".buy[data-item-code]")];
  const purchaseModal = document.getElementById("purchase-modal");
  const modalClose = document.getElementById("purchase-modal-close");
  const modalCancel = document.getElementById("purchase-modal-cancel");
  const modalConfirm = document.getElementById("purchase-modal-confirm");
  const modalPreview = document.getElementById("purchase-modal-preview");
  const modalName = document.getElementById("purchase-modal-name");
  const modalDescription = document.getElementById("purchase-modal-description");
  const modalPrice = document.getElementById("purchase-modal-price");
  const modalBalance = document.getElementById("purchase-modal-balance");
  const modalError = document.getElementById("purchase-modal-error");
  let activeBuyButton = null;

  const selectCategory = (category) => {
    tabs.forEach((tab) => {
      const isActive = tab.dataset.category === category;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
    });

    shop.classList.toggle("is-filtered", category !== "limited");
    items.forEach((item) => {
      const categories = item.dataset.categories.split(/\s+/);
      item.hidden = !categories.includes(category);
    });
    shop.scrollTop = 0;
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => selectCategory(tab.dataset.category));
  });

  selectCategory("limited");

  const showMessage = (text, isError = false) => {
    message.textContent = text;
    message.classList.toggle("is-error", isError);
    message.hidden = false;
  };

  const closePurchaseModal = () => {
    if (purchaseModal.open && !modalConfirm.disabled) purchaseModal.close();
  };

  buyButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      activeBuyButton = button;
      const item = button.closest(".item");
      modalPreview.innerHTML = item.querySelector(".item-icon").innerHTML;
      modalName.textContent = button.dataset.itemName;
      modalDescription.textContent = item.querySelector(".left p").textContent;
      modalPrice.textContent = button.dataset.price;
      modalBalance.textContent = coinBalance.textContent.trim();
      modalError.hidden = true;
      modalConfirm.disabled = false;
      modalConfirm.innerHTML = '<i class="fa-solid fa-bag-shopping" aria-hidden="true"></i> 購入する';
      purchaseModal.showModal();
    });
  });

  modalClose.addEventListener("click", closePurchaseModal);
  modalCancel.addEventListener("click", closePurchaseModal);
  purchaseModal.addEventListener("click", (event) => {
    if (event.target === purchaseModal) closePurchaseModal();
  });
  purchaseModal.addEventListener("cancel", (event) => {
    if (modalConfirm.disabled) event.preventDefault();
  });

  modalConfirm.addEventListener("click", async () => {
    if (!activeBuyButton || modalConfirm.disabled) return;
    if (config.dataset.authenticated !== "true") {
      window.location.assign(config.dataset.loginUrl);
      return;
    }

    modalConfirm.disabled = true;
    modalConfirm.textContent = "購入中…";
    modalError.hidden = true;
    message.hidden = true;

    try {
      const body = new FormData();
      body.append("item_code", activeBuyButton.dataset.itemCode);
      body.append(
        "csrfmiddlewaretoken",
        config.querySelector("[name=csrfmiddlewaretoken]").value
      );
      const response = await fetch(config.dataset.purchaseUrl, {
        method: "POST",
        body,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const result = await response.json();
      if (!response.ok) {
        modalConfirm.disabled = false;
        modalConfirm.textContent = "購入する";
        modalError.textContent = result.error || "購入できませんでした。";
        modalError.hidden = false;
        if (typeof result.coin_balance !== "undefined") {
          modalBalance.textContent = String(result.coin_balance);
          coinBalance.textContent = String(result.coin_balance);
        }
        if (result.quantity >= 99 && activeBuyButton.dataset.itemType === "card") {
          activeBuyButton.dataset.quantity = String(result.quantity);
          activeBuyButton.disabled = true;
          activeBuyButton.textContent = "上限";
        }
        return;
      }

      if (result.item_type === "card") {
        activeBuyButton.dataset.quantity = String(result.quantity);
        const stock = activeBuyButton
          .closest(".item")
          .querySelector(".card-owned-count");
        if (stock) stock.textContent = `所持 ${result.quantity}/99`;
        activeBuyButton.disabled = result.is_maxed;
        activeBuyButton.textContent = result.is_maxed ? "上限" : "購入";
      } else {
        activeBuyButton.dataset.owned = "true";
        activeBuyButton.textContent = "所持済み";
        activeBuyButton.disabled = true;
      }
      coinBalance.textContent = String(result.coin_balance);
      modalBalance.textContent = String(result.coin_balance);
      purchaseModal.close();
      showMessage(result.message);
    } catch (_error) {
      modalConfirm.disabled = false;
      modalConfirm.textContent = "購入する";
      modalError.textContent = "通信を確認してもう一度お試しください。";
      modalError.hidden = false;
    }
  });
})();
