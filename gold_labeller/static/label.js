(function () {
  const form = document.getElementById("label-form");
  if (!form) return;

  const recordId = form.dataset.recordId;
  const nextId = form.dataset.nextId;
  const statusEl = document.getElementById("save-status");
  const dropped = document.getElementById("dropped");
  const stepB = document.getElementById("step-b-fieldset");
  const progress = document.getElementById("progress");

  function toggleStepB() {
    const isDropped = dropped && dropped.checked;
    if (stepB) {
      stepB.classList.toggle("disabled", isDropped);
    }
  }

  if (dropped) {
    dropped.addEventListener("change", toggleStepB);
    toggleStepB();
  }

  function formPayload() {
    const data = new FormData(form);
    const payload = Object.fromEntries(data.entries());
    payload.ontology_match = form.querySelector('[name="ontology_match"]').checked;
    payload.dropped = dropped ? dropped.checked : false;
    payload.labelled = true;
    return payload;
  }

  function fillForm(row) {
    const setRadio = (name, value) => {
      const el = form.querySelector(`input[name="${name}"][value="${value}"]`);
      if (el) el.checked = true;
    };
    if (row.is_food_entity !== undefined && row.is_food_entity !== "") {
      setRadio("is_food_entity", String(row.is_food_entity).toLowerCase() === "true" ? "true" : "false");
    }
    if (row.is_metaphor !== undefined && row.is_metaphor !== "") {
      setRadio("is_metaphor", String(row.is_metaphor).toLowerCase() === "true" ? "true" : "false");
    }
    const setVal = (name, value) => {
      const el = form.querySelector(`[name="${name}"]`);
      if (el && value !== undefined && value !== null) el.value = value;
    };
    setVal("formal_dimension", row.formal_dimension);
    setVal("canonical_pref_label", row.canonical_pref_label);
    setVal("step_a_reasoning", row.step_a_reasoning);
    setVal("drop_reason", row.drop_reason);
    setVal("selected_frame", row.selected_frame);
    setVal("lexical_unit", row.lexical_unit);
    setVal("step_b_reasoning", row.step_b_reasoning);
    setVal("notes", row.notes);
    const ont = form.querySelector('[name="ontology_match"]');
    if (ont) ont.checked = ["true", "1", "True"].includes(String(row.ontology_match));
    if (dropped) dropped.checked = ["true", "1", "True"].includes(String(row.dropped));
    toggleStepB();
  }

  async function save(andNext) {
    statusEl.textContent = "Saving…";
    statusEl.className = "save-status";
    try {
      const res = await fetch(`/api/save/${encodeURIComponent(recordId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formPayload()),
      });
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      if (progress && body.stats) {
        progress.textContent = `${body.stats.labelled} / ${body.stats.total} labelled`;
      }
      statusEl.textContent = "Saved.";
      statusEl.className = "save-status ok";
      if (andNext && nextId) {
        window.location.href = `/label/${encodeURIComponent(nextId)}`;
      }
    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`;
      statusEl.className = "save-status err";
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    save(true);
  });

  document.getElementById("btn-save-stay")?.addEventListener("click", () => save(false));

  document.getElementById("btn-suggest")?.addEventListener("click", async () => {
    statusEl.textContent = "LLM suggest… (may take a minute)";
    statusEl.className = "save-status";
    try {
      const res = await fetch(`/api/suggest/${encodeURIComponent(recordId)}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      fillForm(body.suggestion);
      statusEl.textContent = "Suggestion loaded — review and save.";
      statusEl.className = "save-status ok";
    } catch (err) {
      statusEl.textContent = `Suggest failed: ${err.message}`;
      statusEl.className = "save-status err";
    }
  });
})();
