(function () {
  const form = document.getElementById("stepc-form");
  if (!form) return;

  const frameSelect = document.getElementById("selected_frame");
  const actionInput = document.getElementById("form_action");
  const nextInput = document.getElementById("next_record_id");
  const dropped = document.getElementById("dropped");
  const nextId = form.dataset.nextId || "";
  const groups = Array.from(document.querySelectorAll(".qualia-group[data-frame]"));
  const frames = ["COOKING_CREATION", "CURE", "INGESTION", "PRESERVING", "NONE"];

  function syncQualia() {
    const frame = frameSelect ? frameSelect.value : "";
    for (const group of groups) {
      const match = group.dataset.frame === frame;
      group.hidden = !match;
      group.classList.toggle("is-active", match);
    }
  }

  function typingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  }

  function prepareAction(action) {
    if (actionInput) actionInput.value = action;
    if (action === "drop_next" && dropped) {
      dropped.checked = true;
    }
    if (nextInput) {
      nextInput.value = action === "save" ? "" : nextId;
    }
  }

  function submitAction(action) {
    prepareAction(action);
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }

  function navigateSibling(direction) {
    const links = Array.from(
      document.querySelectorAll('.record-nav a[href*="/label/"]'),
    );
    const link = links.find((a) => {
      const label = a.textContent.trim().toLowerCase();
      return direction === "prev"
        ? label.startsWith("previous")
        : label.startsWith("next");
    });
    if (link?.href) {
      window.location.assign(link.href);
    }
  }

  form.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-action]");
    if (!btn) return;
    prepareAction(btn.dataset.action);
  });

  form.addEventListener("submit", () => {
    // Ensure action is set even when Enter submits the first button.
    if (actionInput && !actionInput.value) {
      actionInput.value = "save_next";
    }
  });

  if (frameSelect) {
    frameSelect.addEventListener("change", syncQualia);
    syncQualia();
  }

  document.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (typingTarget(event.target)) {
      if (event.key === "Escape") {
        event.target.blur();
      }
      return;
    }

    const key = event.key.toLowerCase();
    if (key === "s") {
      event.preventDefault();
      submitAction("save_next");
      return;
    }
    if (key === "d") {
      event.preventDefault();
      submitAction("drop_next");
      return;
    }
    if (key === "n") {
      event.preventDefault();
      navigateSibling("next");
      return;
    }
    if (key === "p") {
      event.preventDefault();
      navigateSibling("prev");
      return;
    }
    if (key === "/") {
      event.preventDefault();
      const active = document.querySelector(".qualia-group.is-active");
      const food = document.getElementById("ingestion_food_patient");
      const focusEl =
        food && active && active.contains(food)
          ? food
          : active
            ? active.querySelector("input")
            : null;
      focusEl?.focus();
      return;
    }
    if (key >= "1" && key <= "5" && frameSelect) {
      event.preventDefault();
      const frame = frames[Number(key) - 1];
      if (frame) {
        frameSelect.value = frame;
        syncQualia();
      }
    }
  });
})();
