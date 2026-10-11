/* Onigiri settings — WebUI front end.
 *
 * Renders whatever settings_web/schema.py describes. Adding a setting should
 * never mean touching this file: add a dict to the schema, and if it needs a new
 * control, add one renderer to FIELD_RENDERERS below.
 *
 * Edits auto-save: each change goes into `pending` and is flushed to Python as a
 * small patch — immediately for discrete controls, debounced for typing and
 * dragging. There is no Save button and therefore no unsaved state to lose.
 */

(function () {
  "use strict";

  const CTX = ONIGIRI_SETTINGS_CONTEXT || {};
  const PAGES = CTX.pages || [];
  const STRINGS = CTX.strings || {};

  const pageById = {};
  PAGES.forEach(function (page) { pageById[page.id] = page; });

  const fieldById = {};
  PAGES.forEach(function (page) {
    (page.sections || []).forEach(function (section) {
      (section.fields || []).forEach(function (field) {
        field.__page = page.id;
        fieldById[field.id] = field;
      });
    });
  });

  const values = {};       // field id -> current value
  Object.keys(fieldById).forEach(function (id) {
    const field = fieldById[id];
    let value = field.value;
    // Old Sidebar Typography builds allowed values below today's 8px floor.
    // Normalize any persisted numeric value before both the input and preview
    // read it, so a legacy 2px value cannot make a working control look inert.
    if ((field.type === "number" || field.type === "slider") && Number.isFinite(Number(value))) {
      const scale = field.scale > 0 ? field.scale : 1;
      value = Number(value);
      if (field.min != null) value = Math.max(Number(field.min) * scale, value);
      if (field.max != null) value = Math.min(Number(field.max) * scale, value);
    }
    values[id] = value;
  });

  let currentPage = (CTX.initialPage && pageById[CTX.initialPage])
    ? CTX.initialPage
    : (PAGES.length ? PAGES[0].id : null);
  // Restore the saved presentation; Advanced remains the default for new or
  // invalid preferences. Simple uses the existing schema's reduced controls.
  let settingsComplexity = CTX.settingsComplexity === "simple" ? "simple" : "advanced";
  const SETTINGS_MODE_PARITY = false;
  let toastTimer = null;

  // Auto-save state. `pending` is what has changed but not yet reached Python.
  let pending = {};
  let flushTimer = null;
  let inFlight = false;
  let statusTimer = null;
  let profileContextRevision = 0;
  // Theme application updates a large group of bound values at once. Hold the
  // dependent preview painters until that group is complete so a card never
  // briefly mixes values from two themes.
  let deferringPreviewRefresh = false;
  const FLUSH_DELAY = 300;

  // ── helpers ────────────────────────────────────────────────────────────────

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function str(key, fallback) {
    const value = STRINGS[key];
    return (value == null || value === "") ? fallback : value;
  }

  function bridge(command) {
    try { pycmd(command); } catch (err) { /* dialog is closing */ }
  }

  /* Anki hands the Python handler's return value to the pycmd callback, already
     JSON-parsed. Used for the auto-save patch, which needs a real result so a
     failed write surfaces instead of vanishing. */
  function call(command) {
    return new Promise(function (resolve) {
      if (typeof pycmd !== "function") {
        resolve({ ok: false, error: "Bridge not ready" });
        return;
      }
      try {
        pycmd(command, function (res) {
          if (typeof res === "string") {
            try { res = JSON.parse(res); } catch (err) { /* leave as-is */ }
          }
          resolve(res || { ok: false, error: "No response" });
        });
      } catch (err) {
        resolve({ ok: false, error: String(err) });
      }
    });
  }

  function hexToRgb(hex) {
    let value = String(hex || "").trim().replace("#", "");
    if (value.length === 3) value = value.split("").map(function (c) { return c + c; }).join("");
    if (value.length !== 6 || /[^0-9a-f]/i.test(value)) return [0, 169, 130];
    return [0, 2, 4].map(function (i) { return parseInt(value.slice(i, i + 2), 16); });
  }

  function rgba(hex, alpha) {
    const rgb = hexToRgb(hex);
    return "rgba(" + rgb[0] + ", " + rgb[1] + ", " + rgb[2] + ", " + alpha + ")";
  }

  function mix(hexA, hexB, amount) {
    const a = hexToRgb(hexA);
    const b = hexToRgb(hexB);
    const out = [0, 1, 2].map(function (i) {
      return Math.round(a[i] + (b[i] - a[i]) * (1 - amount));
    });
    return "#" + out.map(function (c) {
      return Math.max(0, Math.min(255, c)).toString(16).padStart(2, "0");
    }).join("");
  }

  // ── theme tokens ───────────────────────────────────────────────────────────

  function applyTheme() {
    const pal = CTX.palette || {};
    const accent = CTX.accent || "#00a982";
    const root = document.documentElement.style;
    const map = {
      outer: "--osw-outer", panel: "--osw-panel", surface: "--osw-surface",
      surface_alt: "--osw-surface-alt", inset: "--osw-inset",
      inset_hover: "--osw-inset-hover", hairline: "--osw-hairline",
      hairline_soft: "--osw-hairline-soft", fg: "--osw-fg",
      fg_muted: "--osw-fg-muted", fg_faint: "--osw-fg-faint",
      shadow: "--osw-shadow", danger: "--osw-danger"
    };
    Object.keys(map).forEach(function (key) {
      if (pal[key]) root.setProperty(map[key], pal[key]);
    });
    root.setProperty("--osw-accent", accent);
    // Precomputed accent tints — this webview's Chromium has no CSS mixing.
    root.setProperty("--osw-accent-a14", rgba(accent, 0.14));
    root.setProperty("--osw-accent-a16", rgba(accent, 0.16));
    root.setProperty("--osw-accent-line", mix(accent, pal.hairline || "#e3e4e7", 0.45));
    root.setProperty("--osw-accent-line-strong", mix(accent, pal.hairline || "#e3e4e7", 0.55));
    root.setProperty("--osw-accent-wash", mix(accent, pal.surface || "#ffffff", 0.05));
    root.setProperty("--osw-accent-wash-strong", mix(accent, pal.surface || "#ffffff", 0.07));
  }

  // ── value plumbing ─────────────────────────────────────────────────────────

  /* opts.debounce  wait for typing/dragging to settle before writing
     opts.keepDom   don't re-render the control (it's the one being typed in)
     opts.silent    skip cascades and toasts (used when echoing a value back) */
  function setValue(id, value, options) {
    const opts = options || {};
    if (values[id] === value) return;
    values[id] = value;
    profileContextRevision += 1;

    const field = fieldById[id];
    // A virtual field has no binding in Python — it is a second way of editing
    // some *other* field (the chip's opacity slider edits the alpha inside the
    // chip's colour). Staging it would come back as a save error.
    if (!field || !field.virtual) pending[id] = value;
    if (field && !opts.silent) {
      if (field.cascade && !opts.skipCascade) applyCascade(field, value);
      if (value && field.toastOn) toast(field.toastOn);
    }
    if (!opts.keepDom) {
      syncField(id);
    } else {
      refreshSettingsPreviews();
    }
    refreshProfileLevelLinks();
    refreshPageVisibility();
    if (document.getElementById("oswProfilePreviewCard")) updateProfileVisibility();

    // A zero delay still coalesces: a cascade's synchronous setValue calls all
    // land in `pending` before the timer fires, so they travel as one patch.
    scheduleFlush(opts.debounce ? FLUSH_DELAY : 0);
  }

  function applyCascade(field, value) {
    const exact = Object.prototype.hasOwnProperty.call(field.cascade || {}, String(value));
    const rules = exact ? field.cascade[String(value)] : field.cascade[value ? "on" : "off"];
    if (!rules) return;
    Object.keys(rules).forEach(function (otherId) {
      if (fieldById[otherId]) setValue(otherId, rules[otherId], { skipCascade: true });
    });
  }

  // ── auto-save ──────────────────────────────────────────────────────────────

  function scheduleFlush(delay) {
    if (!Object.keys(pending).length) return;
    setStatus("saving");
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = setTimeout(flush, delay);
  }

  function flush() {
    flushTimer = null;
    if (inFlight) {
      // A write is already on the wire; re-arm so this patch follows it.
      scheduleFlush(FLUSH_DELAY);
      return;
    }
    const keys = Object.keys(pending);
    if (!keys.length) return;
    const patch = pending;
    pending = {};
    inFlight = true;
    call("osw:patch:" + JSON.stringify(patch)).then(function (res) {
      inFlight = false;
      if (!res || !res.ok) {
        // Put the patch back so the next flush retries it rather than dropping
        // the user's edit; anything newer than it wins.
        Object.keys(patch).forEach(function (id) {
          if (!(id in pending)) pending[id] = patch[id];
        });
        setStatus("error", (res && res.error) || null);
        return;
      }
      // Python resolves Sync with Anki from Anki's current mode. Repaint
      // the open settings window after the preference has been persisted.
      if (res.appearance && !("onigiri_theme_mode" in pending)) {
        CTX.dark = res.appearance.dark;
        CTX.palette = res.appearance.palette;
        CTX.accent = res.appearance.accent;
        applyTheme();
        refreshSettingsPreviews();
      }
      if (res.profilePreview && !Object.keys(pending).length) {
        applyProfileContext(res.profilePreview);
      }
      if (Object.keys(pending).length) scheduleFlush(FLUSH_DELAY);
      else setStatus("saved");
    });
  }

  function setStatus(state, detail) {
    const node = document.getElementById("oswAutosave");
    if (!node) return;
    const label = node.querySelector(".osw-autosave-label");
    node.setAttribute("data-state", state);
    const text = {
      idle: str("autosave_idle", "Changes save automatically"),
      saving: str("autosave_saving", "Saving…"),
      saved: str("autosave_saved", "Saved"),
      error: detail || str("autosave_error", "Could not save")
    }[state] || "";
    if (label) label.textContent = text;

    if (statusTimer) clearTimeout(statusTimer);
    if (state === "saved") {
      statusTimer = setTimeout(function () { setStatus("idle"); }, 2200);
    }
  }

  /* Re-renders just the controls bound to one field. Cheaper and less jarring
     than rebuilding the page, and it keeps cascades from stealing focus. */
  function syncField(id) {
    const nodes = document.querySelectorAll('[data-field="' + id + '"]');
    Array.prototype.forEach.call(nodes, function (node) {
      const type = node.getAttribute("data-field-type");
      const value = values[id];
      if (type === "toggle" || type === "mode_card") {
        const host = node.closest(".osw-card") || node.closest(".osw-row") || node;
        host.classList.toggle("is-on", !!value);
        const sw = node.querySelector(".osw-switch, .osw-sq-switch") || node;
        if (sw.classList.contains("osw-switch") || sw.classList.contains("osw-sq-switch")) {
          sw.classList.toggle("is-on", !!value);
        }
        node.setAttribute("aria-pressed", value ? "true" : "false");
      } else if (type === "language") {
        markSelected(node, value);
        if (node.__paintHero) node.__paintHero();
      } else if (type === "choice") {
        Array.prototype.forEach.call(node.querySelectorAll(".osw-choice, .osw-segment-btn"), function (choice) {
          const selected = choice.getAttribute("data-value") === String(value);
          choice.classList.toggle("is-selected", selected && choice.classList.contains("osw-choice"));
          choice.classList.toggle("is-active", selected && choice.classList.contains("osw-segment-btn"));
          choice.setAttribute("aria-selected", selected ? "true" : "false");
        });
      } else if (type === "number" || type === "text") {
        const input = node.querySelector("input, textarea");
        const scale = (fieldById[id] && fieldById[id].scale > 0) ? fieldById[id].scale : 1;
        const shown = scale === 1 ? value : Math.round((Number(value) || 0) / scale);
        if (input && input.value !== String(shown)) input.value = shown;
      } else if (type === "select") {
        const sel = node.querySelector("select");
        if (sel && sel.value !== String(value)) sel.value = value;
        const trigger = node.querySelector(".osw-select-menu-trigger");
        if (trigger) {
          // Floating menus live outside the control while open, but patches
          // must still update their selected label and checkmark.
          const optionHost = node.__selectList || node;
          const option = optionHost.querySelector('.osw-select-menu-option[data-value="' + String(value).replace(/"/g, '\\"') + '"]');
          if (option) {
            trigger.querySelector(".osw-select-menu-value").textContent = option.getAttribute("data-label") || option.textContent;
            Array.prototype.forEach.call(optionHost.querySelectorAll(".osw-select-menu-option"), function (item) {
              const active = item === option;
              item.classList.toggle("is-active", active);
              item.setAttribute("aria-selected", active ? "true" : "false");
            });
          }
        }
      } else if (type === "color") {
        const swatch = node.querySelector(".osw-chip-swatch");
        const hex = node.querySelector(".osw-chip-hex");
        if (swatch) {
          swatch.style.background = value || "transparent";
          swatch.style.color = readableTextColor(value);
        }
        if (hex) hex.textContent = String(value || "").toUpperCase();
        // A marker card also draws the colour on its own deck-row preview.
        if (node.__syncMarker) node.__syncMarker();
      } else if (type === "button_order") {
        // A section Reset (or an external patch) replaces the whole layout
        // object, so the list rebuilds rather than nudging one row.
        if (node.__syncButtonOrder) node.__syncButtonOrder();
      } else if (type === "font") {
        const label = node.querySelector(".osw-chip-label");
        if (label) {
          const option = (fieldById[id].options || []).filter(function (o) { return o.value === value; })[0];
          label.textContent = option ? option.label : value;
          if (option && option.family) label.style.fontFamily = option.family;
        }
      }
    });
    if (!deferringPreviewRefresh) refreshSettingsPreviews();
  }

  function refreshSettingsPreviews() {
    // Immersion fields have no bound switch node anymore (the slider drives
    // them), so the ladder head/slider is always resynced here rather than
    // inside the field-control loop above.
    refreshLadders();
    refreshFontPreviews();
    refreshImageFields();
    refreshScenarioPickers();
    refreshIconChips();
    refreshPairFields();
    refreshGamesFields();
    refreshGameCards();
    refreshConditionalBlocks();
    refreshPomodoroSetups();
    updateProfilePreview();
    updateDesignerPreviews();
    refreshThemeStyleCards();
    refreshThingsPreviews();
    refreshProfileLevelLinks();
  }

  /* Games controls that paint themselves from `values` rather than from a
     plain input — a cascade or a native picker can move them without the click
     that would otherwise have repainted them. */
  function refreshGamesFields() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-gamechoice"), function (node) {
      if (node.__syncGameChoice) node.__syncGameChoice();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-notifpos"), function (node) {
      if (node.__syncNotifPos) node.__syncNotifPos();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-msglist"), function (node) {
      // Only when the list actually differs: repainting mid-typing would pull
      // the row out from under the cursor.
      if (node.__syncMessageList && document.activeElement &&
          !node.contains(document.activeElement)) {
        node.__syncMessageList();
      }
    });
  }

  function refreshFontPreviews() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-font-role-section"), function (node) {
      if (node.__updateFontPreview) node.__updateFontPreview();
    });
  }

  function refreshPomodoroSetups() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-pomo-setup"), function (node) {
      if (node.__syncPomodoroSetup) node.__syncPomodoroSetup();
    });
  }

  // ── field renderers ────────────────────────────────────────────────────────

  function makeSwitch(field) {
    const button = el("button", "osw-row-control " + (field.square ? "osw-sq-switch-btn" : "osw-switch-btn"));
    button.type = "button";
    button.setAttribute("data-field", field.id);
    button.setAttribute("data-field-type", field.type);
    button.setAttribute("aria-pressed", values[field.id] ? "true" : "false");
    const track = el("div", (field.square ? "osw-sq-switch" : "osw-switch") + (values[field.id] ? " is-on" : ""));
    button.appendChild(track);
    button.addEventListener("click", function () { setValue(field.id, !values[field.id]); });
    return button;
  }

  function renderToggle(field) {
    const row = el("div", "osw-row" + (field.hero ? " is-hero" : "") + (values[field.id] ? " is-on" : ""));
    // The Games pages lead with artwork rather than a line icon: a tinted
    // shell holding the game's own picture, the way its widget looks in the
    // deck browser.
    if (field.heroImage) {
      row.classList.add("osw-game-hero");
      if (field.accent) {
        row.style.setProperty("--osw-game-accent", field.accent);
        row.style.setProperty("--osw-game-hover", rgba(field.accent, 0.08));
      }
      const shell = el("div", "osw-game-hero-mark");
      if (field.accent) {
        shell.style.backgroundColor = rgba(field.accent, 0.14);
        shell.style.borderColor = rgba(field.accent, 0.26);
      }
      const img = document.createElement("img");
      img.src = field.heroImage;
      img.alt = "";
      img.loading = "lazy";
      shell.appendChild(img);
      row.appendChild(shell);
    } else if (field.icon) {
      const mark = el("div", field.hero ? "osw-hero-mark" : "osw-card-icon");
      mark.innerHTML = field.icon;
      row.appendChild(mark);
    }
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    const desc = el("div", "osw-row-desc");
    if (field.descLink && field.desc && field.desc.indexOf(field.descLink.text) !== -1) {
      const parts = field.desc.split(field.descLink.text);
      desc.appendChild(document.createTextNode(parts[0]));
      const link = el("a", null, field.descLink.text);
      link.href = "#";
      link.addEventListener("click", function (event) {
        event.preventDefault();
        bridge("osw:link:" + field.descLink.href);
      });
      desc.appendChild(link);
      desc.appendChild(document.createTextNode(parts.slice(1).join(field.descLink.text)));
    } else {
      desc.textContent = field.desc || "";
    }
    text.appendChild(desc);
    row.appendChild(text);
    row.appendChild(makeSwitch(field));
    return row;
  }

  function renderModeCard(field) {
    const card = el("div", "osw-card" + (values[field.id] ? " is-on" : ""));
    if (field.icon) {
      const icon = el("div", "osw-card-icon");
      icon.innerHTML = field.icon;
      card.appendChild(icon);
    }
    const body = el("div", "osw-card-body");
    body.appendChild(el("div", "osw-card-title", field.label));
    if (field.desc) body.appendChild(el("div", "osw-card-desc", field.desc));
    const notes = (field.notes || []).filter(function (note) { return !!note; });
    if (notes.length) {
      const list = el("ul", "osw-card-notes");
      notes.forEach(function (note) { list.appendChild(el("li", null, note)); });
      body.appendChild(list);
    }
    card.appendChild(body);
    const control = makeSwitch(field);
    control.classList.add("osw-card-control");
    card.appendChild(control);
    return card;
  }

  function renderChoice(field) {
    const wrap = el("div", "osw-segmented-wrap");
    if (field.label) {
      wrap.appendChild(el("div", "osw-segmented-title", field.label));
    }
    const host = el("div", "osw-segmented-control");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "choice");

    (field.options || []).forEach(function (option) {
      const btn = el("div", "osw-segment-btn" + (option.value === values[field.id] ? " is-active" : ""));
      btn.setAttribute("role", "button");
      btn.setAttribute("tabindex", "0");
      btn.setAttribute("data-value", option.value);

      if (option.emoji) {
        btn.appendChild(el("span", "osw-segment-emoji", option.emoji));
      }
      btn.appendChild(el("span", "osw-segment-label", option.label));

      btn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        setValue(field.id, option.value);
        Array.prototype.forEach.call(host.querySelectorAll(".osw-segment-btn"), function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-value") === String(option.value));
        });
      });

      host.appendChild(btn);
    });

    wrap.appendChild(host);
    return wrap;
  }

  function renderNumber(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "number");

    const box = el("div", "osw-number");
    const input = document.createElement("input");
    input.type = "number";
    // `scale` separates the stored unit from the edited one: the reviewer
    // notification duration is milliseconds on disk (every reader expects
    // that) and seconds in the box.
    const scale = field.scale > 0 ? field.scale : 1;
    input.value = Math.round((Number(values[field.id]) || 0) / scale);
    if (field.min != null) input.min = field.min;
    if (field.max != null) input.max = field.max;
    input.step = field.step != null ? field.step : 1;
    input.addEventListener("input", function () {
      const raw = parseFloat(input.value);
      if (isNaN(raw)) return;
      let next = raw;
      if (field.min != null) next = Math.max(field.min, next);
      if (field.max != null) next = Math.min(field.max, next);
      setValue(field.id, next * scale, { keepDom: true, debounce: true });
    });
    input.addEventListener("change", function () {
      const raw = parseFloat(input.value);
      let next = isNaN(raw) ? Number(values[field.id] || 0) / scale : raw;
      if (field.min != null) next = Math.max(field.min, next);
      if (field.max != null) next = Math.min(field.max, next);
      input.value = next;
      setValue(field.id, next * scale, { keepDom: true });
    });
    box.appendChild(input);
    if (field.suffix) box.appendChild(el("span", "osw-number-suffix", field.suffix));

    // A regular numeric input remains best for exact keyboard entry. Settings
    // that opt into `stepper` also get explicit +/- targets, making small
    // adjustments easy without relying on a hidden browser spinner.
    if (field.stepper) {
      const stepper = el("div", "osw-number-stepper");
      function nudge(direction) {
        const raw = parseFloat(input.value);
        const current = isNaN(raw) ? (field.min != null ? field.min : 0) : raw;
        const increment = field.step != null ? field.step : 1;
        let next = current + (direction * increment);
        if (field.min != null) next = Math.max(field.min, next);
        if (field.max != null) next = Math.min(field.max, next);
        if (next === current) return;
        input.value = next;
        bridge("osw:haptic:1");
        setValue(field.id, next * scale, { keepDom: true });
      }

      [["−", -1, "Decrease"], ["+", 1, "Increase"]].forEach(function (spec) {
        const button = el("button", "osw-number-step", spec[0]);
        button.type = "button";
        button.setAttribute("aria-label", spec[2] + " " + field.label);
        button.addEventListener("click", function () { nudge(spec[1]); });
        stepper.appendChild(button);
      });
      box.appendChild(stepper);
    }

    if (field.resetTo != null) {
      const reset = el("button", "osw-reset");
      reset.type = "button";
      reset.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
        ' stroke-linecap="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>';
      installResetHold(reset, function () { setValue(field.id, field.resetTo); }, {
        title: str("reset_to_default", "Reset to Default")
      });
      box.appendChild(reset);
    }

    control.appendChild(box);
    row.appendChild(control);
    return row;
  }

  function renderText(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "text");
    const input = field.multiline ? document.createElement("textarea") : document.createElement("input");
    if (!field.multiline) input.type = "text";
    input.className = field.multiline ? "osw-textarea-input" : "osw-text-input";
    input.value = values[field.id] == null ? "" : values[field.id];
    if (field.placeholder) input.placeholder = field.placeholder;
    if (field.maxLength != null) input.maxLength = field.maxLength;
    input.addEventListener("input", function () {
      let next = input.value;
      const blankToken = String(field.blankToken || "");
      // The avatar's explicit blank marker needs all three dots to reach the
      // stored value. Let its partial input through rather than clipping the
      // second dot under the usual one-grapheme limit.
      if (blankToken && blankToken.indexOf(next) === 0) {
        if (next === blankToken) {
          toast(str("profile_avatar_blank_notice", "Avatar content hidden"));
        }
        setValue(field.id, next, { keepDom: true, debounce: true });
        return;
      }
      if (field.maxGraphemes != null) {
        const limit = Math.max(0, Number(field.maxGraphemes) || 0);
        if (typeof Intl !== "undefined" && Intl.Segmenter) {
          next = Array.from(new Intl.Segmenter().segment(next))
            .slice(0, limit)
            .map(function (segment) { return segment.segment; })
            .join("");
        } else {
          next = Array.from(next).slice(0, limit).join("");
        }
        if (input.value !== next) input.value = next;
      }
      setValue(field.id, next, { keepDom: true, debounce: true });
    });
    control.appendChild(input);
    row.appendChild(control);
    return row;
  }

  function renderSelect(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "select");

    if (field.controlStyle === "modern") {
      const picker = el("div", "osw-select-menu");
      const trigger = el("button", "osw-select-menu-trigger");
      trigger.type = "button";
      trigger.setAttribute("aria-haspopup", "listbox");
      trigger.setAttribute("aria-expanded", "false");
      const selected = (field.options || []).filter(function (opt) { return opt.value === values[field.id]; })[0] || (field.options || [])[0] || {};
      trigger.appendChild(el("span", "osw-select-menu-value", selected.label || ""));
      trigger.appendChild(el("span", "osw-select-menu-chevron"));
      const list = el("div", "osw-select-menu-list");
      list.setAttribute("role", "listbox");
      control.__selectList = list;
      const floating = field.id === "pomodoro_start_sound" || field.id === "pomodoro_end_sound";
      let detachObserver = null;

      function positionList() {
        if (!trigger.isConnected) { close(); return; }
        const rect = trigger.getBoundingClientRect();
        const margin = 10;
        const gap = 6;
        const below = Math.max(0, window.innerHeight - rect.bottom - gap - margin);
        const above = Math.max(0, rect.top - gap - margin);
        // Prefer the usual downward menu unless it would crop the options.
        // Unlike the scrolling page, this body-level popup is not masked by
        // its bottom fade or clipped by the page's overflow boundary.
        list.style.maxHeight = "none";
        const width = Math.min(rect.width, window.innerWidth - 2 * margin);
        list.style.width = Math.max(0, width) + "px";
        const naturalHeight = list.scrollHeight + 2;
        const upward = below < naturalHeight && above > below;
        list.style.maxHeight = (upward ? above : below) + "px";
        const height = list.getBoundingClientRect().height;
        list.style.left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin)) + "px";
        list.style.top = Math.max(margin, upward ? rect.top - gap - height : rect.bottom + gap) + "px";
      }

      function onScroll(event) {
        // The menu itself can scroll in very short windows. Scrolling the
        // underlying page closes it so it cannot float away from its trigger.
        if (!list.contains(event.target)) close();
      }

      function onKeydown(event) {
        if (event.key === "Escape") {
          close();
          trigger.focus();
        }
      }

      // Designer-deck rows normally clip their contents so conditional rows
      // can collapse cleanly. A custom select's list is intentionally outside
      // the row, though; let this one row escape while its menu is open.
      function setOpen(open) {
        if (floating && open) {
          document.querySelectorAll(".osw-select-menu-list.is-floating").forEach(function (other) {
            if (other !== list && other.__closePicker) other.__closePicker();
          });
        }
        picker.classList.toggle("is-open", open);
        trigger.setAttribute("aria-expanded", open ? "true" : "false");
        const fieldHost = control.closest("[data-field-host]");
        if (fieldHost) fieldHost.classList.toggle("has-open-select", open);
        if (floating) {
          if (open) {
            list.classList.add("is-floating");
            document.body.appendChild(list);
            positionList();
            window.addEventListener("resize", positionList);
            window.addEventListener("scroll", onScroll, true);
            document.addEventListener("keydown", onKeydown);
            // Page rebuilds can remove a picker without a click or scroll.
            detachObserver = new MutationObserver(function () {
              if (!trigger.isConnected) close();
            });
            detachObserver.observe(document.body, { childList: true, subtree: true });
            const active = list.querySelector(".is-active");
            if (active) list.scrollTop = Math.max(0, active.offsetTop - list.clientHeight / 2);
          } else {
            if (detachObserver) detachObserver.disconnect();
            detachObserver = null;
            window.removeEventListener("resize", positionList);
            window.removeEventListener("scroll", onScroll, true);
            document.removeEventListener("keydown", onKeydown);
            list.classList.remove("is-floating");
            list.removeAttribute("style");
            picker.appendChild(list);
          }
        }
      }

      function close() {
        setOpen(false);
      }
      list.__closePicker = close;
      trigger.addEventListener("click", function (event) {
        event.stopPropagation();
        setOpen(!picker.classList.contains("is-open"));
      });
      (field.options || []).forEach(function (opt) {
        const option = el("button", "osw-select-menu-option" + (opt.value === values[field.id] ? " is-active" : ""), opt.label);
        option.type = "button";
        option.setAttribute("role", "option");
        option.setAttribute("data-value", opt.value);
        option.setAttribute("data-label", opt.label);
        option.setAttribute("aria-selected", opt.value === values[field.id] ? "true" : "false");
        option.addEventListener("click", function () {
          bridge("osw:haptic:1");
          close();
          setValue(field.id, opt.value);
        });
        list.appendChild(option);
      });
      picker.appendChild(trigger);
      picker.appendChild(list);
      document.addEventListener("click", close);
      control.appendChild(picker);
      row.appendChild(control);
      return row;
    }

    const selectNode = document.createElement("select");
    selectNode.className = "osw-select-input" + (field.controlStyle === "modern" ? " osw-select-modern" : "");
    (field.options || []).forEach(function (opt) {
      const optionNode = document.createElement("option");
      optionNode.value = opt.value;
      optionNode.textContent = opt.label;
      if (opt.value === values[field.id]) optionNode.selected = true;
      selectNode.appendChild(optionNode);
    });
    selectNode.addEventListener("change", function () {
      setValue(field.id, selectNode.value);
    });
    control.appendChild(selectNode);
    row.appendChild(control);
    return row;
  }

  /* Contrast text colour for values drawn on a colour surface elsewhere in
     Settings previews. */
  function readableTextColor(hex) {
    const h = String(hex || "").replace("#", "");
    const full = h.length === 3 ? h.split("").map(function (c) { return c + c; }).join("") : h;
    if (full.length !== 6) return "#1f2124";
    const r = parseInt(full.substr(0, 2), 16);
    const g = parseInt(full.substr(2, 2), 16);
    const b = parseInt(full.substr(4, 2), 16);
    const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
    return luminance > 150 ? "#1f2124" : "#ffffff";
  }

  function renderColor(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "color");
    if (field.controlStyle === "designer_color_slot") {
      const fallback = (CTX.dark ? values[field.fallbackDark] : values[field.fallbackLight]) ||
        values[field.fallbackLight] || values[field.fallbackDark] || "";
      const value = values[field.id] || field.default || "";
      const shown = value || fallback;
      const isDefault = !value && !!fallback;
      const slot = el("button", "osw-imgslot osw-colorslot osw-ready-color-slot" +
        (isDefault ? " is-default" : ""));
      slot.type = "button";
      slot.setAttribute("aria-label", field.label || str("color", "Color"));
      const swatch = el("span", "osw-imgslot-thumb is-swatch");
      swatch.style.background = shown || "transparent";
      slot.appendChild(swatch);
      const meta = el("span", "osw-imgslot-meta");
      meta.appendChild(el("span", "osw-imgslot-name",
        shown ? String(shown).toUpperCase() : "Transparent"));
      slot.appendChild(meta);
      slot.addEventListener("click", function () {
        bridge("osw:haptic:1");
        openColorPicker(field, shown, field.default);
      });
      control.appendChild(slot);
      row.appendChild(control);
      return row;
    }
    const chip = el("button", "osw-chip osw-chip-color");
    chip.type = "button";
    const swatch = el("span", "osw-chip-swatch");
    swatch.style.background = values[field.id] || field.default || "transparent";
    chip.appendChild(swatch);
    chip.appendChild(el("span", "osw-chip-hex", String(values[field.id] || field.default || "").toUpperCase()));
    chip.addEventListener("click", function () {
      bridge("osw:haptic:1");
      openColorPicker(field, values[field.id] || field.default || "", field.default);
    });
    control.appendChild(chip);
    row.appendChild(control);
    return row;
  }

  function renderFont(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "font");
    const chip = el("button", "osw-chip");
    chip.type = "button";
    const option = (field.options || []).filter(function (o) { return o.value === values[field.id]; })[0];
    const label = el("span", "osw-chip-label", option ? option.label : values[field.id]);
    if (option && option.family) label.style.fontFamily = option.family;
    chip.appendChild(label);
    chip.addEventListener("click", function () {
      openFontPicker(field);
    });
    control.appendChild(chip);
    row.appendChild(control);
    return row;
  }

  function renderIcon(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "icon");
    // The icon itself, not its filename: "system:pomodoro.svg" tells the user
    // nothing the glyph does not tell them faster.
    const chip = el("button", "osw-chip osw-icon-chip");
    chip.type = "button";
    const preview = el("span", "osw-icon-chip-preview");
    function paintPreview() {
      // Empty means "the bundled default", not "no icon" — see iconValue().
      const raw = String(iconValue(field.id) || "");
      preview.innerHTML = "";
      preview.classList.remove("is-emoji", "is-empty");
      if (raw.indexOf("emoji:") === 0) {
        preview.classList.add("is-emoji");
        preview.textContent = raw.slice(6);
        return;
      }
      const url = resolveIconAssetUrl(raw);
      if (url) {
        preview.style.webkitMaskImage = "url('" + url + "')";
        preview.style.maskImage = "url('" + url + "')";
      } else {
        // No mask-image at all (not url('') — an empty/invalid mask reference
        // makes some engines render the element fully unmasked, i.e. a solid
        // currentColor square) reads as a real icon that failed to load.
        // is-empty drops the background entirely instead.
        preview.style.webkitMaskImage = "";
        preview.style.maskImage = "";
        preview.classList.add("is-empty");
        preview.textContent = "—";
      }
    }
    paintPreview();
    chip.__syncIconChip = paintPreview;
    chip.appendChild(preview);
    chip.addEventListener("click", function () {
      bridge("osw:haptic:1");
      openIconPicker(field);
    });
    control.appendChild(chip);
    row.appendChild(control);
    return row;
  }

  /* Languages gets its own renderer rather than reusing the generic choice grid.
     A language is picked by recognising its script, so each card leads with a
     greeting in that script, and the hero panel shows what the UI will actually
     read like. Hovering a card previews it in the hero; leaving snaps back to
     the selected one.

     Two rules keep the hover preview from flickering, and both matter:

     1. Every language renders the SAME structure, so the hero's height never
        changes. It used to drop the footer row for a fully translated language,
        which made the hero shrink on hover, which moved the grid up, which slid
        the card out from under the cursor, which fired mouseleave, which put the
        row back — a layout feedback loop that oscillated for as long as the
        pointer sat near a card edge.
     2. The hero is built once and then updated in place. Rebuilding it with
        innerHTML on every mouseenter flashed the whole panel even when the
        resulting size was identical. */
  function renderLanguage(field) {
    const host = el("div", "osw-lang");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "language");

    const options = field.options || [];
    const optionFor = function (value) {
      return options.filter(function (o) { return o.value === value; })[0] || options[0];
    };
    // Fixed number of preview slots across every language, for the same reason.
    const slotCount = options.reduce(function (most, option) {
      return Math.max(most, (option.preview || []).length);
    }, 0);

    // ── hero skeleton, built exactly once ──
    const hero = el("div", "osw-lang-hero");
    const ref = {};

    const top = el("div", "osw-lang-hero-top");
    ref.flag = el("div", "osw-lang-hero-flag");
    top.appendChild(ref.flag);
    const titles = el("div", "osw-lang-hero-titles");
    ref.greeting = el("div", "osw-lang-hero-greeting");
    ref.name = el("div", "osw-lang-hero-name");
    titles.appendChild(ref.greeting);
    titles.appendChild(ref.name);
    top.appendChild(titles);
    ref.badge = el("div", "osw-lang-badge");
    top.appendChild(ref.badge);
    hero.appendChild(top);

    ref.slots = [];
    if (slotCount) {
      const preview = el("div", "osw-lang-preview");
      preview.appendChild(el("div", "osw-lang-preview-title", str("lang_preview", "Preview")));
      const list = el("div", "osw-lang-preview-list");
      for (let i = 0; i < slotCount; i += 1) {
        const row = el("div", "osw-lang-pair");
        const from = el("span", "osw-lang-pair-from");
        const to = el("span", "osw-lang-pair-to");
        row.appendChild(from);
        row.appendChild(el("span", "osw-lang-pair-arrow", "→"));
        row.appendChild(to);
        list.appendChild(row);
        ref.slots.push({ row: row, from: from, to: to });
      }
      preview.appendChild(list);
      hero.appendChild(preview);
    }

    host.appendChild(hero);

    function paintHero(option) {
      if (!option) return;
      const isActive = option.value === values[field.id];
      hero.classList.toggle("is-peek", !isActive);

      ref.flag.textContent = option.emoji;
      ref.greeting.textContent = option.greeting || option.label;
      ref.name.textContent = option.label + " · " + option.sub;
      ref.badge.textContent = isActive
        ? str("lang_active", "Active")
        : (option.code || "").toUpperCase();
      ref.badge.classList.toggle("is-active", isActive);

      const pairs = option.preview || [];
      ref.slots.forEach(function (slot, index) {
        const pair = pairs[index];
        if (!pair) {
          // Keep the row occupying its space; never remove it.
          slot.row.style.visibility = "hidden";
          slot.from.textContent = "";
          slot.to.textContent = "";
          return;
        }
        slot.row.style.visibility = "";
        slot.from.textContent = pair.from;
        slot.to.textContent = pair.to;
        slot.row.classList.toggle("is-missing", !!pair.missing);
      });
    }

    const grid = el("div", "osw-lang-grid");
    options.forEach(function (option) {
      const card = el("button", "osw-lang-card");
      card.type = "button";
      card.setAttribute("data-value", option.value);

      const head = el("div", "osw-lang-card-head");
      head.appendChild(el("span", "osw-lang-card-flag", option.emoji));
      head.appendChild(el("span", "osw-lang-card-code", (option.code || "").toUpperCase()));
      card.appendChild(head);

      card.appendChild(el("div", "osw-lang-card-greeting", option.greeting || option.label));
      card.appendChild(el("div", "osw-lang-card-name", option.label));

      card.addEventListener("click", function () { setValue(field.id, option.value); });
      card.addEventListener("mouseenter", function () { paintHero(option); });
      card.addEventListener("focus", function () { paintHero(option); });
      grid.appendChild(card);
    });

    /* Reverting to the selected language is the GRID's job, not each card's.
       Per-card mouseleave/blur fired the moment the pointer crossed the gap
       between two neighbours, so dragging from Português to 简体中文 flashed the
       selected language's text in between. Listening on the container means the
       gap is still "inside", and the hero only snaps back when the pointer or
       focus actually leaves the picker. */
    const revert = function () { paintHero(optionFor(values[field.id])); };
    grid.addEventListener("mouseleave", revert);
    grid.addEventListener("focusout", function (event) {
      // relatedTarget is what is gaining focus; staying within the grid is a
      // move between cards, not a departure.
      if (!grid.contains(event.relatedTarget)) revert();
    });

    host.appendChild(grid);

    host.__paintHero = function () { paintHero(optionFor(values[field.id])); };
    host.__paintHero();
    markSelected(host, values[field.id]);
    return host;
  }

  function markSelected(host, value) {
    Array.prototype.forEach.call(host.querySelectorAll(".osw-lang-card"), function (card) {
      card.classList.toggle("is-selected", card.getAttribute("data-value") === String(value));
    });
  }

  function fmt(template, map) {
    return String(template).replace(/\{(\w+)\}/g, function (whole, key) {
      return key in map ? String(map[key]) : whole;
    });
  }

  function num(value) {
    return Number(value || 0).toLocaleString();
  }

  function renderNote(field) {
    if (field.layout === "grid") {
      const grid = el("div", "osw-note-grid");
      (field.items || []).forEach(function (item) {
        grid.appendChild(el("div", "osw-note", item));
      });
      return grid;
    }
    // A toned note is a status banner rather than a caption: the Onigimon page
    // uses it to report whether Ankimon is installed at all.
    const note = el("div", "osw-note" + (field.tone ? " osw-note-tone is-" + field.tone : ""));
    if (field.tone) note.appendChild(el("span", "osw-note-dot"));
    const body = field.tone ? el("div", "osw-note-body") : note;
    const label = el("div", "osw-note-label", field.label || "");
    const desc = el("div", "osw-note-desc", field.desc || "");
    if (field.label || field.contextKey) body.appendChild(label);
    if (field.desc || field.contextKey) body.appendChild(desc);
    if (field.tone) note.appendChild(body);
    // A note whose text is live state (Ankimon's install status) is filled in
    // when that state arrives rather than at build time — see ensureGamesContext.
    if (field.contextKey) {
      note.classList.add("osw-note-live");
      note.__syncNote = function () {
        const data = gamesCtx[field.contextKey] || {};
        label.textContent = data.title || "";
        desc.textContent = data.detail || "";
        if (data.state) {
          note.classList.remove("is-ok", "is-warn", "is-error");
          note.classList.add("is-" + data.state);
        }
        note.style.display = data.title ? "" : "none";
      };
      note.__syncNote();
    }
    return note;
  }

  const ACTION_ICONS = {
    import: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    reset: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
    sync: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-15 6.7M3 12a9 9 0 0 1 15-6.7"/><path d="M21 4v5h-5M3 20v-5h5"/></svg>',
    open: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
    play: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M8 5.6v12.8a1 1 0 0 0 1.52.85l10.2-6.4a1 1 0 0 0 0-1.7l-10.2-6.4A1 1 0 0 0 8 5.6z"/></svg>',
    coin: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="M12 8v8M9.5 10a2.5 2.5 0 0 1 5 0c0 2.6-5 1.4-5 4a2.5 2.5 0 0 0 5 0"/></svg>'
  };

  function renderAction(field) {
    const row = el("div", "osw-row");
    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    const control = el("div", "osw-row-control");
    const button = el("button", "osw-action-btn" + (field.danger ? " is-danger" : "") +
      (field.neutral ? " is-neutral" : ""));
    button.type = "button";

    const iconSpan = el("span", "osw-action-btn-icon");
    // The import arrow is the default because most actions import something;
    // a button that resets or opens says so with its own glyph instead.
    iconSpan.innerHTML = ACTION_ICONS[field.buttonIcon] || ACTION_ICONS.import;
    button.appendChild(iconSpan);

    const labelText = field.buttonLabel || field.button_label || str("import_button", "Import");
    button.appendChild(el("span", "osw-action-btn-label", labelText));

    function invokeAction() {
      if (!field.action || button.classList.contains("is-busy")) return;
      button.classList.add("is-busy");
      // Answered rather than fired blind: a Games action can hand back fresh
      // state (the island balance after buying the Keys) that the page shows.
      let command = "osw:" + field.action;
      // Tone previews must use the visible selection even before the
      // debounced auto-save has reached Python. This does not save any edits.
      if (field.action === "pomodoro_test_start_sound" ||
          field.action === "pomodoro_test_end_sound") {
        command += ":" + JSON.stringify({
          start_sound: values.pomodoro_start_sound,
          end_sound: values.pomodoro_end_sound,
          sound_file: values.pomodoro_sound_file
        });
      }
      call(command).then(function (reply) {
        button.classList.remove("is-busy", "is-ready");
        applyActionReply(reply);
        if (reply && reply.reload) {
          ensureGamesContext();
        }
      }).catch(function () {
        button.classList.remove("is-busy", "is-ready");
        toast(str("games_action_failed", "Could not complete that action."));
      });
    }

    if (field.holdToConfirm) {
      installResetHold(button, invokeAction, {
        title: str("hold_to_confirm", "Hold for 3 seconds to continue")
      });
    } else {
      button.addEventListener("click", invokeAction);
    }
    control.appendChild(button);
    row.appendChild(control);
    return row;
  }

  /* State a bridge action reports back. Kept in one place so every caller —
     the generic action row, the Keys button, the companion grid — refreshes
     the same way. */
  function applyActionReply(res) {
    if (!res) return;
    if (res.hexagon) {
      gamesCtx.hexagon = res.hexagon;
      refreshHexagonCards();
    }
    if (res.error) toast(res.error);
  }

  function renderSlider(field) {
    const min = field.min != null ? field.min : 0;
    const max = field.max != null ? field.max : 100;
    const step = field.step != null ? field.step : 1;
    // An alpha slider has no stored value of its own — it reads the opacity out
    // of the colour it edits, so it is always in step with that colour however
    // it was last changed.
    if (field.alphaOf) values[field.id] = chipAlphaPercent(field);
    const currentVal = values[field.id] != null ? values[field.id] : (field.default != null ? field.default : min);

    const card = el("div", "osw-slider-card");
    card.setAttribute("data-field", field.id);
    card.setAttribute("data-field-type", "slider");

    const header = el("div", "osw-slider-header");
    const title = el("div", "osw-slider-title", field.label);
    const valueBadge = el("div", "osw-slider-value", currentVal + (field.suffix || ""));
    header.appendChild(title);
    header.appendChild(valueBadge);
    card.appendChild(header);

    const track = el("div", "osw-slider-track");
    const fill = el("div", "osw-slider-fill");
    const thumb = el("div", "osw-slider-thumb");

    track.appendChild(fill);
    track.appendChild(thumb);
    card.appendChild(track);

    // The fill keeps a small visible tip even at 0% instead of vanishing
    // outright. The thumb is a constant-size pill handle, clamped so it
    // always stays fully inside the track.
    function paint(pct) {
      fill.style.width = pct + "%";
      thumb.style.left = "max(6px, min(calc(" + pct + "% - 10px), calc(100% - 11px)))";
    }

    const pct = Math.max(0, Math.min(100, ((currentVal - min) / (max - min)) * 100));
    paint(pct);

    let isDragging = false;
    let lastHapticVal = currentVal;

    function updateFromClientX(clientX) {
      const rect = track.getBoundingClientRect();
      if (rect.width <= 0) return;
      let ratio = (clientX - rect.left) / rect.width;
      ratio = Math.max(0, Math.min(1, ratio));
      let rawVal = min + ratio * (max - min);
      let stepped = Math.round((rawVal - min) / step) * step + min;
      stepped = Math.max(min, Math.min(max, stepped));

      if (stepped !== lastHapticVal) {
        lastHapticVal = stepped;
        bridge("osw:haptic:2");
      }

      if (field.alphaOf) setChipAlpha(field, stepped);
      else setValue(field.id, stepped, { keepDom: true, debounce: true });

      const newPct = ((stepped - min) / (max - min)) * 100;
      paint(newPct);
      valueBadge.textContent = stepped + (field.suffix || "");
    }

    function onPointerDown(e) {
      isDragging = true;
      card.classList.add("is-dragging");
      updateFromClientX(e.clientX);
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    }

    function onPointerMove(e) {
      if (!isDragging) return;
      updateFromClientX(e.clientX);
    }

    function onPointerUp(e) {
      if (!isDragging) return;
      isDragging = false;
      card.classList.remove("is-dragging");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    track.addEventListener("pointerdown", onPointerDown);

    // An alpha slider's value lives inside another field's colour, so it has to
    // be repainted whenever that colour — or the theme deciding which colour it
    // is — changes. Kept off syncField: the preview painter is what notices, and
    // syncField repaints previews, which would loop.
    if (field.alphaOf) {
      card.__syncAlpha = function () {
        const next = chipAlphaPercent(field);
        values[field.id] = next;
        paint(Math.max(0, Math.min(100, ((next - min) / (max - min)) * 100)));
        valueBadge.textContent = next + (field.suffix || "");
      };
    }

    return card;
  }

  function refreshAlphaSliders() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-slider-card"), function (node) {
      if (node.__syncAlpha) node.__syncAlpha();
    });
  }

  /* A duration stored in seconds, edited as "amount + unit": the slider moves
     within the chosen unit's own range, the unit chips convert. The unit is
     derived from the stored value (300s reads as 5 minutes), so nothing new
     has to be persisted alongside it. */
  const DURATION_UNITS = [
    { id: "s", factor: 1, max: 60, key: "seconds", fallback: "Seconds" },
    { id: "m", factor: 60, max: 60, key: "minutes", fallback: "Minutes" },
    { id: "h", factor: 3600, max: 24, key: "hours", fallback: "Hours" },
  ];

  function durationUnitFor(seconds) {
    const value = Number(seconds) || 0;
    for (let i = DURATION_UNITS.length - 1; i > 0; i--) {
      const unit = DURATION_UNITS[i];
      if (value >= unit.factor && value % unit.factor === 0) return unit;
    }
    return DURATION_UNITS[0];
  }

  function renderDuration(field) {
    const row = el("div", "osw-row osw-duration");
    row.setAttribute("data-field", field.id);
    row.setAttribute("data-field-type", "duration");

    const text = el("div", "osw-row-text");
    text.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) text.appendChild(el("div", "osw-row-desc", field.desc));
    row.appendChild(text);

    function seconds() {
      const raw = Number(values[field.id]);
      return raw > 0 ? raw : (Number(field.default) || 1);
    }

    const control = el("div", "osw-row-control osw-duration-control");

    const amountInput = document.createElement("input");
    amountInput.type = "number";
    amountInput.className = "osw-duration-amount";
    amountInput.min = "1";
    amountInput.inputMode = "numeric";

    const unitSelect = document.createElement("select");
    unitSelect.className = "osw-select-input osw-duration-unit-select";
    DURATION_UNITS.forEach(function (candidate) {
      const opt = document.createElement("option");
      opt.value = candidate.id;
      opt.textContent = str(candidate.key, candidate.fallback);
      unitSelect.appendChild(opt);
    });

    function amountFor(unit) {
      return Math.max(1, Math.min(unit.max, Math.round(seconds() / unit.factor)));
    }

    function sync() {
      const unit = durationUnitFor(seconds());
      unitSelect.value = unit.id;
      amountInput.max = String(unit.max);
      amountInput.value = String(amountFor(unit));
    }
    sync();

    function currentUnit() {
      return DURATION_UNITS.filter(function (u) { return u.id === unitSelect.value; })[0] || DURATION_UNITS[0];
    }

    amountInput.addEventListener("input", function () {
      const unit = currentUnit();
      let amount = Math.round(Number(amountInput.value));
      if (!isFinite(amount) || amount < 1) amount = 1;
      amount = Math.min(unit.max, amount);
      setValue(field.id, amount * unit.factor, { keepDom: true, debounce: true });
    });

    unitSelect.addEventListener("change", function () {
      bridge("osw:haptic:1");
      const unit = currentUnit();
      // The number stays put, the unit under it changes: 5 seconds becomes
      // 5 minutes, which is what "switch to minutes" reads as.
      let amount = Math.round(Number(amountInput.value));
      if (!isFinite(amount) || amount < 1) amount = 1;
      amount = Math.min(unit.max, amount);
      amountInput.max = String(unit.max);
      amountInput.value = String(amount);
      setValue(field.id, amount * unit.factor, { keepDom: true });
    });

    control.appendChild(amountInput);
    control.appendChild(unitSelect);
    row.appendChild(control);
    return row;
  }

  let currentProfilePreviewMode = CTX.dark ? "dark" : "light";
  let activeProfileTab = "picture";
  let profileContextInFlight = false;

  function applyProfileContext(snapshot) {
    if (!snapshot || !snapshot.profileLevel) return;
    const changed = ["profileLevel", "chipColors", "chipDefaults"].some(function (key) {
      return JSON.stringify(CTX[key]) !== JSON.stringify(snapshot[key]);
    });
    if (!changed) return;
    profileContextRevision += 1;
    CTX.profileLevel = snapshot.profileLevel;
    CTX.chipColors = snapshot.chipColors;
    CTX.chipDefaults = snapshot.chipDefaults;
    updateProfilePreview();
    updateDesignerPreviews();
  }

  function refreshLiveProfileContext() {
    // Only open profile previews need a fresh progress snapshot. Polling is
    // read-only and never rebuilds Anki or replaces an edit still being saved.
    if (document.hidden || !document.querySelector(".osw-profile-preview-item") ||
        profileContextInFlight || inFlight || Object.keys(pending).length) return;
    profileContextInFlight = true;
    const revision = profileContextRevision;
    call("osw:profile_context:").then(function (snapshot) {
      profileContextInFlight = false;
      if (revision === profileContextRevision && !inFlight && !Object.keys(pending).length) applyProfileContext(snapshot);
    }, function () { profileContextInFlight = false; });
  }

  // The profile used to expose one "Dynamic mode" toggle per asset. The UI now
  // shows a single one; these stay as the storage so existing readers of each
  // key keep working. Off means "any of them is off".
  const PROFILE_DYNAMIC_KEYS = [
    "modern_menu_profile_picture_dynamic_mode",
    "modern_menu_profile_bg_dynamic_mode",
    "modern_menu_profile_name_dynamic_mode",
    "modern_menu_profile_fill_dynamic_mode",
  ];

  /* Simple mode intentionally keeps the profile to one calm, reliable
     presentation. Advanced retains the full set of layout, avatar and
     light/dark controls. These are applied when entering Simple mode so the
     sidebar itself always agrees with the simplified settings surface. */
  const SIMPLE_PROFILE_VALUES = {
    modern_menu_profile_type: "ring",
    modern_menu_profile_picture_mode: "custom",
  };

  function simpleProfileModeActive() {
    return settingsComplexity === "simple";
  }

  function syncSimpleProfileControls() {
    const simple = simpleProfileModeActive();

    Array.prototype.forEach.call(
      document.querySelectorAll(
        "[data-simple-profile-dynamic], " +
        "[data-simple-profile-style], " +
        "[data-simple-profile-advanced], " +
        '[data-field-host="modern_menu_profile_picture_mode"]'
      ),
      function (control) {
        control.classList.toggle("osw-simple-profile-hidden", simple);
        control.setAttribute("aria-hidden", simple ? "true" : "false");
      }
    );
  }

  function applySimpleProfileDefaults() {
    if (!simpleProfileModeActive()) {
      syncSimpleProfileControls();
      return;
    }

    Object.keys(SIMPLE_PROFILE_VALUES).forEach(function (id) {
      setValue(id, SIMPLE_PROFILE_VALUES[id], { silent: true, keepDom: true });
    });
    PROFILE_DYNAMIC_KEYS.forEach(function (id) {
      setValue(id, true, { silent: true, keepDom: true });
    });
    syncProfileLevelDynamicMode(true);
    Array.prototype.forEach.call(
      document.querySelectorAll(".osw-profile-page-wrap"),
      function (profileWrap) {
        if (profileWrap.__syncProfileTabs) profileWrap.__syncProfileTabs("ring");
      }
    );
    syncSimpleProfileControls();
  }

  /* Simple Sync has one policy: copy every supported category. Keep the
     concrete flags aligned with the preset because the sync backend reads the
     categories themselves when it builds an archive. */
  const SIMPLE_SYNC_VALUES = {
    ankiweb_sync_preset: "everything",
    ankiweb_sync_theme: true,
    ankiweb_sync_profile: true,
    ankiweb_sync_games: true,
    ankiweb_sync_study_tools: true,
    ankiweb_sync_assets: true,
    ankiweb_sync_layout: true,
  };

  function applySimpleSyncDefaults() {
    if (settingsComplexity !== "simple") return;
    Object.keys(SIMPLE_SYNC_VALUES).forEach(function (id) {
      setValue(id, SIMPLE_SYNC_VALUES[id], { silent: true });
    });
  }

  function profileDynamicOn() {
    return PROFILE_DYNAMIC_KEYS.every(function (key) { return values[key] !== false; });
  }

  function profileAccentColor(isDark) {
    const key = isDark ? "theme_accent_dark" : "theme_accent_light";
    return values[key] || CTX.accent || "#00A982";
  }

  let syncingProfilePictureAccent = false;

  function syncProfilePictureAccentColors() {
    if (syncingProfilePictureAccent) return;
    syncingProfilePictureAccent = true;
    setValue(
      "modern_menu_profile_picture_color_light",
      profileAccentColor(false),
      { silent: true, keepDom: true }
    );
    setValue(
      "modern_menu_profile_picture_color_dark",
      profileAccentColor(true),
      { silent: true, keepDom: true }
    );
    syncingProfilePictureAccent = false;
  }

  function syncProfileLevelDynamicMode(next) {
    if (!("g_rl_dynamic_chip_colors" in values)) return;
    const wanted = next == null ? profileDynamicOn() : !!next;
    if (values.g_rl_dynamic_chip_colors === wanted) return;
    // This is a hidden compatibility value, not a second user-facing control.
    setValue("g_rl_dynamic_chip_colors", wanted, { silent: true, keepDom: true });
  }

  function profileLevelGameEnabled() {
    return !!(values.g_nook_enabled || values.g_onigimon_enabled || values.g_hexagon_enabled);
  }

  /* Ring Color is only a fallback. An active Profile Level source uses the
     shared Profile Level progress color. */
  function selectedProfileLevelGameEnabled() {
    const game = values.g_profile_level_game || "nook";
    if (game === "onigimon") return values.g_onigimon_enabled === true;
    if (game === "hexagon") return values.g_hexagon_enabled === true;
    return values.g_nook_enabled === true && values.g_nook_profile_bar !== false;
  }

  function refreshProfileLevelLinks() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-profile-level-link-wrap"), function (node) {
      if (node.__syncProfileLevelLink) node.__syncProfileLevelLink();
    });
  }

  const OSW_MOON_ICON = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg>';
  const OSW_SUN_ICON = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
  const OSW_RESET_ICON = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9a9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>';

  // Every reset uses the same deliberate hold as "Reset to default" in the
  // Themes panel. The progress wash is CSS-driven by .is-holding; the
  // action is allowed only when the user releases after the full 3 seconds.
  function installResetHold(button, action, options) {
    const opts = options || {};
    const title = opts.title || str("reset_to_default", "Reset to Default");
    button.classList.add("osw-profile-reset-btn");
    button.title = title;
    if (!button.getAttribute("aria-label")) button.setAttribute("aria-label", title);

    let holdTimer = null;
    let isReady = false;
    let isHolding = false;

    function stopEvent(event) {
      if (event) {
        event.preventDefault();
        if (opts.stopPropagation !== false) event.stopPropagation();
      }
    }

    function cancelHold() {
      if (holdTimer) clearTimeout(holdTimer);
      holdTimer = null;
      isHolding = false;
      isReady = false;
      button.classList.remove("is-holding", "is-ready");
    }

    function startHold(event) {
      if (event && event.button !== undefined && event.button !== 0) return;
      if (button.disabled || isHolding) return;
      stopEvent(event);
      isHolding = true;
      isReady = false;
      button.classList.remove("is-ready");
      button.classList.add("is-holding");
      holdTimer = setTimeout(function () {
        holdTimer = null;
        if (!isHolding) return;
        isReady = true;
        button.classList.add("is-ready");
        bridge("osw:haptic:1");
      }, 3000);
    }

    function endHold(event) {
      if (event && event.button !== undefined && event.button !== 0) return;
      if (!isHolding) return;
      stopEvent(event);
      const shouldReset = isReady;
      cancelHold();
      if (!shouldReset) return;
      bridge("osw:haptic:2");
      action(event);
    }

    // Prevent the browser's synthetic click after mouseup/touchend from
    // bypassing the release gate. Keyboard activation follows the same rule.
    button.addEventListener("click", stopEvent);
    button.addEventListener("mousedown", startHold);
    button.addEventListener("mouseup", endHold);
    button.addEventListener("mouseleave", cancelHold);
    button.addEventListener("touchstart", startHold, { passive: false });
    button.addEventListener("touchend", endHold);
    button.addEventListener("touchcancel", cancelHold);
    button.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      startHold(event);
    });
    button.addEventListener("keyup", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      endHold(event);
    });
  }

  function renderProfilePreview(section, page) {
    // Outer wrapper carries no chrome of its own: the preview is the only
    // boxed container, the controls below it sit flat on the page.
    const wrap = el("div", "osw-profile-page-wrap");

    const container = el("div", "osw-profile-preview-card");
    container.id = "oswProfilePreviewCard";
    wrap.appendChild(container);

    // 1. Header
    const head = el("div", "osw-profile-preview-head");
    const headText = el("div", "osw-profile-preview-title-group");
    headText.appendChild(el("div", "osw-profile-preview-title", str("preview", "Preview")));
    head.appendChild(headText);

    // Assigned once the tab strip exists further down; the Profile Style
    // control below has to call it before that point in source order.
    let syncProfileTabs = function () {};

    function resetProfileSettings() {
      const profileSecIds = [
        "profile_picture_appearance", "profile_bg_appearance",
        "profile_name_appearance", "profile_fill_appearance",
        "profile_info", "profile_panel_toggles", "profile_type_section",
        "profile_page_background"
      ];
      (page.sections || []).forEach(function (section) {
        if (profileSecIds.indexOf(section.id) === -1) return;
        (section.fields || []).forEach(function (field) {
          if (!field.bound || field.virtual || field.default === undefined) return;
          const defaultValue = field.default && typeof field.default === "object"
            ? JSON.parse(JSON.stringify(field.default))
            : field.default;
          setValue(field.id, defaultValue, { silent: true, skipCascade: true });
        });
      });
      applySimpleProfileDefaults();
      syncProfileTabs();
      refreshFontPreviews();
      refreshImageFields();
      refreshIconChips();
      refreshPairFields();
      updateProfilePreview();
      updateProfileVisibility();
    }

    const headControls = el("div", "osw-preview-head-controls");

    // One Dynamic mode switch replaces the four per-asset flags that used to
    // sit in the Picture / Background / Colors tabs. It still writes all four
    // keys, so every renderer reading them keeps working unchanged.
    const dynCtl = el(
      "div",
      "osw-preview-ctl" + (simpleProfileModeActive() ? " osw-simple-profile-hidden" : "")
    );
    dynCtl.setAttribute("data-simple-profile-dynamic", "true");
    dynCtl.appendChild(el("span", "osw-preview-ctl-label", str("dynamic_mode", "Dynamic mode")));
    const dynBtn = el("button", "osw-sq-switch-btn");
    dynBtn.type = "button";
    dynBtn.setAttribute("aria-pressed", profileDynamicOn() ? "true" : "false");
    const dynTrack = el("div", "osw-sq-switch" + (profileDynamicOn() ? " is-on" : ""));
    dynBtn.appendChild(dynTrack);
    dynBtn.addEventListener("click", function () {
      bridge("osw:haptic:1");
      const next = !profileDynamicOn();
      PROFILE_DYNAMIC_KEYS.forEach(function (key) { setValue(key, next); });
      syncProfileLevelDynamicMode(next);
      dynTrack.classList.toggle("is-on", next);
      dynBtn.setAttribute("aria-pressed", next ? "true" : "false");
      syncPreviewModeToggle();
      // Dynamic mode decides whether a picture is one slot or a light/dark
      // pair, so the picture fields have to be rebuilt, not just re-read.
      refreshImageFields();
      updateProfilePreview();
      updateProfileVisibility();
    });
    dynCtl.appendChild(dynBtn);
    headControls.appendChild(dynCtl);

    // Profile Style moved up here: it drives both the preview and which tabs
    // are relevant, so it belongs beside the preview rather than inside one.
    const styleCtl = el(
      "div",
      "osw-preview-ctl" + (simpleProfileModeActive() ? " osw-simple-profile-hidden" : "")
    );
    styleCtl.setAttribute("data-simple-profile-style", "true");
    styleCtl.appendChild(el("span", "osw-preview-ctl-label", str("profile_type", "Profile Style")));
    const styleField = fieldById["modern_menu_profile_type"];
    const styleSeg = el("div", "osw-segmented-control osw-preview-style-seg");
    styleSeg.setAttribute("data-field", "modern_menu_profile_type");
    styleSeg.setAttribute("data-field-type", "choice");
    ((styleField && styleField.options) || []).forEach(function (option) {
      const sBtn = el("div", "osw-segment-btn" + (option.value === values["modern_menu_profile_type"] ? " is-active" : ""), option.label);
      sBtn.setAttribute("role", "button");
      sBtn.setAttribute("tabindex", "0");
      sBtn.setAttribute("data-value", option.value);
      sBtn.addEventListener("click", function () {
        const newType = option.value;
        if (newType === values["modern_menu_profile_type"]) return;
        bridge("osw:haptic:1");
        Array.prototype.forEach.call(styleSeg.querySelectorAll(".osw-segment-btn"), function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-value") === String(newType));
        });
        // Tab bar doesn't wait on the value commit below — it only needs to
        // know the type that's about to land, so it can start fading right away.
        syncProfileTabs(newType);
        // Bar/Ring/Minimal are structurally different markup, so this crossfades
        // the swap instead of popping straight to the new DOM. `setValue` has to
        // stay inside the timeout, not run up front: it triggers its own
        // synchronous updateProfilePreview() via syncField, and that used to fire
        // before is-switching was even applied — the old markup got swapped for
        // the new one at full opacity, THEN faded out, so the fade-out animated
        // the wrong (already-new) content and the actual swap read as an instant
        // hiccup. Hiding first and only committing the value once invisible is
        // what makes the crossfade show old-fades-out / new-fades-in.
        const previewItem = document.getElementById("oswPreviewProfileItem");
        if (previewItem) {
          previewItem.classList.add("is-switching");
          setTimeout(function () {
            setValue("modern_menu_profile_type", newType);
            updateProfileVisibility();
            // setValue()'s internal rebuild overwrites className wholesale
            // (sets is-type-<type>), which drops is-switching along with it —
            // put it straight back, flush layout so the browser commits that
            // as the current state, then release it next frame to fade the
            // new markup in rather than have it appear instantly.
            const item = document.getElementById("oswPreviewProfileItem");
            if (item) {
              item.classList.add("is-switching");
              void item.offsetWidth;
              requestAnimationFrame(function () {
                item.classList.remove("is-switching");
              });
            }
          }, 260);
        } else {
          setValue("modern_menu_profile_type", newType);
          updateProfileVisibility();
        }
      });
      styleSeg.appendChild(sBtn);
    });
    styleCtl.appendChild(styleSeg);
    headControls.appendChild(styleCtl);

    const toggleBtn = el("button", "osw-profile-preview-toggle-btn");
    toggleBtn.id = "oswProfilePreviewToggle";
    toggleBtn.setAttribute("type", "button");
    toggleBtn.setAttribute("aria-label", str("toggle_preview_mode", "Toggle preview mode"));
    toggleBtn.innerHTML = currentProfilePreviewMode === "dark" ? OSW_MOON_ICON : OSW_SUN_ICON;

    toggleBtn.addEventListener("click", function () {
      currentProfilePreviewMode = currentProfilePreviewMode === "dark" ? "light" : "dark";
      const isDark = currentProfilePreviewMode === "dark";
      toggleBtn.innerHTML = isDark ? OSW_MOON_ICON : OSW_SUN_ICON;
      updateProfilePreview();
    });

    // With Dynamic mode off there is a single set of colours, so a light/dark
    // preview switch would have nothing to switch between.
    function syncPreviewModeToggle() {
      toggleBtn.classList.toggle("is-hidden", !profileDynamicOn());
    }
    syncPreviewModeToggle();

    // Match the Sidebar's header utilities: one theme button and one hold-to-
    // reset action, rather than a second reset control in the profile tab row.
    const resetLabel = str("reset", "Reset");
    const resetBtn = el("button", "osw-btn osw-designer-reset");
    resetBtn.type = "button";
    resetBtn.setAttribute("aria-label", resetLabel);
    resetBtn.title = resetLabel;
    resetBtn.appendChild(el("span", "osw-designer-reset-label", resetLabel));
    const resetIcon = el("span", "osw-designer-reset-icon");
    resetIcon.innerHTML = OSW_RESET_ICON;
    resetBtn.appendChild(resetIcon);
    installResetHold(resetBtn, resetProfileSettings, {
      title: resetLabel
    });
    const utilityCtl = el("div", "osw-preview-utility-ctl");
    utilityCtl.appendChild(toggleBtn);
    utilityCtl.appendChild(resetBtn);
    headControls.appendChild(utilityCtl);
    head.appendChild(headControls);
    container.appendChild(head);

    // 2. Stage
    const stage = el("div", "osw-profile-preview-stage");
    const backdrop = el("div", "osw-profile-preview-backdrop");
    backdrop.id = "oswPreviewBackdrop";

    const profileItem = el("div", "osw-profile-preview-item");
    profileItem.id = "oswPreviewProfileItem";
    backdrop.appendChild(profileItem);

    stage.appendChild(backdrop);
    container.appendChild(stage);

    // 3. Profile tabs use the shared page-header slot, matching tabbed pages
    // such as Main Menu. The settings controls themselves remain below the
    // preview, so changing tabs never shifts the header or preview card.
    if (page && page.sections) {
      const controlsWrap = el("div", "osw-profile-embedded-controls");

      const tabsWrap = el("div", "osw-subtabs-strip osw-profile-tabs-wrap");
      const pageTabs = document.getElementById("oswPageTabs");
      // "Profile Page" gathers everything that describes the panel itself
      // (layout, the user's info, which modules show). The customisation
      // tabs stay separate because each carries its own mode/colour cascade.
      const tabDefs = [
        { id: "picture", label: str("profile_tab_picture", "Profile Picture"), secIds: ["profile_picture_appearance", "profile_name_appearance", "profile_fill_appearance"] },
        { id: "background", label: str("profile_tab_background", "Background"), secIds: ["profile_bg_appearance"] },
        { id: "page", label: str("profile_tab_page", "Profile Sidebar"), secIds: ["profile_info", "profile_panel_toggles", "profile_page_background"] },
      ];

      const tabBtnById = {};

      function activateProfileTab(tabId) {
        activeProfileTab = tabId;
        Array.prototype.forEach.call(tabsWrap.querySelectorAll(".osw-segment-btn"), function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-tab-id") === tabId);
        });
        Array.prototype.forEach.call(controlsWrap.querySelectorAll(".osw-profile-tab-content"), function (contentNode) {
          contentNode.style.display = contentNode.getAttribute("data-tab-id") === tabId ? "" : "none";
        });
        updateProfileVisibility();
      }

      tabDefs.forEach(function (tDef) {
        const tBtn = el(
          "div",
          "osw-segment-btn osw-subtab" + (activeProfileTab === tDef.id ? " is-active" : ""),
          tDef.label
        );
        tBtn.setAttribute("role", "button");
        tBtn.setAttribute("tabindex", "0");
        tBtn.setAttribute("data-tab-id", tDef.id);
        tBtn.addEventListener("click", function () {
          bridge("osw:haptic:1");
          activateProfileTab(tDef.id);
        });
        tabBtnById[tDef.id] = tBtn;
        tabsWrap.appendChild(tBtn);
        if (tDef.id === "background") tBtn.style.maxWidth = "160px";
      });

      // Only the Bar layout paints a background behind the profile, so the whole
      // Background tab is irrelevant for Ring and Minimal. `.osw-segment-btn`
      // sets `display: inline-flex !important`, so hiding needs a class that
      // out-specifies it rather than an inline style (inline style alone loses
      // to a stylesheet !important rule) — `.is-hidden` (settings.css) collapses
      // opacity/width/padding together, so this is just a class toggle.
      //
      // `max-width: none` isn't something a browser can transition, so a
      // fixed generous cap (comfortably wider than the "Background" label in
      // any locale) sits on the button permanently, giving `.is-hidden`'s
      // max-width:0 something concrete to animate against. Measuring the
      // label's real width at runtime instead (e.g. right before each
      // collapse) sounds more precise but isn't reliable here: the very
      // first auto-hide can run before the section has been laid out
      // (getBoundingClientRect reads 0), which pins the collapse target at
      // 0 permanently — a 0-to-0 "transition" never actually changes value,
      // so it never fires transitionend either, meaning nothing was ever
      // going to catch and correct the bad pin later.
      syncProfileTabs = function (typeOverride) {
        const showBg = (typeOverride || values["modern_menu_profile_type"] || "bar") === "bar";
        const bgBtn = tabBtnById["background"];
        if (bgBtn) bgBtn.classList.toggle("is-hidden", !showBg);
        if (!showBg && activeProfileTab === "background") activateProfileTab("picture");
      };

      // Profile Level is a separate destination from the Profile tabs. Show
      // this shortcut only while at least one level-bearing game is enabled.
      const profileLevelLinkWrap = el(
        "div",
        "osw-profile-level-link-wrap"
      );
      const profileLevelLinkBtn = el(
        "button",
        "osw-segment-btn osw-subtab osw-profile-level-link-btn",
        str("profile_level_title", "Profile Level")
      );
      profileLevelLinkBtn.type = "button";
      profileLevelLinkBtn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        activeTabByPage.gamification = "gamification_profile_level";
        showPage("gamification");
      });
      profileLevelLinkWrap.appendChild(profileLevelLinkBtn);
      profileLevelLinkWrap.__syncProfileLevelLink = function () {
        profileLevelLinkWrap.classList.toggle("is-hidden", !profileLevelGameEnabled());
      };
      tabsWrap.appendChild(profileLevelLinkWrap);
      profileLevelLinkWrap.__syncProfileLevelLink();
      if (pageTabs) pageTabs.appendChild(tabsWrap);
      else controlsWrap.appendChild(tabsWrap);

      const tabContents = el("div", "osw-profile-tab-contents");
      tabDefs.forEach(function (tDef) {
        tabContents.appendChild(renderProfileTabContent(tDef, page));
      });

      controlsWrap.appendChild(tabContents);
      wrap.appendChild(controlsWrap);
      syncProfileTabs();
      wrap.__syncProfileTabs = syncProfileTabs;
    }

    function renderProfileTabContent(tDef, page) {
      const contentNode = el("div", "osw-profile-tab-content");
      contentNode.setAttribute("data-tab-id", tDef.id);
      if (activeProfileTab !== tDef.id) contentNode.style.display = "none";

      const secMap = {};
      (page.sections || []).forEach(function (sec) {
        secMap[sec.id] = sec;
      });

      function renderFieldNode(field, extraClass) {
        if (!field) return null;
        const renderer = FIELD_RENDERERS[field.type];
        if (!renderer) return null;
        const node = renderer(field);
        node.setAttribute("data-field-host", field.id);
        if (extraClass) node.classList.add(extraClass);
        return node;
      }

      function getField(secId, fieldId) {
        const sec = secMap[secId];
        if (!sec || !sec.fields) return null;
        return sec.fields.filter(function (f) { return f.id === fieldId; })[0] || null;
      }

      function profileFontMenuButton(fontField, sizeField, nameColorField, levelFontField, levelSizeField, levelColorField) {
        if (!fontField) return null;
        const label = str("profile_fonts", "Profile Fonts");
        const button = el(
          "button",
          "osw-organize-reset-btn osw-organize-fonts-btn osw-profile-font-menu-btn"
        );
        button.type = "button";
        button.setAttribute("aria-haspopup", "dialog");
        button.setAttribute("aria-expanded", "false");
        const icon = el("span", "osw-organize-fonts-icon");
        icon.innerHTML = ICON_TYPE;
        button.appendChild(icon);
        button.appendChild(el("span", null, label));
        button.addEventListener("click", function () {
          if (compactFontMenuEl && compactFontMenuEl.__anchor === button) {
            closeCompactFontMenu();
            return;
          }
          const roles = [{
            id: "profile_name_font",
            title: str("profile_name_font", "Name Font"),
            description: str(
              "profile_name_font_desc",
              "Changes the profile name's font, size, and light/dark colors."
            ),
            field_ids: [fontField.id]
              .concat(sizeField ? [sizeField.id] : [])
              .concat(nameColorField ? [nameColorField.id] : [])
          }];
          // The level line exists only when Profile Level is sourcing progress
          // from the selected mini-game, so keep its typography out of this
          // compact picker until it can affect the profile.
          if (selectedProfileLevelGameEnabled() && levelFontField) {
            roles.push({
              id: "profile_level_font",
              title: str("profile_level_font", "Level Font"),
              description: str(
                "profile_level_font_desc",
                "Changes the Profile Level text and chip font, size, and light/dark colors."
              ),
              field_ids: [levelFontField.id]
                .concat(levelSizeField ? [levelSizeField.id] : [])
                .concat(levelColorField ? [levelColorField.id] : [])
            });
          }
          openCompactFontMenu(button, roles, label);
        });
        return button;
      }

      if (tDef.id === "page") {
        // Profile Style is rendered in the preview header, not here.
        const secInfo = secMap["profile_info"];
        if (secInfo) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secInfo.id);
          if (secInfo.title) secBlock.appendChild(el("div", "osw-section-title", secInfo.title));

          ["userName", "userBirthday", "profile_music", "profile_bio"]
            .forEach(function (fieldId) {
              const field = getField("profile_info", fieldId);
              const node = renderFieldNode(field);
              if (node) {
                if (field.advanced) {
                  node.setAttribute("data-simple-profile-advanced", "true");
                  node.classList.toggle("osw-simple-profile-hidden", simpleProfileModeActive());
                  node.setAttribute("aria-hidden", simpleProfileModeActive() ? "true" : "false");
                }
                secBlock.appendChild(node);
              }
            });
          contentNode.appendChild(secBlock);
        }

        const secMod = secMap["profile_panel_toggles"];
        if (secMod) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secMod.id);
          secBlock.setAttribute("data-simple-profile-advanced", "true");
          secBlock.classList.toggle("osw-simple-profile-hidden", simpleProfileModeActive());
          secBlock.setAttribute("aria-hidden", simpleProfileModeActive() ? "true" : "false");
          if (secMod.title) secBlock.appendChild(el("div", "osw-section-title", secMod.title));

          const gridModules = el("div", "osw-profile-modules-grid");
          (secMod.fields || []).forEach(function (f) {
            const node = renderFieldNode(f);
            if (node) gridModules.appendChild(node);
          });
          secBlock.appendChild(gridModules);
          contentNode.appendChild(secBlock);
        }

        // The Gamification profile page's own backdrop. Its two background
        // color pairs share the available row; the second pair is conditional
        // on Gradient mode, so the first can take the full row on its own.
        const secPageBg = secMap["profile_page_background"];
        if (secPageBg) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secPageBg.id);
          secBlock.__section = secPageBg;
          secBlock.setAttribute("data-simple-profile-advanced", "true");
          secBlock.classList.toggle("osw-simple-profile-hidden", simpleProfileModeActive());
          secBlock.setAttribute("aria-hidden", simpleProfileModeActive() ? "true" : "false");
          if (secPageBg.title) secBlock.appendChild(el("div", "osw-section-title", secPageBg.title));
          const colorIds = {
            onigiri_profile_page_bg_color1: true,
            onigiri_profile_page_bg_color2: true
          };
          const colorFields = el("div", "osw-profile-page-bg-colors");
          let hasColorFields = false;
          (secPageBg.fields || []).forEach(function (f) {
            const node = renderFieldNode(f);
            if (!node) return;
            if (colorIds[f.id]) {
              if (!hasColorFields) secBlock.appendChild(colorFields);
              colorFields.appendChild(node);
              hasColorFields = true;
            } else {
              secBlock.appendChild(node);
            }
          });
          // Keep show_when behavior in sync with regular sections, including
          // hiding Second Color when Color only is selected.
          secBlock.__fieldsHost = secBlock;
          applyPlainVisibility(secBlock);
          conditionalBlocks.push(secBlock);
          contentNode.appendChild(secBlock);
        }

      } else if (tDef.id === "picture") {
        const secPic = secMap["profile_picture_appearance"];
        if (secPic) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secPic.id);
          if (secPic.title) secBlock.appendChild(el("div", "osw-section-title", secPic.title));

          const fMode = getField("profile_picture_appearance", "modern_menu_profile_picture_mode");
          const fPic = getField("profile_picture_appearance", "modern_menu_profile_picture");
          const fColor = getField("profile_picture_appearance", "modern_menu_profile_picture_color");
          const fContentType = getField("profile_picture_appearance", "modern_menu_profile_picture_content_type");
          const fLetter = getField("profile_picture_appearance", "modern_menu_profile_picture_letter");
          const fIcon = getField("profile_picture_appearance", "modern_menu_profile_picture_icon");

          if (fMode) {
            const modeNode = renderFieldNode(fMode);
            if (simpleProfileModeActive()) {
              modeNode.classList.add("osw-simple-profile-hidden");
              modeNode.setAttribute("aria-hidden", "true");
            }
            secBlock.appendChild(modeNode);
          }
          // One picture slot (or two, when split per theme) instead of the old
          // Import button + file-name dropdown pair; same for the colours.
          if (fPic) secBlock.appendChild(renderFieldNode(fPic));
          if (fContentType) secBlock.appendChild(renderFieldNode(fContentType));

          // Typography and its paired light/dark colours belong with the
          // picture they describe. Keeping them in the compact popup makes
          // the name and level options easy to distinguish without a tab of
          // permanently expanded controls.
          const fFont = getField("profile_name_appearance", "onigiri_font_profile_name");
          const fSize = getField("profile_name_appearance", "onigiri_font_size_profile_name");
          const fNameColor = getField("profile_name_appearance", "modern_menu_profile_name_color");
          const fLevelFont = getField("profile_name_appearance", "onigiri_font_profile_level");
          const fLevelSize = getField("profile_name_appearance", "onigiri_font_size_profile_level");
          const fLevelColor = getField("profile_name_appearance", "modern_menu_profile_level_color");
          const fontButton = profileFontMenuButton(
            fFont, fSize, fNameColor, fLevelFont, fLevelSize, fLevelColor
          );
          // Avatar content and typography are supporting profile controls.
          // Keep them together in the same two-column row instead of giving
          // each a full-width card.
          if (fLetter || fIcon || fontButton || fColor) {
            const avatarOptionsGrid = el("div", "osw-profile-grid-2col osw-profile-avatar-options");
            if (fLetter) avatarOptionsGrid.appendChild(renderFieldNode(fLetter));
            if (fIcon) avatarOptionsGrid.appendChild(renderFieldNode(fIcon));
            if (fontButton || fColor) {
              const fontAndColors = el("div", "osw-profile-fonts-and-colors");
              if (fontButton) fontAndColors.appendChild(fontButton);
              if (fColor) fontAndColors.appendChild(renderFieldNode(fColor));
              avatarOptionsGrid.appendChild(fontAndColors);
            }
            secBlock.appendChild(avatarOptionsGrid);
          }

          contentNode.appendChild(secBlock);
        }

        const secFill = secMap["profile_fill_appearance"];
        if (secFill) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secFill.id);
          if (secFill.title) secBlock.appendChild(el("div", "osw-section-title", secFill.title));

          const fHint = getField("profile_fill_appearance", "profile_fill_hint");
          const fColor = getField("profile_fill_appearance", "modern_menu_profile_fill_color");
          if (fHint) secBlock.appendChild(renderFieldNode(fHint, "osw-profile-hint-compact"));
          if (fColor) secBlock.appendChild(renderFieldNode(fColor));
          contentNode.appendChild(secBlock);
        }

      } else if (tDef.id === "background") {
        const secBg = secMap["profile_bg_appearance"];
        if (secBg) {
          const secBlock = el("div", "osw-profile-sec-block");
          secBlock.setAttribute("data-section-id", secBg.id);
          if (secBg.title) secBlock.appendChild(el("div", "osw-section-title", secBg.title));

          const fMode = getField("profile_bg_appearance", "modern_menu_profile_bg_mode");
          const fImg = getField("profile_bg_appearance", "modern_menu_profile_bg_image");
          const fColor = getField("profile_bg_appearance", "modern_menu_profile_bg_color");
          const fBlur = getField("profile_bg_appearance", "modern_menu_profile_bg_blur");
          const fOp = getField("profile_bg_appearance", "modern_menu_profile_bg_opacity");

          if (fMode) secBlock.appendChild(renderFieldNode(fMode));
          if (fImg) secBlock.appendChild(renderFieldNode(fImg));
          if (fColor) secBlock.appendChild(renderFieldNode(fColor));

          const gridSliders = el("div", "osw-profile-grid-2col");
          if (fBlur) gridSliders.appendChild(renderFieldNode(fBlur));
          if (fOp) gridSliders.appendChild(renderFieldNode(fOp));
          secBlock.appendChild(gridSliders);

          contentNode.appendChild(secBlock);
        }

      }

      return contentNode;
    }

    setTimeout(function () {
      updateProfilePreview();
      updateProfileVisibility();
      syncSimpleProfileControls();
    }, 10);
    return wrap;
  }

  /* Flips the preview to a theme from outside the preview's own renderer.
     Picking the dark picture while the preview is showing light would otherwise
     change nothing on screen, which reads as the click not having worked. */
  function setProfilePreviewMode(mode) {
    if (currentProfilePreviewMode === mode) return;
    currentProfilePreviewMode = mode;
    const button = document.getElementById("oswProfilePreviewToggle");
    if (button) button.innerHTML = mode === "dark" ? OSW_MOON_ICON : OSW_SUN_ICON;
    updateProfilePreview();
  }

  function updateProfileVisibility() {
    const pType = values["modern_menu_profile_type"] || "bar";
    const picMode = values["modern_menu_profile_picture_mode"] || "image";
    const bgMode = values["modern_menu_profile_bg_mode"] || "image";

    // One Dynamic mode now governs every light/dark pair on the page.
    const dyn = profileDynamicOn();
    const dynPic = dyn;
    const dynBg = dyn;
    const dynName = dyn;
    const dynFill = dyn;

    function setVisible(fieldId, show) {
      const hosts = document.querySelectorAll('[data-field-host="' + fieldId + '"], [data-field="' + fieldId + '"]');
      Array.prototype.forEach.call(hosts, function (node) {
        node.style.display = show ? "" : "none";
      });
    }

    /* Swaps a field's caption for its `descAlt` — some controls mean something
       slightly different depending on a neighbouring mode, and saying so beats
       one caption vague enough to cover both. */
    function setFieldDesc(fieldId, useAlt) {
      const field = fieldById[fieldId];
      if (!field || !field.descAlt) return;
      const text = useAlt ? field.descAlt : (field.desc || "");
      const hosts = document.querySelectorAll('[data-field="' + fieldId + '"]');
      Array.prototype.forEach.call(hosts, function (node) {
        if (node.__descOverride === text) return;
        node.__descOverride = text;
        if (node.__syncPairField) node.__syncPairField();
        else if (node.__syncImageField) node.__syncImageField();
      });
    }

    function setSectionVisible(secId, show) {
      const secs = document.querySelectorAll('[data-section-id="' + secId + '"]');
      Array.prototype.forEach.call(secs, function (node) {
        node.style.display = show ? "" : "none";
      });
    }

    // 1. Section Level
    setSectionVisible("profile_bg_appearance", pType === "bar");
    // Ring Color only makes sense when no enabled mini-game is supplying the
    // selected Profile Level progress for the ring.
    setSectionVisible("profile_fill_appearance", pType === "ring" && !selectedProfileLevelGameEnabled());

    // 2. Picture Fields
    // The picture and colour controls handle the light/dark split themselves,
    // so each is one row whether or not Dynamic mode is on.
    const pictureUsesGeneratedAvatar = picMode === "custom" || picMode === "accent";
    if (picMode === "accent") syncProfilePictureAccentColors();
    setVisible("modern_menu_profile_picture", picMode === "image");
    setVisible("modern_menu_profile_picture_color", pictureUsesGeneratedAvatar);
    setVisible("modern_menu_profile_picture_content_type", pictureUsesGeneratedAvatar);
    const pictureContentType = values["modern_menu_profile_picture_content_type"] || "letter";
    setVisible("modern_menu_profile_picture_letter", pictureUsesGeneratedAvatar && pictureContentType === "letter");
    setVisible("modern_menu_profile_picture_icon", pictureUsesGeneratedAvatar && pictureContentType === "icon");
    // When avatar content is unavailable, let Profile Fonts reclaim the
    // complete row instead of leaving an empty half-width column behind.
    const showAvatarContent = pictureUsesGeneratedAvatar
      && (pictureContentType === "letter" || pictureContentType === "icon");
    const avatarOptionGrids = document.querySelectorAll(".osw-profile-avatar-options");
    Array.prototype.forEach.call(avatarOptionGrids, function (grid) {
      grid.style.gridTemplateColumns = showAvatarContent ? "" : "1fr";
    });

    // 3. Background Fields
    setVisible("modern_menu_profile_bg_image", bgMode === "image" && pType === "bar");
    // The colour is not an alternative to the image: it fills the bar behind
    // it, so it is exactly what the opacity slider fades the image down into.
    // Hiding it in Image mode is what made low opacity look like a bug.
    setVisible("modern_menu_profile_bg_color",
               (bgMode === "custom" || bgMode === "image") && pType === "bar");
    setFieldDesc("modern_menu_profile_bg_color", bgMode === "image");
    setVisible("modern_menu_profile_bg_blur", bgMode === "image" && pType === "bar");
    setVisible("modern_menu_profile_bg_opacity", bgMode === "image" && pType === "bar");

    // 4. Name Colors
    // (Handled by color_pair internally)

    // 5. Fill Colors
    // (Handled by color_pair internally)

    syncSimpleProfileControls();
  }

  /* The page-side twin of config.themed_asset: an empty per-theme key falls
     back to the shared one, which is what "same picture for both" looks like on
     disk. Keeping the two in step is what makes the preview trustworthy. */
  function themedAsset(baseId, isDark, dynamic) {
    if (dynamic) {
      const themed = values[baseId + (isDark ? "_dark" : "_light")];
      if (themed) return themed;
    }
    return values[baseId] || "";
  }

  function updateProfilePreview() {
    const backdrop = document.getElementById("oswPreviewBackdrop");
    const profileItem = document.getElementById("oswPreviewProfileItem");
    if (!backdrop || !profileItem) return;

    // Profile colours resolve their own Dynamic flags. The sidebar backdrop
    // still follows Anki's appearance when those colours use one palette.
    const isDark = profileDynamicOn() ? currentProfilePreviewMode === "dark" : !!CTX.dark;
    paintProfileBackdrop(backdrop, isDark);

    // 2. Profile Item
    paintProfileItem(profileItem, isDark);
  }

  // Keep every profile-shaped preview on the live sidebar backdrop. The old
  // version read CTX.sidebarBg, which is only a snapshot from when Settings
  // opened. As a result, changing the Sidebar's colour, source, or image left
  // the Profile preview stale. Resolve the same live values as the Sidebar
  // preview instead.
  function paintProfileBackdrop(backdrop, isDark) {
    const existing = backdrop.querySelector(".osw-profile-preview-sidebar-layers");
    if (existing) existing.remove();

    // Keep effects on dedicated layers: filtering the backdrop itself also
    // filtered the profile contents, which is not how the real sidebar works.
    backdrop.style.background = "transparent";
    backdrop.style.filter = "none";
    backdrop.style.opacity = "1";
    backdrop.style.overflow = "hidden";

    const layers = el("div", "osw-profile-preview-sidebar-layers");
    layers.style.position = "absolute";
    layers.style.inset = "0";
    layers.style.overflow = "hidden";
    layers.style.pointerEvents = "none";
    backdrop.insertBefore(layers, backdrop.firstChild);

    const spec = designerSidebarSpec(values, isDark);
    if (spec.bgMode === "main") {
      // Match Main Menu means the sidebar shows the main backdrop through its
      // overlay, including a main-menu image or slideshow.
      designerPaintBackdrop(layers, values, isDark);
      const overlay = el("div", "osw-bg-preview-layer");
      overlay.style.position = "absolute";
      overlay.style.inset = "0";
      overlay.style.background = spec.color;
      if (spec.backdropBlur) {
        overlay.style.backdropFilter = "blur(" + spec.backdropBlur.toFixed(1) + "px)";
        overlay.style.webkitBackdropFilter = overlay.style.backdropFilter;
      }
      layers.appendChild(overlay);
      return;
    }

    const opacity = Math.max(0, Math.min(100, spec.opacity)) / 100;
    const fill = el("div", "osw-bg-preview-layer");
    fill.style.position = "absolute";
    fill.style.inset = "0";
    fill.style.background = rgba(spec.color, opacity);
    if (spec.backdropBlur) {
      fill.style.backdropFilter = "blur(" + spec.backdropBlur.toFixed(1) + "px)";
      fill.style.webkitBackdropFilter = fill.style.backdropFilter;
    }
    layers.appendChild(fill);

    // Widget-synced custom sidebars intentionally fall back to a colour in
    // patcher.py, so their old image selection must not leak into this preview.
    const usesImage = spec.bgMode !== "custom" && !values["modern_menu_sidebar_sync_box_effect"] &&
      (spec.type === "image_color" || spec.type === "slideshow");
    const url = usesImage && spec.image ? imageUrl("sidebar_bg", spec.image) : "";
    if (!url) return;

    const blurPx = Math.max(0, spec.blur) * 0.2;
    const image = el("div", "osw-bg-preview-image");
    image.style.position = "absolute";
    image.style.inset = "0";
    image.style.backgroundImage = "url(\"" + url.replace(/\"/g, "") + "\")";
    image.style.backgroundSize = "cover";
    image.style.backgroundPosition = "center";
    image.style.opacity = String(opacity);
    if (blurPx) {
      image.style.filter = "blur(" + blurPx.toFixed(1) + "px)";
      image.style.transform = "scale(" + (1 + blurPx / 50).toFixed(3) + ")";
    }
    layers.appendChild(image);
  }

  /* The profile exactly as a sidebar draws it — Bar / Ring / Minimal, with the
     chosen picture, background, fill colour, font and level chip. Split out of
     updateProfilePreview so the Sidebar page's own previews show the real
     profile instead of a grey placeholder: there is one profile, and both
     pages have to be looking at it. `profileItem` is any element to paint
     into; it is given the `.osw-profile-preview-item is-type-*` classes. */
  function paintProfileItem(profileItem, isDark, options) {
    options = options || {};
    const profileAssets = CTX.profileAssets || {};
    const pType = values["modern_menu_profile_type"] || "bar";
    const userName = values["userName"] || "USER";
    const advancedProfileFont = SETTINGS_MODE_PARITY || settingsComplexity === "advanced";
    const fontKey = advancedProfileFont
      ? (values["onigiri_font_profile_name"] || "sync")
      : (values["onigiri_font_main"] || "system");
    const profileFontField = advancedProfileFont
      ? fieldById["onigiri_font_profile_name"]
      : fieldById["onigiri_font_main"];
    const fontOption = (profileFontField && profileFontField.options || [])
      .filter(function (o) { return o.value === fontKey; })[0];
    const fontFamily = fontOption && fontOption.family ? fontOption.family : "inherit";
    const profileFontSize = advancedProfileFont
      ? (values["onigiri_font_size_profile_name"] || 14)
      : (values["onigiri_font_size_main"] || 14);
    const levelFontKey = advancedProfileFont
      ? (values["onigiri_font_profile_level"] || "sync")
      : fontKey;
    const levelFontField = advancedProfileFont
      ? fieldById["onigiri_font_profile_level"]
      : profileFontField;
    const levelFontOption = (levelFontField && levelFontField.options || [])
      .filter(function (o) { return o.value === levelFontKey; })[0];
    const levelFontFamily = levelFontKey === "sync"
      ? fontFamily
      : (levelFontOption && levelFontOption.family ? levelFontOption.family : fontFamily);
    const levelFontSize = advancedProfileFont
      ? (values["onigiri_font_size_profile_level"] || 11)
      : profileFontSize;

    const dynName = values["modern_menu_profile_name_dynamic_mode"] !== false;
    const nameColor = isDark ? (dynName ? (values["modern_menu_profile_name_color_dark"] || "#f9fafb") : (values["modern_menu_profile_name_color_light"] || "#111827"))
                             : (values["modern_menu_profile_name_color_light"] || "#111827");
    const levelColor = isDark ? (dynName ? (values["modern_menu_profile_level_color_dark"] || "#95D5E0") : (values["modern_menu_profile_level_color_light"] || "#95D5E0"))
                              : (values["modern_menu_profile_level_color_light"] || "#95D5E0");

    const dynFill = values["modern_menu_profile_fill_dynamic_mode"] !== false;
    const fillColor = isDark ? (dynFill ? (values["modern_menu_profile_fill_color_dark"] || "#4f7cff") : (values["modern_menu_profile_fill_color_light"] || "#4f7cff"))
                             : (values["modern_menu_profile_fill_color_light"] || "#4f7cff");

    // Bar-mode chip colors, straight from the same source the real sidebar
    // chip renders with, so the preview always matches what's on screen.
    const chipColors = options.chipColors || nookChipColors(values, isDark);
    const emptyLevel = { enabled: false, level: 0, fraction: 0, color: "" };
    let levelData = options.levelData || CTX.profileLevel || emptyLevel;
    // A newly selected source must not borrow the previous game's progress
    // while its save and fresh snapshot are on the bridge.
    if (levelData.game && levelData.game !== (values.g_profile_level_game || "nook")) levelData = emptyLevel;
    // The selected mini game supplies the level and fraction, never the
    // progress color. That color belongs to the shared Profile Level setting.
    // Do not fall back to levelData.color: Hexagon Land and Onigimon expose
    // their own accents there, which would make the profile bar change color.
    const sharedChipColors = (CTX.chipColors && CTX.chipColors[isDark ? "dark" : "light"]) || {};
    const effectiveFillColor = options.fillColor || chipColors.progress ||
      sharedChipColors.progress || fillColor;

    // Picture
    const picMode = values["modern_menu_profile_picture_mode"] || "image";
    const dynPic = values["modern_menu_profile_picture_dynamic_mode"] !== false;
    const picColor = isDark ? (dynPic ? (values["modern_menu_profile_picture_color_dark"] || "#B8BDC3") : (values["modern_menu_profile_picture_color_light"] || "#8CACB4"))
                            : (values["modern_menu_profile_picture_color_light"] || "#8CACB4");
    const picOpacity = (values["modern_menu_profile_picture_opacity"] != null ? values["modern_menu_profile_picture_opacity"] : 100) / 100;
    const picContentType = values["modern_menu_profile_picture_content_type"] || "letter";
    const picIconColor = isDark
      ? (dynPic ? (values["modern_menu_profile_picture_icon_color_dark"] || "#FFFFFF") : (values["modern_menu_profile_picture_icon_color_light"] || "#FFFFFF"))
      : (values["modern_menu_profile_picture_icon_color_light"] || "#FFFFFF");

    const picFileName = picMode === "image"
      ? themedAsset("modern_menu_profile_picture", isDark, dynPic)
      : "";
    // imageUrl() reads the live gallery cache, so a picture imported a moment
    // ago shows here without the page being rebuilt.
    const picUrl = (picFileName && imageUrl("profile", picFileName))
      || (picMode === "image" ? profileAssets.defaultPic : "");

    // Background
    const bgMode = values["modern_menu_profile_bg_mode"] || "image";
    const dynBg = values["modern_menu_profile_bg_dynamic_mode"] !== false;
    const bgColor = isDark ? (dynBg ? (values["modern_menu_profile_bg_color_dark"] || "#3C3C3C") : (values["modern_menu_profile_bg_color_light"] || "#EEEEEE"))
                           : (values["modern_menu_profile_bg_color_light"] || "#EEEEEE");
    const bgBlur = values["modern_menu_profile_bg_blur"] || 0;
    const bgOpacity = (values["modern_menu_profile_bg_opacity"] != null ? values["modern_menu_profile_bg_opacity"] : 50) / 100;

    const bgFileName = bgMode === "image"
      ? themedAsset("modern_menu_profile_bg_image", isDark, dynBg)
      : "";
    const bgUrl = (bgFileName && imageUrl("profile_bg", bgFileName))
      || (bgMode === "image" ? profileAssets.defaultBg : "");

    profileItem.innerHTML = "";
    profileItem.className = "osw-profile-preview-item is-type-" + pType;

    function avatarLetter() {
      const configured = String(values["modern_menu_profile_picture_letter"] || "").trim();
      if (configured === "...") return "";
      return configured ? configured.toUpperCase() : (userName || "U").slice(0, 1).toUpperCase();
    }

    function paintAvatarContent(av) {
      const icon = String(iconValue("modern_menu_profile_picture_icon") || "");
      if ((picMode === "custom" || picMode === "accent") && picContentType === "icon") {
        if (icon.indexOf("emoji:") === 0 && icon.slice(6)) {
          av.textContent = icon.slice(6);
          av.classList.add("is-avatar-emoji");
          return;
        }
        const iconUrl = resolveIconAssetUrl(icon);
        if (iconUrl) {
          const glyph = el("span", "osw-profile-avatar-icon");
          glyph.style.backgroundColor = picIconColor;
          glyph.style.webkitMaskImage = "url('" + iconUrl + "')";
          glyph.style.maskImage = "url('" + iconUrl + "')";
          av.appendChild(glyph);
          return;
        }
      }
      av.textContent = avatarLetter();
    }

    function applyAvatarStyle(av) {
      av.style.backgroundColor = picMode === "accent" ? profileAccentColor(isDark) : picColor;
      av.style.opacity = picOpacity;
      if (picUrl && picMode === "image") {
        av.style.backgroundImage = 'url("' + picUrl + '")';
        av.style.backgroundSize = 'cover';
        av.style.backgroundPosition = 'center';
      } else {
        paintAvatarContent(av);
        av.style.color = "#ffffff";
        av.style.fontWeight = "bold";
        if (bgMode === "image" && pType === "bar") {
          av.style.border = "2px solid rgba(255,255,255,0.4)";
          av.style.boxSizing = "border-box";
        }
      }
    }

    if (pType === "bar") {
      const pill = el("div", "osw-preview-bar-pill");
      pill.style.backgroundColor = bgMode === "accent" ? CTX.accent : bgColor;
      if (bgUrl && bgMode === "image") {
        const bgImg = el("div", "osw-preview-bar-bg-img");
        bgImg.style.backgroundImage = 'url("' + bgUrl + '")';
        bgImg.style.filter = 'blur(' + bgBlur + 'px)';
        bgImg.style.opacity = bgOpacity;
        pill.appendChild(bgImg);
      }

      const avatar = el("div", "osw-preview-avatar");
      applyAvatarStyle(avatar);

      const nameNode = el("div", "osw-preview-name", userName);
      nameNode.style.fontFamily = fontFamily;
      nameNode.style.fontSize = profileFontSize + "px";
      
      const isDynDefaultBg = (bgMode === "image" && dynBg && !bgFileName);
      if (bgUrl && bgMode === "image" && !isDynDefaultBg) {
        nameNode.style.color = nameColor;
        nameNode.style.textShadow = "1px 1px 3px rgba(0,0,0,0.5)";
      } else {
        nameNode.style.color = nameColor;
      }

      pill.appendChild(avatar);
      pill.appendChild(nameNode);

      if (levelData.enabled !== false) {
        const chip = el("div", "restaurant-level-chip");
        if (chipColors.bg) chip.style.backgroundColor = chipColors.bg;
        const chipLevel = el("span", "rl-chip-level", str("level_prefix", "Level") + " " + (levelData.level != null ? levelData.level : 0));
        chipLevel.style.color = levelColor;
        chipLevel.style.fontFamily = levelFontFamily;
        chipLevel.style.fontSize = levelFontSize + "px";
        const chipProgress = el("div", "rl-chip-progress");
        const chipFillColor = chipColors.progress || effectiveFillColor;
        if (chipFillColor && chipFillColor.length === 7 && chipFillColor.startsWith('#')) {
          const r = parseInt(chipFillColor.slice(1, 3), 16);
          const g = parseInt(chipFillColor.slice(3, 5), 16);
          const b = parseInt(chipFillColor.slice(5, 7), 16);
          const alpha = isDark ? 0.35 : 0.25;
          chipProgress.style.backgroundColor = 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
        }
        const chipFill = el("div", "rl-chip-progress-fill");
        const frac = levelData.fraction != null ? levelData.fraction : 0;
        chipFill.style.width = (frac * 100).toFixed(2) + "%";
        if (chipFillColor) chipFill.style.backgroundColor = chipFillColor;
        chipProgress.appendChild(chipFill);
        chip.appendChild(chipLevel);
        chip.appendChild(chipProgress);
        pill.appendChild(chip);
      }

      profileItem.appendChild(pill);
    } else if (pType === "ring") {
      const ringWrap = el("div", "osw-preview-ring-wrap");
      const avatar = el("div", "osw-preview-avatar");
      applyAvatarStyle(avatar);

      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 48 48");
      svg.setAttribute("class", "osw-preview-ring-svg");

      const circleTrack = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circleTrack.setAttribute("cx", "24"); circleTrack.setAttribute("cy", "24"); circleTrack.setAttribute("r", "21");
      circleTrack.setAttribute("stroke", "rgba(128,128,128,0.3)"); circleTrack.setAttribute("stroke-width", "3.5"); circleTrack.setAttribute("fill", "none");

      const r = 21;
      const circ = 2 * Math.PI * r;
      const frac = levelData.enabled !== false ? (levelData.fraction != null ? levelData.fraction : 0) : 0;
      const offset = circ * (1 - frac);

      const circleFill = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circleFill.setAttribute("cx", "24"); circleFill.setAttribute("cy", "24"); circleFill.setAttribute("r", "21");
      circleFill.setAttribute("stroke", effectiveFillColor); circleFill.setAttribute("stroke-width", "3.5"); circleFill.setAttribute("fill", "none");
      circleFill.setAttribute("stroke-linecap", "round");
      circleFill.setAttribute("stroke-dasharray", circ.toFixed(2)); circleFill.setAttribute("stroke-dashoffset", offset.toFixed(2));

      svg.appendChild(circleTrack);
      svg.appendChild(circleFill);

      ringWrap.appendChild(avatar);
      ringWrap.appendChild(svg);

      const infoCol = el("div", "osw-preview-ring-info");
      const nameNode = el("div", "osw-preview-name", userName);
      nameNode.style.fontFamily = fontFamily;
      nameNode.style.fontSize = profileFontSize + "px";
      nameNode.style.color = nameColor;
      infoCol.appendChild(nameNode);
      if (levelData.enabled !== false) {
        const subNode = el("div", "osw-preview-sub-text", str("level_prefix", "Level") + " " + (levelData.level != null ? levelData.level : 0) + " · " + (levelData.sourceName || ""));
        subNode.style.color = levelColor;
        subNode.style.fontFamily = levelFontFamily;
        subNode.style.fontSize = levelFontSize + "px";
        infoCol.appendChild(subNode);
      }

      profileItem.appendChild(ringWrap);
      profileItem.appendChild(infoCol);
    } else if (pType === "minimal") {
      const avatar = el("div", "osw-preview-avatar is-small");
      applyAvatarStyle(avatar);

      const infoCol = el("div", "osw-preview-minimal-info");
      const nameNode = el("div", "osw-preview-name", userName);
      nameNode.style.fontFamily = fontFamily;
      nameNode.style.fontSize = profileFontSize + "px";
      nameNode.style.color = nameColor;

      const track = el("div", "osw-preview-minimal-track");
      const fill = el("div", "osw-preview-minimal-fill");
      fill.style.backgroundColor = effectiveFillColor;
      const frac = levelData.enabled !== false ? (levelData.fraction != null ? levelData.fraction : 0) : 0;
      fill.style.width = (frac * 100).toFixed(1) + "%";
      track.appendChild(fill);

      infoCol.appendChild(nameNode);
      infoCol.appendChild(track);

      profileItem.appendChild(avatar);
      profileItem.appendChild(infoCol);
    }
  }

  /* ── image fields + the gallery popover ─────────────────────────────────────
   *
   * One control, one popover, for every picture in the add-on. The old settings
   * window spread this across three widgets per image (a combo box of file
   * names, an Import button, and a separate Gallery page to delete from), which
   * meant picking a picture without seeing it and deleting it somewhere else
   * entirely. Here the slot *is* the thumbnail, and everything else happens in
   * the popover it opens.
   *
   * The folder listing is shipped in CTX.galleries, so the popover opens on
   * real content in the same frame as the click; it then refreshes over the
   * bridge, which is what picks up files added outside Anki. */

  const galleryCache = {};

  function setGalleryList(folder, images) {
    const byName = {};
    (images || []).forEach(function (item) { byName[item.name] = item.url; });
    galleryCache[folder] = { list: images || [], byName: byName };
  }

  Object.keys(CTX.galleries || {}).forEach(function (folder) {
    setGalleryList(folder, CTX.galleries[folder]);
  });

  function galleryList(folder) {
    return (galleryCache[folder] || {}).list || [];
  }

  function imageUrl(folder, name) {
    if (!name) return "";
    const entry = galleryCache[folder];
    if (entry && entry.byName[name]) return entry.byName[name];
    // A file the cache has not seen yet (imported in another window). The media
    // server resolves it anyway, so build the URL rather than showing nothing.
    return (CTX.addonBase || "") + "user_files/" + folder + "/" + encodeURIComponent(name);
  }

  /* ── light/dark pairing ─────────────────────────────────────────────────────
   *
   * Dynamic mode says the profile *can* differ between themes. It does not say
   * every asset must: a user who wants one background for both themes and two
   * different avatars should not have to choose between them. So each asset
   * carries its own link switch, and Dynamic mode only decides whether that
   * switch is offered at all.
   *
   * "Linked" is stored honestly rather than as a mode flag the renderers would
   * have to learn: for a picture it means the light/dark keys are empty and the
   * base key answers for both (exactly the fallback every renderer already
   * does — see config.themed_asset); for a colour pair it means the two colours
   * are equal. The `*_theme_mode` key only records an explicit choice, so that
   * "unlinked but not yet different" survives reopening the window; left unset,
   * the values speak for themselves and nothing needs migrating. */

  function pairAvailable(field) {
    if (!field.lightField || !field.darkField) return false;
    return field.dynamicField ? values[field.dynamicField] !== false : true;
  }

  function pairLinked(field) {
    if (!pairAvailable(field)) return true;
    // The level chip's colours are split by their own Dynamic switch, not by
    // an inferred "these two happen to be equal": with Dynamic on the reader
    // looks *only* at the light/dark keys, so collapsing onto the shared key
    // would write somewhere nothing reads.
    if (field.alwaysSplit) return false;
    const explicit = values[field.themeModeField];
    if (explicit === "single") return true;
    if (explicit === "separate") return false;
    return field.type === "color_pair"
      ? values[field.lightField] === values[field.darkField]
      : !values[field.lightField] && !values[field.darkField];
  }

  function setPairLinked(field, linked) {
    // Not every pair declares a real hidden field for its theme mode — for
    // those, "same for both" is inferred from the two values (see pairLinked)
    // and there is nothing to persist. Staging an id the store has no binding
    // for would come back from the bridge as a save error, so the write is
    // guarded the same way applyCascade guards its targets.
    if (fieldById[field.themeModeField]) {
      setValue(field.themeModeField, linked ? "single" : "separate");
    }
    // Main Background renamed this key during the settings rewrite. Keep the
    // legacy mirror coherent for older runtime surfaces and synced profiles.
    if (field.themeModeField === "modern_menu_bg_image_theme_mode" &&
        fieldById.modern_menu_background_image_mode) {
      setValue("modern_menu_background_image_mode", linked ? "single" : "separate");
    }
    if (field.type === "color_pair") {
      // Linking adopts the light colour for both; unlinking leaves them equal
      // so nothing changes on screen until the user actually picks a second one.
      if (linked) setValue(field.darkField, values[field.lightField]);
    } else if (linked) {
      // Collapse onto the base key, which is what both themes then read.
      // Keep the themed slots intact: turning Dynamic mode back on should
      // restore the user's two choices instead of silently deleting them.
      setValue(field.id, values[field.lightField] || values[field.darkField] || values[field.id] || "");
    } else {
      // Seed both from whatever was shared, so splitting is a no-op until one
      // of the two is changed.
      const shared = values[field.id] || "";
      if (!values[field.lightField]) setValue(field.lightField, shared);
      if (!values[field.darkField]) setValue(field.darkField, shared);
    }
    refreshImageFields();
    refreshIconChips();
    refreshPairFields();
    updateProfilePreview();
  }



  /* Which key(s) a picture field writes right now: one slot when the asset is
     linked (or has no pair at all), two when it is split per theme. */
  function imageTargets(field) {
    if (pairAvailable(field) && !pairLinked(field)) {
      return [
        {
          id: field.lightField,
          role: "light",
          label: String(str("light_mode", "Light")).replace(/\s+mode$/i, ""),
          key: "L"
        },
        {
          id: field.darkField,
          role: "dark",
          label: String(str("dark_mode", "Dark")).replace(/\s+mode$/i, ""),
          key: "D"
        }
      ];
    }
    // Dynamic mode off: one value serves both themes, so use the neutral
    // "Color" role instead of suggesting separate light/dark values.
    // A visible color_pair is a presentation field, not storage: its actual
    // value lives in the light companion (and mirrors to dark while linked).
    // Writing to `field.id` made the single Dynamic-off slot appear editable
    // but left the real Pomodoro value unchanged.
    const singleId = field.type === "color_pair" && field.lightField
      ? (field.singleField || field.lightField)
      : field.id;
    return [{ id: singleId, role: "single", label: "", key: "" }];
  }

  /* Light/dark keys fall back to the plain one when unset — the same rule every
     renderer applies (`conf[..._dark] or conf[...]`), so the slot shows the
     picture that will actually be drawn, not an empty box. */
  function imageValue(field, target) {
    if (target.role === "single") {
      const preferred = CTX.dark ? field.darkField : field.lightField;
      const alternate = CTX.dark ? field.lightField : field.darkField;
      return values[target.id] || values[preferred] || values[alternate] || "";
    }
    return values[target.id] || values[field.id] || "";
  }

  /* Label, optional description, and — when Dynamic mode makes it meaningful —
     the link switch, on one line. Shared by the picture and colour fields so
     the two read as the same kind of control. */
  function makeFieldHead(field, descOverride) {
    const head = el("div", "osw-imagefield-head");
    const text = el("div", "osw-imagefield-head-text");
    if (field.label) text.appendChild(el("div", "osw-row-label", field.label));
    const desc = descOverride != null ? descOverride : (field.desc || "");
    if (desc) text.appendChild(el("div", "osw-row-desc", desc));
    head.appendChild(text);
    return head;
  }

  function renderImage(field) {
    const host = el("div", "osw-imagefield");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "image");

    const slots = el("div", "osw-imagefield-slots");

    function paint() {
      const targets = imageTargets(field);
      // Rebuilt whole: Dynamic mode and the link switch both change how many
      // slots there are *and* whether the head carries a switch at all.
      host.innerHTML = "";
      host.appendChild(makeFieldHead(field, host.__descOverride));
      host.appendChild(slots);
      slots.innerHTML = "";
      slots.classList.toggle("is-split", targets.length > 1);
      slots.classList.add("has-color-slots");
      targets.forEach(function (target) {
        const name = imageValue(field, target);
        const url = imageUrl(field.folder, name);

        const slot = el("button", "osw-imgslot" + (name ? " is-set" : ""));
        slot.type = "button";
        slot.setAttribute("data-slot", target.role);

        const thumb = el("span", "osw-imgslot-thumb");
        appendImageWithFallback(thumb, url);
        slot.appendChild(thumb);

        const meta = el("span", "osw-imgslot-meta");
        if (target.label) {
          const role = el("span", "osw-imgslot-role");
          const kbd = el("span", "osw-imgslot-kbd");
          if (target.role === "light") {
            kbd.innerHTML = OSW_SUN_ICON;
          } else if (target.role === "dark") {
            kbd.innerHTML = OSW_MOON_ICON;
          } else {
            kbd.textContent = target.key;
          }
          role.appendChild(kbd);
          role.appendChild(el("span", "osw-imgslot-role-label", target.label));
          meta.appendChild(role);
        }
        meta.appendChild(el(
          "span",
          "osw-imgslot-name",
          name || field.emptyLabel || str("gallery_choose", "Choose image")
        ));
        slot.appendChild(meta);

        const action = el("span", "osw-imgslot-action");
        const actionIcon = el("span", "osw-imgslot-action-icon");
        actionIcon.innerHTML = ICON_SWAP;
        action.appendChild(actionIcon);
        action.appendChild(el("span", "osw-imgslot-action-label", str("gallery_change", "Change")));
        slot.appendChild(action);

        slot.addEventListener("click", function () {
          bridge("osw:haptic:1");
          openGallery(field, target.role);
        });
        slots.appendChild(slot);
      });
    }

    host.__syncImageField = paint;
    paint();
    return host;
  }

  /* Bundled Onigimon scenes are intentionally separate from the user's image
     library: presets remain available after the user tidies their own uploads,
     and each category can be browsed without an import step. */
  function renderScenarioPicker(field) {
    const host = el("div", "osw-scenarios");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "scenario_picker");

    const categoryList = field.categories || [];
    let activeCategory = "";
    const selectedAtOpen = values[field.id] || field.default || "";
    categoryList.forEach(function (category) {
      if (selectedAtOpen.indexOf("/" + category.id + "/") !== -1) {
        activeCategory = category.id;
      }
    });
    if (!activeCategory && categoryList.length) activeCategory = categoryList[0].id;

    // Keep category selection visually parallel with Background Type: a
    // labelled, full-width segmented control rather than a detached tab bar.
    const categoryTabsRow = el("div", "osw-scenario-tabs-row osw-segmented-wrap");
    categoryTabsRow.appendChild(el(
      "div", "osw-scenario-tabs-title osw-segmented-title",
      str("onigimon_scenario_type", "Scenario type")
    ));
    const categoryTabs = el("div", "osw-scenario-tabs osw-segmented-control");
    categoryTabsRow.appendChild(categoryTabs);
    const categories = el("div", "osw-scenario-categories");
    function showCategory(categoryId) {
      activeCategory = categoryId;
      Array.prototype.forEach.call(categoryTabs.querySelectorAll("[data-scenario-category-tab]"), function (tab) {
        const active = tab.getAttribute("data-scenario-category-tab") === activeCategory;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      Array.prototype.forEach.call(categories.querySelectorAll("[data-scenario-category]"), function (panel) {
        panel.hidden = panel.getAttribute("data-scenario-category") !== activeCategory;
      });
    }
    categoryList.forEach(function (category) {
      const tab = el("button", "osw-scenario-tab osw-segment-btn", category.title || "");
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("data-scenario-category-tab", category.id || "");
      tab.addEventListener("click", function () {
        bridge("osw:haptic:1");
        showCategory(category.id || "");
      });
      categoryTabs.appendChild(tab);

      const group = el("section", "osw-scenario-category");
      group.setAttribute("data-scenario-category", category.id || "");
      const grid = el("div", "osw-scenario-grid");
      (category.items || []).forEach(function (item) {
        const tile = el("button", "osw-scenario-tile");
        tile.type = "button";
        tile.setAttribute("data-scenario-path", item.path || "");
        tile.setAttribute("aria-label", item.label || "Scenario");
        const image = document.createElement("img");
        image.src = item.image || "";
        image.alt = "";
        image.loading = "lazy";
        image.decoding = "async";
        tile.appendChild(image);
        tile.addEventListener("click", function () {
          bridge("osw:haptic:1");
          setValue(field.id, item.path || field.default || "");
          setValue(field.modeField, "preset");
        });
        grid.appendChild(tile);
      });
      group.appendChild(grid);
      categories.appendChild(group);
    });
    host.appendChild(categoryTabsRow);
    host.appendChild(categories);
    showCategory(activeCategory);

    host.__syncScenarioPicker = function () {
      const selectedPath = values[field.id] || field.default || "";
      Array.prototype.forEach.call(host.querySelectorAll("[data-scenario-path]"), function (tile) {
        const selected = tile.getAttribute("data-scenario-path") === selectedPath;
        tile.classList.toggle("is-selected", selected);
        tile.setAttribute("aria-pressed", selected ? "true" : "false");
      });
    };
    host.__syncScenarioPicker();
    return host;
  }

  /* A color's swatch carries its value; the visible role name carries its
     context in both split and linked theme modes. */

  function renderColorPair(field) {
    const host = el("div", "osw-imagefield osw-pairfield");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "color_pair");

    const slots = el("div", "osw-imagefield-slots");

    function paint() {
      const targets = imageTargets(field);
      host.innerHTML = "";
      host.appendChild(makeFieldHead(field, host.__descOverride));
      host.appendChild(slots);
      slots.innerHTML = "";
      slots.classList.toggle("is-split", targets.length > 1);
      // A colour that is genuinely one value for both themes (a marker, the
      // heatmap streak icon) declares no light/dark companions at all and is
      // bound straight to its own key.
      const single = !field.lightField && !field.darkField;

      targets.forEach(function (target) {
        // A linked pair still writes through the light key; the dark one is
        // mirrored on the way back from the picker (see setFieldValue).
        // `singleField` overrides that for a pair whose "both themes" state has
        // a key of its own rather than borrowing the light one.
        const key = single
          ? field.id
          : (target.role === "single" ? (field.singleField || field.lightField) : target.id);
        const value = values[key] || "";
        const fallback = pairColorFallback(field, target);
        const shown = value || fallback;
        const isDefault = !value && !!fallback;
        // The chip's colours are stored in Qt's #AARRGGBB order, which CSS
        // would read as #RRGGBBAA — a different hue, not just a different
        // opacity. Everything shown or handed to the picker is converted.
        const displayed = field.chipRole ? qtColorToCss(shown) : shown;

        const slot = el("button", "osw-imgslot osw-colorslot" + (isDefault ? " is-default" : ""));
        slot.type = "button";
        slot.setAttribute("data-slot", target.role);
        slot.setAttribute(
          "aria-label",
          target.role === "light" ? "Light color" : target.role === "dark" ? "Dark color" : (field.label || str("color", "Color"))
        );
        const swatch = el("span", "osw-imgslot-thumb is-swatch");
        swatch.style.background = displayed || "transparent";
        slot.appendChild(swatch);

        const meta = el("span", "osw-imgslot-meta");
        const role = el("span", "osw-imgslot-role");
        if (target.role === "light") {
          role.innerHTML = OSW_SUN_ICON;
        } else if (target.role === "dark") {
          role.innerHTML = OSW_MOON_ICON;
        }
        if (target.role === "light" || target.role === "dark") meta.appendChild(role);
        meta.appendChild(el("span", "osw-imgslot-name", String(displayed || "").toUpperCase()));
        slot.appendChild(meta);
        slot.addEventListener("click", function () {
          bridge("osw:haptic:1");
          openColorPickerById(key, field.chipRole ? cssColorToHex(displayed) : shown);
        });
        slots.appendChild(slot);
      });
    }

    host.__syncPairField = paint;
    paint();
    return host;
  }

  /* Companion colour under an icon popover's grid (e.g. Heatmap Shape's own
     "Color") — same compact slot shape as the deck browser's Edit Icon modal
     (web/icon_modal.js: .onigiri-icon-color-*), not the full-size field row
     renderColor/renderColorPair use everywhere else on the page. Still reads
     and writes through imageTargets/imageValue, so a field's existing light/
     dark linking (Dynamic Mode) behaves exactly as it does outside the
     popover — one slot collapses to a shared colour, two when unlinked. */
  /* The colour an untinted icon is painted with: the field names the two keys
     that hold it (`fallback_light`/`fallback_dark` in the schema), and which of
     them applies follows the same light/dark link as everything else. */
  function iconColorFallback(field) {
    if (!field.fallbackLight && !field.fallbackDark) return "";
    const isDark = !!CTX.dark;
    return (isDark ? values[field.fallbackDark] : values[field.fallbackLight]) ||
      values[field.fallbackLight] || values[field.fallbackDark] || "";
  }

  /* Same idea for a light/dark pair, per slot: the light slot inherits the light
     colour, the dark slot the dark one. A pair whose value is empty means
     "inherit" (the deck list showing the sidebar through it, a highlighted row
     keeping the normal text colour) — the slot shows what it inherits so it
     still reads as a colour with a hex, rather than as a blank. */
  function pairColorFallback(field, target) {
    // The chip's three colours inherit whatever nook_level resolves when they
    // are unset, which Python ships as chipDefaults — a literal colour rather
    // than another field's value.
    if (field.chipRole) {
      const defaults = (CTX.chipDefaults || {})[chipFallbackDark(target) ? "dark" : "light"] || {};
      return qtColorToCss(defaults[field.chipRole] || "");
    }
    if (field.inheritMainBackground) {
      const useDark = target && target.role === "dark"
        ? true
        : target && target.role === "light"
          ? false
          : !!CTX.dark;
      const configured = useDark
        ? values.things_main_background_dark
        : values.things_main_background_light;
      const legacy = useDark ? "#0b0c0f" : "#f6f3ec";
      const clean = String(configured || "").toLowerCase() === legacy
        ? ""
        : configured;
      return clean || (useDark ? "#171717" : "#eeeeee");
    }
    if (field.staticFallback) {
      const dark = target && target.role === "dark";
      const single = !target || target.role === "single";
      // Dynamic mode off makes the live Pomodoro use its light palette in
      // either app theme. Its collapsed colour slot must show that same value.
      if (single) {
        const useDark = field.dynamicField && values[field.dynamicField] === false
          ? false
          : !!CTX.dark;
        return (useDark ? field.staticFallback.dark : field.staticFallback.light) || "";
      }
      return (dark ? field.staticFallback.dark : field.staticFallback.light) || "";
    }
    if (!field.fallbackLight && !field.fallbackDark) return "";
    if (target && target.role === "dark") {
      return values[field.fallbackDark] || values[field.fallbackLight] || "";
    }
    return values[field.fallbackLight] || values[field.fallbackDark] || "";
  }

  /* An icon tile's companion colour, shown under the tile itself: one small
     swatch per theme slot (two when the pair is unlinked, one when it is not),
     hex on the tooltip rather than in the label — a 4-up grid of tiles has no
     room for the full slot, and the point here is comparing the four colours
     side by side, which a popover cannot do. Clicking opens the same native
     picker the popover's slot opens. */
  function renderIconTileColors(field) {
    // `osw-pairfield` is what refreshPairFields() looks for — without it the
    // swatch keeps showing the old colour after the native picker returns,
    // because nothing ever calls its paint().
    const host = el("div", "osw-icontile-colors osw-pairfield");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", field.type);

    function paint() {
      host.innerHTML = "";
      const targets = field.type === "color_pair"
        ? imageTargets(field)
        : [{ id: field.id, role: "single" }];
      targets.forEach(function (target) {
        const key = field.type === "color_pair"
          ? (target.role === "single" ? field.lightField : target.id)
          : field.id;
        const value = values[key] || (field.type === "color_pair"
          ? pairColorFallback(field, target) : iconColorFallback(field)) || "";
        const chip = el("button", "osw-icontile-swatch");
        chip.type = "button";
        chip.title = (field.label || "") + " " +
          (target.role === "dark" ? str("theme_dark_mode", "Dark mode")
            : target.role === "light" ? str("theme_light_mode", "Light mode") : "") +
          " " + String(value).toUpperCase();
        const dot = el("span", "osw-icontile-dot");
        dot.style.background = value || "transparent";
        chip.appendChild(dot);
        if (target.role === "light" || target.role === "dark") {
          const glyph = el("span", "osw-icontile-theme");
          glyph.innerHTML = target.role === "dark" ? OSW_MOON_ICON : OSW_SUN_ICON;
          chip.appendChild(glyph);
        }
        chip.addEventListener("click", function (event) {
          event.stopPropagation();
          bridge("osw:haptic:1");
          openColorPickerById(key, value);
        });
        host.appendChild(chip);
      });
    }

    host.__syncPairField = paint;
    paint();
    return host;
  }

  function renderIconPopupColorSlots(field) {
    const host = el("div", "onigiri-icon-color-section osw-pairfield");
    host.setAttribute("data-field", field.id);

    const slotsRow = el("div", "onigiri-icon-color-slots");
    host.appendChild(slotsRow);

    function paint() {
      slotsRow.innerHTML = "";
      const targets = field.type === "color_pair" ? imageTargets(field) : [{ id: field.id, role: "single" }];
      targets.forEach(function (target) {
        const value = field.type === "color_pair" ? imageValue(field, target) : (values[field.id] || "");
        // An unset tint is not "no colour": it means the glyph is painted with
        // the shared icon colour. Show that, so the swatch always answers "what
        // colour is this icon right now" instead of going blank.
        const fallback = field.type === "color_pair"
          ? pairColorFallback(field, target) : iconColorFallback(field);
        const shown = value || fallback;
        const isDefault = !value && !!fallback;

        const slot = el("button", "onigiri-icon-color-slot" + (isDefault ? " is-default" : ""));
        slot.type = "button";
        slot.setAttribute(
          "aria-label",
          target.role === "light" ? "Light color" : target.role === "dark" ? "Dark color" : (field.label || str("icon_color", "Icon Color"))
        );
        const swatch = el("span", "onigiri-icon-color-swatch");
        swatch.style.background = shown || "transparent";
        slot.appendChild(swatch);

        const meta = el("span", "onigiri-icon-color-meta");
        const roleRow = el("span", "onigiri-icon-color-role");
        if (target.role === "light") {
          roleRow.innerHTML = OSW_SUN_ICON;
        } else if (target.role === "dark") {
          roleRow.innerHTML = OSW_MOON_ICON;
        }
        if (target.role === "light" || target.role === "dark") {
          roleRow.appendChild(document.createTextNode(target.label));
        }
        if (target.role === "light" || target.role === "dark") meta.appendChild(roleRow);
        meta.appendChild(el("span", "onigiri-icon-color-hex", String(shown || "").toUpperCase()));
        slot.appendChild(meta);
        slot.addEventListener("click", function () {
          bridge("osw:haptic:1");
          openColorPickerById(target.id, shown, "", !!value && !!fallback);
        });
        slotsRow.appendChild(slot);
      });
    }

    host.__syncPairField = function () {
      paint();
      // The grid above these slots is tinted with this very colour.
      if (iconPicker && iconPicker.retint) iconPicker.retint();
    };
    paint();
    return host;
  }

  /* Repaints every picture slot on the page. Dynamic mode changes how many
     slots a field has, and a delete can blank one from Python, so the trigger
     is not always the field's own edit. */
  function refreshIconChips() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-icon-chip"), function (node) {
      if (node.__syncIconChip) node.__syncIconChip();
    });
  }

  function refreshImageFields() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-imagefield"), function (node) {
      if (node.__syncImageField) node.__syncImageField();
    });
  }

  function refreshScenarioPickers() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-scenarios"), function (node) {
      if (node.__syncScenarioPicker) node.__syncScenarioPicker();
    });
  }

  function refreshPairFields() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-pairfield"), function (node) {
      if (node.__syncPairField) node.__syncPairField();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-color-gallery"), function (node) {
      if (node.__syncColorGallery) node.__syncColorGallery();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-reviewer-color-gallery"), function (node) {
      if (node.__syncColorGallery) node.__syncColorGallery();
    });
  }

  /* The colour pair whose light key is `id` and which is currently showing a
     single shared slot — the caller must consult this BEFORE writing, since
     "linked" can be inferred from the two colours being equal. */
  function linkedPairForLightKey(id) {
    let match = null;
    Object.keys(fieldById).forEach(function (fid) {
      const field = fieldById[fid];
      if (field.type !== "color_pair") return;
      if (field.lightField !== id) return;
      if (pairLinked(field)) match = field;
    });
    return match;
  }

  // ── gallery popover ────────────────────────────────────────────────────────

  const ICON_IMAGE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"' +
    ' stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/>' +
    '<circle cx="8.5" cy="9.5" r="1.6"/><path d="M21 15.5l-4.6-4.2a2 2 0 0 0-2.7 0L4 20"/></svg>';
  const ICON_CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>';
  const ICON_PLUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
  const ICON_MINUS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round"><path d="M5 12h14"/></svg>';
  const ICON_TYPE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h16v3"/>' +
    '<path d="M9 20h6M12 4v16"/></svg>';
  const ICON_PALETTE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/>' +
    '<circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>' +
    '<circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 22a10 10 0 1 1 10-10c0 2.2-1.8 4-4 4h-1.8a2.2 2.2 0 0 0-2.2 2.2c0 .5.2 1 .5 1.4.4.5 0 1.4-.7 1.8-.6.4-1.2.6-1.8.6Z"/></svg>';
  const ICON_INFO = '<svg class="lucide lucide-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/>' +
    '<path d="M12 16v-4M12 8h.01"/></svg>';
  const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';

  /* WebView shows its own broken-image glyph when a stored filename no longer
     resolves. That glyph is especially distracting in the compact Light/Dark
     image slots, where it gets rendered as a tiny shaped fallback. Keep image
     failures inside our visual language: remove the failed <img> and use the
     same deliberate placeholder as an empty slot. */
  function appendImageWithFallback(container, url) {
    if (!url) {
      container.insertAdjacentHTML("beforeend", ICON_IMAGE);
      return null;
    }
    const img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    // Keep the browser's native broken-image marker from flashing while the
    // request is in flight. A successful image becomes visible on load; a
    // failed one is removed by the error handler below.
    img.style.visibility = "hidden";
    img.addEventListener("load", function () { img.style.visibility = "visible"; });
    img.addEventListener("error", function () {
      img.remove();
      if (!container.querySelector("svg")) container.insertAdjacentHTML("beforeend", ICON_IMAGE);
    });
    img.src = url;
    container.appendChild(img);
    return img;
  }

  // One compact typography editor shared by Widget Color and Effect and the
  // stats designer. It edits the existing role fields without mounting the
  // former full preview cards.
  let compactFontMenuEl = null;
  let compactFontMenuOutsideHandler = null;
  let compactFontMenuResizeHandler = null;
  let activeCompactFontRole = "";

  function closeCompactFontMenu() {
    if (compactFontMenuOutsideHandler) {
      document.removeEventListener("pointerdown", compactFontMenuOutsideHandler, true);
      compactFontMenuOutsideHandler = null;
    }
    if (compactFontMenuResizeHandler) {
      window.removeEventListener("resize", compactFontMenuResizeHandler);
      compactFontMenuResizeHandler = null;
    }
    if (compactFontMenuEl && compactFontMenuEl.parentNode) {
      const anchor = compactFontMenuEl.__anchor;
      const floatingRoleList = compactFontMenuEl.__floatingRoleList;
      if (floatingRoleList && floatingRoleList.parentNode) {
        floatingRoleList.parentNode.removeChild(floatingRoleList);
      }
      if (anchor) anchor.setAttribute("aria-expanded", "false");
      compactFontMenuEl.parentNode.removeChild(compactFontMenuEl);
    }
    compactFontMenuEl = null;
  }

  function openCompactFontMenu(anchor, roles, labelText) {
    closeCompactFontMenu();
    roles = (roles || []).filter(function (role) {
      return !role.show_when || showWhenMatches(role.show_when);
    });
    if (!roles || !roles.length) return;
    const hasRolePicker = roles.length > 1;

    const menu = el("div", "osw-organize-menu is-widget-fonts");
    const isColorMenu = anchor.classList.contains("osw-organize-colors-btn");
    if (isColorMenu) {
      menu.classList.add("is-widget-colors");
    }
    menu.__anchor = anchor;

    const head = el("div", "osw-organize-font-head");
    head.appendChild(el("span", "osw-organize-font-title", labelText));
    const headActions = el("div", "osw-organize-font-actions");
    const syncSlot = el("div", "osw-organize-font-sync-slot");
    const infoBtn = el("button", "osw-organize-font-info");
    infoBtn.type = "button";
    infoBtn.setAttribute("aria-label", str("font_role_info", "What does this control change?"));
    infoBtn.setAttribute("aria-expanded", "false");
    infoBtn.innerHTML = ICON_INFO;
    const closeBtn = el("button", "osw-organize-font-close");
    closeBtn.type = "button";
    closeBtn.innerHTML = ICON_CLOSE;
    closeBtn.addEventListener("click", closeCompactFontMenu);
    headActions.appendChild(syncSlot);
    headActions.appendChild(infoBtn);
    headActions.appendChild(closeBtn);
    head.appendChild(headActions);
    menu.appendChild(head);

    const infoText = el("div", "osw-organize-font-info-text");
    infoText.hidden = true;
    menu.appendChild(infoText);

    if (!roles.some(function (role) { return role.id === activeCompactFontRole; })) {
      activeCompactFontRole = roles[0].id;
    }
    const rolePicker = el("div", "osw-organize-font-role-picker");
    const roleButton = el("button", "osw-organize-font-role");
    roleButton.type = "button";
    roleButton.setAttribute("aria-haspopup", "listbox");
    roleButton.setAttribute("aria-expanded", "false");
    const roleLabel = el("span", "osw-organize-font-role-label");
    const roleChevron = el("span", "osw-organize-font-role-chevron");
    roleChevron.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    roleButton.appendChild(roleLabel);
    roleButton.appendChild(roleChevron);
    const roleList = el("div", "osw-organize-font-role-list");
    roleList.setAttribute("role", "listbox");
    roleList.hidden = true;
    if (isColorMenu) {
      rolePicker.classList.add("is-color-gallery");
      roleList.classList.add("osw-reviewer-color-gallery");
      roleList.setAttribute("role", "tablist");
      roleList.hidden = false;
      rolePicker.appendChild(roleList);
    } else {
      rolePicker.appendChild(roleButton);
      rolePicker.appendChild(roleList);
    }
    menu.appendChild(rolePicker);
    rolePicker.hidden = !hasRolePicker;

    const fieldsHost = el("div", "osw-organize-font-fields");
    menu.appendChild(fieldsHost);

    // The menu itself scrolls when its contents are taller than the viewport.
    // Keep the role list above that scrolling/clipping boundary while it is
    // open, otherwise the lower options disappear below the popup edge.
    const positionRoleList = function () {
      if (!roleList.classList.contains("is-floating") || roleList.hidden) return;
      const buttonRect = roleButton.getBoundingClientRect();
      const listRect = roleList.getBoundingClientRect();
      const width = buttonRect.width;
      let left = buttonRect.left;
      let top = buttonRect.bottom + 6;
      left = Math.max(12, Math.min(left, window.innerWidth - width - 12));
      if (top + listRect.height > window.innerHeight - 12) {
        top = buttonRect.top - listRect.height - 6;
      }
      top = Math.max(12, Math.min(top, window.innerHeight - listRect.height - 12));
      roleList.style.left = left + "px";
      roleList.style.top = top + "px";
      roleList.style.width = width + "px";
    };

    const setRoleListOpen = function (open) {
      if (open) {
        document.body.appendChild(roleList);
        roleList.classList.add("is-floating");
        roleList.hidden = false;
        positionRoleList();
      } else {
        roleList.hidden = true;
        roleList.classList.remove("is-floating");
        roleList.style.left = "";
        roleList.style.top = "";
        roleList.style.width = "";
        rolePicker.appendChild(roleList);
      }
    };
    menu.__floatingRoleList = roleList;
    menu.__positionRoleList = positionRoleList;

    const roleDescription = function (role) {
      if (role.description) return role.description;
      if (menu.classList.contains("is-widget-colors")) {
        return str(
          "color_group_desc",
          "Changes the light and dark colors for this interface element."
        );
      }
      const descriptions = {
        font_widget_title: str("widget_titles_font_desc", "Changes the headings shown at the top of regular dashboard widgets."),
        font_widget_small: str("widget_text_font_desc", "Changes the supporting text inside regular dashboard widgets."),
        font_heatmap_title: str("heatmap_title_font_desc", "Changes the Activity heading in the Heatmap widget."),
        font_heatmap_labels: str("heatmap_labels_font_desc", "Changes the Heatmap navigation, streak, and calendar labels."),
        swidget_font_labels: str("stats_titles_font_desc", "Changes the Studied, Time, Pace, and Retention labels."),
        swidget_font_values: str("stats_labels_font_desc", "Changes the units and supporting labels in the four Stats Widgets."),
        swidget_font_numbers: str("stats_numbers_font_desc", "Changes the numeric figures in the four Stats Widgets."),
        font_profile_name: str("profile_name_font_desc", "Changes the profile name shown in the sidebar."),
        font_sidebar_small: str("profile_text_font_desc", "Changes supporting text within the sidebar profile."),
        font_action_buttons: str("action_buttons_font_desc", "Changes the labels of sidebar action buttons."),
        font_deck_title: str("deck_title_font_desc", "Changes the Decks heading in the sidebar."),
        font_deck_names: str("deck_names_font_desc", "Changes deck names in the sidebar list."),
        font_reviewer_controls: str("reviewer_controls_font_desc", "Changes the labels and supporting text inside the Reviewer bottom-bar buttons."),
        font_stats_labels: str("stats_titles_font_desc", "Changes the headings in the Deck Stats widget."),
        font_stats_values: str("stats_labels_font_desc", "Changes the values and supporting labels in the Deck Stats widget.")
      };
      return descriptions[role.id] || str("font_role_info_default", "Changes the font family and size for this part of the interface.");
    };

    const isStatsSizeSyncField = function (field) {
      return field && (
        field.id === "swidget_label_size_sync" ||
        field.id === "swidget_value_size_sync" ||
        field.id === "swidget_number_size_sync"
      );
    };

    function mountSizeSync(field) {
      syncSlot.innerHTML = "";
      syncSlot.hidden = !field;
      if (!field) return;
      const label = el("span", "osw-organize-font-sync-label", field.label);
      const button = el(
        "button",
        "osw-organize-font-sync-switch" + (values[field.id] ? " is-on" : "")
      );
      button.type = "button";
      button.setAttribute("role", "switch");
      button.setAttribute("aria-checked", values[field.id] ? "true" : "false");
      button.setAttribute("aria-label", field.label);
      button.addEventListener("click", function () {
        setValue(field.id, !values[field.id]);
        mountRole(activeCompactFontRole);
      });
      syncSlot.appendChild(label);
      syncSlot.appendChild(button);
    }

    function mountRole(roleId) {
      activeCompactFontRole = roleId;
      const role = roles.filter(function (item) { return item.id === roleId; })[0] || roles[0];
      roleLabel.textContent = role.title || "";
      roleButton.setAttribute("aria-expanded", "false");
      if (!isColorMenu) setRoleListOpen(false);
      Array.prototype.forEach.call(roleList.querySelectorAll("button"), function (item) {
        const selected = item.getAttribute("data-role-id") === role.id;
        item.classList.toggle("is-selected", selected);
        item.setAttribute("aria-selected", selected ? "true" : "false");
      });
      fieldsHost.innerHTML = "";
      infoText.textContent = roleDescription(role);
      infoText.hidden = infoBtn.getAttribute("aria-expanded") !== "true";
      const syncField = (role.field_ids || []).map(function (fieldId) {
        return fieldById[fieldId];
      }).filter(isStatsSizeSyncField)[0];
      mountSizeSync(syncField);
      (role.field_ids || []).forEach(function (fieldId) {
        const field = fieldById[fieldId];
        const renderer = field && FIELD_RENDERERS[field.type];
        if (
          !renderer || isStatsSizeSyncField(field) ||
          (field.showWhen && !showWhenMatches(field.showWhen))
        ) return;
        const node = renderer(field);
        node.classList.add("osw-organize-menu-field");
        node.setAttribute("data-field-host", field.id);
        fieldsHost.appendChild(node);
      });
      if (menu.__positionWithinViewport) {
        requestAnimationFrame(menu.__positionWithinViewport);
      }
    }
    roles.forEach(function (role) {
      const option = el(
        "button",
        "osw-organize-font-role-option" + (isColorMenu ? " osw-reviewer-color-card" : ""),
        isColorMenu ? "" : (role.title || "")
      );
      option.type = "button";
      option.setAttribute("role", isColorMenu ? "tab" : "option");
      option.setAttribute("data-role-id", role.id);
      if (isColorMenu) option.setAttribute("aria-label", role.title || "");
      if (isColorMenu) {
        const sample = el("span", "osw-reviewer-color-sample", role.preview_label || role.title || "");
        const caption = el("span", "osw-reviewer-color-caption", role.title || "");
        option.appendChild(sample);
        option.appendChild(caption);
        option.__paintColorGroupPreview = function () {
          const suffix = CTX.dark ? "dark" : "light";
          const bgKey = role.preview_bg ? role.preview_bg + "_" + suffix : "";
          const textKey = role.preview_text ? role.preview_text + "_" + suffix : "";
          const borderKey = role.preview_border ? role.preview_border + "_" + suffix : "";
          sample.style.background = (bgKey && values[bgKey]) || (CTX.dark ? "#3a3a3a" : "#f0f0f0");
          sample.style.color = (textKey && values[textKey]) || (CTX.dark ? "#f0f0f0" : "#2c2c2c");
          sample.style.borderColor = (borderKey && values[borderKey]) || "";
        };
        option.__paintColorGroupPreview();
      }
      option.addEventListener("click", function () { mountRole(role.id); });
      roleList.appendChild(option);
    });
    if (isColorMenu) {
      roleList.__syncColorGallery = function () {
        Array.prototype.forEach.call(roleList.querySelectorAll(".osw-reviewer-color-card"), function (item) {
          if (item.__paintColorGroupPreview) item.__paintColorGroupPreview();
        });
      };
    } else {
      roleButton.addEventListener("click", function () {
        const opened = roleButton.getAttribute("aria-expanded") === "true";
        roleButton.setAttribute("aria-expanded", opened ? "false" : "true");
        setRoleListOpen(!opened);
      });
    }
    infoBtn.addEventListener("click", function () {
      const opened = infoBtn.getAttribute("aria-expanded") === "true";
      infoBtn.setAttribute("aria-expanded", opened ? "false" : "true");
      infoText.hidden = opened;
      if (menu.__positionWithinViewport) {
        requestAnimationFrame(function () {
          menu.__positionWithinViewport();
          menu.__positionRoleList();
        });
      }
    });
    mountRole(activeCompactFontRole);

    document.body.appendChild(menu);
    compactFontMenuEl = menu;
    anchor.setAttribute("aria-expanded", "true");

    menu.__positionWithinViewport = function () {
      if (!menu.isConnected) return;
      const anchorRect = anchor.getBoundingClientRect();
      const menuRect = menu.getBoundingClientRect();
      let left = anchorRect.right - menuRect.width;
      let top = anchorRect.bottom + 8;
      left = Math.max(12, Math.min(left, window.innerWidth - menuRect.width - 12));
      if (top + menuRect.height > window.innerHeight - 12) {
        top = anchorRect.top - menuRect.height - 8;
      }
      top = Math.max(12, Math.min(top, window.innerHeight - menuRect.height - 12));
      menu.style.left = left + "px";
      menu.style.top = top + "px";
    };
    menu.__positionWithinViewport();
    compactFontMenuResizeHandler = function () {
      menu.__positionWithinViewport();
      menu.__positionRoleList();
    };
    window.addEventListener("resize", compactFontMenuResizeHandler);

    setTimeout(function () {
      compactFontMenuOutsideHandler = function (event) {
        const inFloatingRoleList = menu.__floatingRoleList &&
          menu.__floatingRoleList.contains(event.target);
        if (!menu.contains(event.target) && event.target !== anchor && !inFloatingRoleList) {
          closeCompactFontMenu();
        }
      };
      document.addEventListener("pointerdown", compactFontMenuOutsideHandler, true);
    }, 0);
  }

  function compactFontMenuButton(section) {
    const button = el("button", "osw-organize-reset-btn osw-organize-fonts-btn");
    button.type = "button";
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");
    const icon = el("span", "osw-organize-fonts-icon");
    icon.innerHTML = ICON_TYPE;
    button.appendChild(icon);
    button.appendChild(el("span", null, section.fontMenuLabel || str("stats_fonts", "Stats Fonts")));
    button.addEventListener("click", function () {
      if (compactFontMenuEl && compactFontMenuEl.__anchor === button) {
        closeCompactFontMenu();
      } else {
        openCompactFontMenu(button, section.fontRoles || [], section.fontMenuLabel || str("stats_fonts", "Stats Fonts"));
      }
    });
    return button;
  }

  function compactColorMenuButton(section) {
    const button = el("button", "osw-organize-reset-btn osw-organize-fonts-btn osw-organize-colors-btn");
    button.type = "button";
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-expanded", "false");
    const icon = el("span", "osw-organize-fonts-icon");
    icon.innerHTML = ICON_PALETTE;
    button.appendChild(icon);
    button.appendChild(el("span", null, section.colorMenuLabel || str("colors", "Colors")));
    button.addEventListener("click", function () {
      if (compactFontMenuEl && compactFontMenuEl.__anchor === button) {
        closeCompactFontMenu();
      } else {
        openCompactFontMenu(
          button,
          section.colorGroups || [],
          section.colorMenuLabel || str("colors", "Colors")
        );
      }
    });
    return button;
  }
  // Kept separate from the chrome icons above: Gallery's delete confirmation
  // explicitly uses Lucide's named check and X glyphs as its two choices.
  const LUCIDE_CHECK = '<svg class="lucide lucide-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>';
  const LUCIDE_X = '<svg class="lucide lucide-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>';
  const ICON_UNDO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M4 10h9a5 5 0 1 1 0 10H8"/>' +
    '<path d="M4 10l4-4M4 10l4 4"/></svg>';
  // Sidebar action-button order editor: drag affordance + show/archive state.
  const OSW_DRAG_HANDLE = '<svg viewBox="0 0 24 24" fill="currentColor">' +
    '<circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/>' +
    '<circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>';
  const OSW_EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/>' +
    '<circle cx="12" cy="12" r="2.6"/></svg>';
  const OSW_EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M4 4l16 16"/>' +
    '<path d="M9.6 5.7A9.6 9.6 0 0 1 12 5.5c6.4 0 10 6.5 10 6.5a17 17 0 0 1-2.6 3.4"/>' +
    '<path d="M6.3 7.9A17 17 0 0 0 2 12s3.6 6.5 10 6.5c1 0 1.9-.1 2.7-.4"/></svg>';
  const ICON_SWAP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13l-3-3M20 16H7l3 3"/></svg>';
  const ICON_LINK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/>' +
    '<path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>';
  const ICON_UNLINK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M17 7l3-3a5 5 0 0 1 0 7l-2 2"/>' +
    '<path d="M7 17l-3 3a5 5 0 0 1 0-7l2-2"/><path d="M3 3l18 18"/></svg>';

  let gallery = null;   // null when closed

  function galleryOpen() { return gallery !== null; }

  function openGallery(field, startRole) {
    if (settingsPicker) closeSettingsPicker();
    if (gallery) closeGallery();

    const targets = imageTargets(field);
    let active = 0;
    targets.forEach(function (target, index) {
      if (target.role === startRole) active = index;
    });

    const root = el("div", "osw-gal");
    const card = el("div", "osw-gal-card");
    root.appendChild(card);

    // Header: what is being picked, how to add more, how to get out.
    const head = el("div", "osw-gal-head");
    const titles = el("div", "osw-gal-titles");
    titles.appendChild(el("div", "osw-gal-title", field.label || str("gallery", "Gallery")));
    const count = el("div", "osw-gal-count");
    titles.appendChild(count);
    head.appendChild(titles);

    const importBtn = el("button", "osw-gal-import");
    importBtn.type = "button";
    const importIcon = el("span", "osw-gal-import-icon");
    importIcon.innerHTML = ICON_PLUS;
    importBtn.appendChild(importIcon);
    importBtn.appendChild(el("span", null, str("gallery_import", "Import image")));
    importBtn.addEventListener("click", runImport);
    head.appendChild(importBtn);

    const closeBtn = el("button", "osw-gal-close");
    closeBtn.type = "button";
    closeBtn.innerHTML = ICON_CLOSE;
    closeBtn.addEventListener("click", closeGallery);
    head.appendChild(closeBtn);
    card.appendChild(head);

    // Target strip. Only meaningful with two slots — with one there is nothing
    // to choose between, so the row is dropped rather than shown disabled.
    const strip = el("div", "osw-gal-targets");
    const targetNodes = [];
    if (targets.length > 1) {
      targets.forEach(function (target, index) {
        const chip = el("button", "osw-gal-target");
        chip.type = "button";
        chip.appendChild(el("span", "osw-gal-target-kbd", target.key));
        const body = el("span", "osw-gal-target-body");
        body.appendChild(el("span", "osw-gal-target-role", target.label));
        const nameNode = el("span", "osw-gal-target-name");
        body.appendChild(nameNode);
        chip.appendChild(body);
        chip.addEventListener("click", function () { setActive(index); });
        strip.appendChild(chip);
        targetNodes.push({ chip: chip, name: nameNode, target: target });
      });
      card.appendChild(strip);
    }

    const grid = el("div", "osw-gal-grid");
    card.appendChild(grid);

    const foot = el("div", "osw-gal-foot");
    foot.textContent = targets.length > 1
      ? str("gallery_hint_dynamic", "Click to set the highlighted slot — or hover an image and press L / D.")
      : str("gallery_hint_single", "Click an image to use it.");
    card.appendChild(foot);

    document.body.appendChild(root);

    gallery = {
      field: field, targets: targets, root: root, grid: grid, count: count,
      targetNodes: targetNodes, hovered: null, active: active, confirming: null
    };

    root.addEventListener("mousedown", function (event) {
      if (event.target === root) closeGallery();
    });
    document.addEventListener("keydown", onGalleryKey, true);

    paintGrid();
    paintTargets();
    refreshFromDisk();

    // ── behaviour ──

    function setActive(index) {
      gallery.active = index;
      paintTargets();
    }

    function paintTargets() {
      targetNodes.forEach(function (entry, index) {
        entry.chip.classList.toggle("is-active", index === gallery.active);
        const name = imageValue(field, entry.target);
        entry.name.textContent = name || field.emptyLabel || str("gallery_none", "None");
        entry.name.classList.toggle("is-empty", !name);
      });
    }

    function assign(name) {
      const target = targets[gallery.active] || targets[0];
      setValue(target.id, name || "");
      if (field.modeField) {
        setValue(field.modeField, name ? (field.modeValue || "custom") : (field.emptyMode || "color"));
      }
      // setValue -> syncField already repainted the preview; this only makes
      // sure it is showing the theme the picture was just assigned to.
      if (target.role === "light" || target.role === "dark") {
        setProfilePreviewMode(target.role);
      }
      paintTargets();
      paintSelection();
      // With a single slot the choice is complete the moment it is made, so
      // staying open would just be one more click to dismiss.
      if (targets.length === 1) closeGallery();
    }

    function assignToRole(role, name) {
      let index = -1;
      targets.forEach(function (target, i) { if (target.role === role) index = i; });
      if (index === -1) return false;
      gallery.active = index;
      setValue(targets[index].id, name || "");
      if (field.modeField) {
        setValue(field.modeField, name ? (field.modeValue || "custom") : (field.emptyMode || "color"));
      }
      setProfilePreviewMode(role);
      paintTargets();
      paintSelection();
      flashTarget(index);
      return true;
    }

    function flashTarget(index) {
      const entry = targetNodes[index];
      if (!entry) return;
      entry.chip.classList.remove("is-flash");
      // Reading offsetWidth restarts the animation; without it a second press
      // on the same key does nothing visible.
      void entry.chip.offsetWidth;
      entry.chip.classList.add("is-flash");
    }

    /* Selection is repainted rather than rebuilt: the grid holds live <img>
       elements, and swapping them out on every keypress would re-decode every
       thumbnail and make the L/D shortcuts feel heavy. */
    function paintSelection() {
      Array.prototype.forEach.call(grid.querySelectorAll(".osw-gal-tile"), function (tile) {
        const name = tile.getAttribute("data-name") || "";
        const badges = tile.querySelector(".osw-gal-badges");
        if (badges) badges.innerHTML = "";
        let selected = false;
        targets.forEach(function (target) {
          if (imageValue(field, target) !== name) return;
          selected = true;
          if (badges && target.key) badges.appendChild(el("span", "osw-gal-badge", target.key));
        });
        tile.classList.toggle("is-selected", selected);
      });
    }

    function paintGrid() {
      const images = galleryList(field.folder);
      grid.innerHTML = "";
      grid.classList.toggle("is-empty", !images.length);
      gallery.confirming = null;

      count.textContent = images.length === 1
        ? str("gallery_count_one", "1 image")
        : fmt(str("gallery_count", "{n} images"), { n: images.length });

      // "None" first: clearing a picture is a choice like any other, and
      // hiding it in a menu was the single most-asked-about gap in the old UI.
      // It is skipped on an empty folder, where "clear the selection" next to
      // "you have no images" is a tile that says nothing.
      if (images.length) {
        const none = el("button", "osw-gal-tile osw-gal-tile-none");
        none.type = "button";
        none.setAttribute("data-name", "");
        const noneThumb = el("span", "osw-gal-thumb");
        noneThumb.innerHTML = ICON_CLOSE;
        none.appendChild(noneThumb);
        none.appendChild(el("span", "osw-gal-name", field.emptyLabel || str("gallery_none", "None")));
        none.appendChild(el("span", "osw-gal-badges"));
        wireTile(none, "");
        grid.appendChild(none);
      }

      images.forEach(function (image) {
        const tile = el("button", "osw-gal-tile");
        tile.type = "button";
        tile.setAttribute("data-name", image.name);

        const thumb = el("span", "osw-gal-thumb");
        appendImageWithFallback(thumb, image.url);
        tile.appendChild(thumb);
        tile.appendChild(el("span", "osw-gal-name", image.name));
        tile.appendChild(el("span", "osw-gal-badges"));

        // ✕ removes the file. It asks first, in place: a modal confirmation on
        // top of a modal picker is heavier than the action deserves, but the
        // file is gone for good, so it cannot be a single stray click either.
        const del = el("span", "osw-gal-del");
        del.setAttribute("role", "button");
        del.innerHTML = ICON_CLOSE;
        del.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          askDelete(tile, image.name);
        });
        tile.appendChild(del);

        const confirm = el("span", "osw-gal-confirm");
        confirm.appendChild(el("span", "osw-gal-confirm-text", str("gallery_delete_ask", "Delete?")));
        const yes = el("span", "osw-gal-confirm-yes");
        yes.setAttribute("role", "button");
        yes.innerHTML = ICON_CHECK;
        yes.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          runDelete(image.name);
        });
        const no = el("span", "osw-gal-confirm-no");
        no.setAttribute("role", "button");
        no.innerHTML = ICON_CLOSE;
        no.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          clearConfirm();
        });
        confirm.appendChild(yes);
        confirm.appendChild(no);
        tile.appendChild(confirm);

        wireTile(tile, image.name);
        grid.appendChild(tile);
      });

      if (!images.length) {
        const empty = el("div", "osw-gal-empty");
        const icon = el("div", "osw-gal-empty-icon");
        icon.innerHTML = ICON_IMAGE;
        empty.appendChild(icon);
        empty.appendChild(el("div", "osw-gal-empty-title", str("gallery_empty_title", "No images yet")));
        empty.appendChild(el("div", "osw-gal-empty-desc",
          str("gallery_empty_desc", "Import a picture to start your gallery.")));
        grid.appendChild(empty);
      }

      paintSelection();
    }

    function wireTile(tile, name) {
      tile.addEventListener("click", function () {
        if (tile.classList.contains("is-confirming")) return;
        bridge("osw:haptic:1");
        assign(name);
      });
      tile.addEventListener("mouseenter", function () { gallery.hovered = name; });
      tile.addEventListener("focus", function () { gallery.hovered = name; });
      tile.addEventListener("mouseleave", function () {
        if (gallery && gallery.hovered === name) gallery.hovered = null;
      });
    }

    function askDelete(tile, name) {
      clearConfirm();
      gallery.confirming = name;
      tile.classList.add("is-confirming");
    }

    function clearConfirm() {
      if (!gallery) return;
      gallery.confirming = null;
      Array.prototype.forEach.call(grid.querySelectorAll(".is-confirming"), function (node) {
        node.classList.remove("is-confirming");
      });
    }

    function runDelete(name) {
      clearConfirm();
      call("osw:gallery_delete:" + JSON.stringify({ folder: field.folder, name: name }))
        .then(function (res) {
          if (!res || !res.ok) {
            toast((res && res.error) || str("autosave_error", "Could not save"));
            return;
          }
          setGalleryList(field.folder, res.images);
          // Python already blanked whatever pointed at the file, so these are
          // applied locally without echoing a patch back at it.
          (res.cleared || []).forEach(function (id) { applyExternalValue(id, ""); });
          if (gallery) { paintGrid(); paintTargets(); }
          refreshImageFields();
          updateProfilePreview();
          toast(fmt(str("gallery_deleted", "“{name}” deleted"), { name: name }));
        });
    }

    function runImport() {
      importBtn.classList.add("is-busy");
      call("osw:gallery_import:" + JSON.stringify({ folder: field.folder }))
        .then(function (res) {
          importBtn.classList.remove("is-busy");
          if (!res || !res.ok) {
            if (res && res.error) toast(res.error);
            return;
          }
          setGalleryList(field.folder, res.images);
          if (gallery) paintGrid();
          refreshImageFields();
          // Importing is always in service of using the picture, so the first
          // new file lands in the active slot straight away.
          const added = res.added || [];
          if (added.length && gallery) {
            assign(added[0]);
            if (gallery) paintGrid();
          }
        });
    }

    function refreshFromDisk() {
      call("osw:gallery_list:" + JSON.stringify({ folder: field.folder }))
        .then(function (res) {
          // A reply carrying no list is not an empty folder: adopting it
          // would blank a grid that is currently showing the right thing.
          if (!res || !res.ok || !gallery || !Array.isArray(res.images)) return;
          const before = JSON.stringify(galleryList(field.folder).map(function (i) { return i.name; }));
          const after = JSON.stringify((res.images || []).map(function (i) { return i.name; }));
          setGalleryList(field.folder, res.images);
          // Only rebuild when the folder actually differs, so the usual case
          // (nothing changed since the page loaded) never flickers.
          if (before !== after) { paintGrid(); refreshImageFields(); }
        });
    }

    function onGalleryKey(event) {
      if (!gallery) return;
      const key = (event.key || "").toLowerCase();
      if (key === "escape") {
        event.preventDefault();
        event.stopPropagation();
        if (gallery.confirming) { clearConfirm(); return; }
        closeGallery();
        return;
      }
      if (key === "l" || key === "d") {
        if (targets.length < 2) return;
        // Nothing is being pointed at, so there is nothing to assign; let the
        // keystroke through rather than swallowing it silently.
        if (gallery.hovered === null) return;
        if (event.metaKey || event.ctrlKey || event.altKey) return;
        event.preventDefault();
        event.stopPropagation();
        bridge("osw:haptic:1");
        assignToRole(key === "l" ? "light" : "dark", gallery.hovered);
        return;
      }
      if (key === "tab" && targets.length > 1) {
        event.preventDefault();
        event.stopPropagation();
        setActive((gallery.active + 1) % targets.length);
      }
    }

    gallery.onKey = onGalleryKey;
  }

  function closeGallery() {
    if (!gallery) return;
    const root = gallery.root;
    document.removeEventListener("keydown", gallery.onKey, true);
    // Dropped from `gallery` first: from here on the popover is closed as far
    // as the rest of the page is concerned, whatever the fade is still doing.
    gallery = null;
    root.classList.add("is-closing");
    root.style.pointerEvents = "none";
    setTimeout(function () {
      if (root.parentNode) root.parentNode.removeChild(root);
    }, 150);
  }

  // ── font and colour pickers ───────────────────────────────────────────────
  //
  // Keep these choices inside the WebView, alongside the Icon Picker. The old
  // bridge commands opened separate Qt windows, which meant the three related
  // settings controls each had a different visual language and focus model.
  let settingsPicker = null;
  let activeTileMenuClose = null;

  function closeSettingsPicker() {
    if (!settingsPicker) return;
    const root = settingsPicker.root;
    document.removeEventListener("keydown", settingsPicker.onKey, true);
    settingsPicker = null;
    root.classList.add("is-closing");
    root.style.pointerEvents = "none";
    setTimeout(function () {
      if (root.parentNode) root.parentNode.removeChild(root);
    }, 150);
  }

  function openPickerShell(title) {
    closeSettingsPicker();
    // A font field can be launched from Widget Fonts' compact editor. That
    // editor is an anchored popover, not a modal, so leaving it open would
    // place it over the new full-screen picker (and create two simultaneous
    // editing surfaces). Every full picker owns focus exclusively.
    closeCompactFontMenu();
    if (activeTileMenuClose) activeTileMenuClose();
    if (iconPicker) closeIconPicker();
    if (gallery) closeGallery();

    const root = el("div", "osw-gal");
    const modal = el("section", "onigiri-icon-modal osw-iconpick-modal osw-settings-picker");
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", title);
    root.appendChild(modal);

    const header = el("div", "onigiri-icon-modal-header");
    header.appendChild(el("div", "onigiri-icon-modal-title", title));
    const close = el("button", "onigiri-icon-modal-close");
    close.type = "button";
    close.setAttribute("aria-label", str("cancel", "Cancel"));
    close.innerHTML = ICON_CLOSE;
    close.addEventListener("click", closeSettingsPicker);
    header.appendChild(close);
    modal.appendChild(header);

    const body = el("div", "osw-settings-picker-body");
    modal.appendChild(body);
    document.body.appendChild(root);
    root.addEventListener("mousedown", function (event) {
      if (event.target === root) closeSettingsPicker();
    });
    return { root: root, modal: modal, body: body };
  }

  function rgbToHsv(red, green, blue) {
    const r = red / 255;
    const g = green / 255;
    const b = blue / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    let hue = 0;
    if (delta) {
      if (max === r) hue = 60 * (((g - b) / delta) % 6);
      else if (max === g) hue = 60 * (((b - r) / delta) + 2);
      else hue = 60 * (((r - g) / delta) + 4);
    }
    if (hue < 0) hue += 360;
    return [hue, max ? delta / max : 0, max];
  }

  function hsvToHex(hue, saturation, value) {
    const chroma = value * saturation;
    const segment = (hue / 60) % 6;
    const x = chroma * (1 - Math.abs((segment % 2) - 1));
    const m = value - chroma;
    const channels = segment < 1 ? [chroma, x, 0] : segment < 2 ? [x, chroma, 0] :
      segment < 3 ? [0, chroma, x] : segment < 4 ? [0, x, chroma] :
      segment < 5 ? [x, 0, chroma] : [chroma, 0, x];
    return rgbToHex(
      Math.round((channels[0] + m) * 255),
      Math.round((channels[1] + m) * 255),
      Math.round((channels[2] + m) * 255)
    );
  }

  function preserveColorAlpha(original, hex) {
    const value = String(original || "").trim();
    const rgbaMatch = /^rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([^)]+)\)$/i.exec(value);
    if (rgbaMatch) {
      const rgb = hexToRgb(hex);
      return "rgba(" + rgb[0] + ", " + rgb[1] + ", " + rgb[2] + ", " + rgbaMatch[1].trim() + ")";
    }
    // Qt's #AARRGGBB format is used by a few chip colour fields. Retain its
    // alpha byte while changing the RGB portion, exactly as the native picker
    // did before this modal replaced it.
    if (/^#[0-9a-f]{8}$/i.test(value)) return value.slice(0, 3) + hex.slice(1);
    return hex;
  }

  function openColorPickerById(fieldId, current, restoreTo, canRestore) {
    const field = fieldById[fieldId];
    if (field) openColorPicker(field, current == null ? values[fieldId] : current, restoreTo, canRestore);
  }

  function mountColorEditor(host, initial, onChange) {
    let hex = cssColorToHex(initial);
    if (!/^#[0-9a-f]{6}$/i.test(hex)) hex = "#00A982";
    let rgb = hexToRgb(hex);
    let hsv = rgbToHsv(rgb[0], rgb[1], rgb[2]);
    const canvas = el("div", "osw-colorpick-sv");
    const cursor = el("span", "osw-colorpick-cursor");
    canvas.appendChild(cursor);
    const hue = document.createElement("input");
    hue.type = "range";
    hue.min = "0";
    hue.max = "360";
    hue.className = "osw-colorpick-hue";
    hue.setAttribute("aria-label", "Hue");
    const valueSlider = document.createElement("input");
    valueSlider.type = "range";
    valueSlider.min = "0";
    valueSlider.max = "100";
    valueSlider.className = "osw-colorpick-value";
    valueSlider.setAttribute("aria-label", str("color_clarity", "Color clarity"));
    const entry = el("label", "osw-colorpick-entry");
    const preview = el("span", "osw-colorpick-preview");
    const hexInput = document.createElement("input");
    hexInput.type = "text";
    hexInput.maxLength = 7;
    hexInput.spellcheck = false;
    hexInput.setAttribute("aria-label", "Hex color");
    entry.appendChild(preview);
    entry.appendChild(hexInput);
    host.appendChild(canvas);
    host.appendChild(valueSlider);
    host.appendChild(hue);
    host.appendChild(entry);

    function paint() {
      hex = hsvToHex(hsv[0], hsv[1], hsv[2]);
      canvas.style.setProperty("--osw-picker-hue", hsv[0]);
      cursor.style.left = (hsv[1] * 100) + "%";
      cursor.style.top = ((1 - hsv[2]) * 100) + "%";
      hue.value = String(Math.round(hsv[0]));
      valueSlider.value = String(Math.round(hsv[2] * 100));
      preview.style.background = hex;
      hexInput.value = hex.toUpperCase();
      if (onChange) onChange(hex);
    }
    function updateFromPoint(event) {
      const rect = canvas.getBoundingClientRect();
      hsv[1] = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      hsv[2] = 1 - Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
      paint();
    }
    canvas.addEventListener("pointerdown", function (event) {
      canvas.setPointerCapture(event.pointerId);
      updateFromPoint(event);
    });
    canvas.addEventListener("pointermove", function (event) {
      if (canvas.hasPointerCapture(event.pointerId)) updateFromPoint(event);
    });
    hue.addEventListener("input", function () { hsv[0] = Number(hue.value); paint(); });
    valueSlider.addEventListener("input", function () {
      hsv[2] = Number(valueSlider.value) / 100;
      paint();
    });
    hexInput.addEventListener("change", function () {
      const typed = String(hexInput.value || "").trim();
      const next = /^#?[0-9a-f]{6}$/i.test(typed)
        ? (typed[0] === "#" ? typed : "#" + typed) : "";
      if (!next) { paint(); return; }
      rgb = hexToRgb(next);
      hsv = rgbToHsv(rgb[0], rgb[1], rgb[2]);
      paint();
    });
    paint();
    return { value: function () { return hex; }, input: hexInput };
  }

  function openColorPicker(field, initial, restoreTo, canRestore) {
    const shell = openPickerShell(field.label || str("color", "Color"));
    shell.modal.classList.add("osw-colorpick-modal");
    const original = String(initial || "");
    const editor = mountColorEditor(shell.body, original);
    const footer = el("div", "osw-settings-picker-footer");
    const defaultColor = restoreTo === undefined ? field.default : restoreTo;
    const restoreAvailable = canRestore === undefined
      ? defaultColor != null && String(values[field.id] || "") !== String(defaultColor)
      : canRestore;
    let restore = null;
    if (restoreAvailable) {
      restore = el("button", "osw-settings-picker-btn osw-colorpick-restore", str("restore_default", "Restore default"));
      restore.type = "button";
      installResetHold(restore, function () {
        setValue(field.id, defaultColor == null ? "" : defaultColor);
        closeSettingsPicker();
      });
      footer.appendChild(restore);
    }
    const save = el("button", "osw-settings-picker-btn is-primary", str("save", "Save"));
    const cancel = el("button", "osw-settings-picker-btn", str("cancel", "Cancel"));
    save.type = cancel.type = "button";
    footer.appendChild(save);
    footer.appendChild(cancel);
    shell.modal.appendChild(footer);

    save.addEventListener("click", function () {
      setValue(field.id, preserveColorAlpha(original, editor.value()));
      closeSettingsPicker();
    });
    cancel.addEventListener("click", closeSettingsPicker);

    const onKey = function (event) {
      if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); closeSettingsPicker(); }
    };
    settingsPicker = { root: shell.root, onKey: onKey };
    document.addEventListener("keydown", onKey, true);
    editor.input.focus();
  }

  function fontFieldColor(vals, fieldId, isDark) {
    const field = fieldById[fieldId];
    const colors = field && field.colorFields || [];
    const target = colors.length > 1 ? colors[isDark ? 1 : 0] : colors[0];
    return target ? vals[target.id] || "" : "";
  }

  function openFontPicker(field) {
    const shell = openPickerShell(field.label || str("fonts", "Fonts"));
    shell.modal.classList.add("osw-fontpick-modal");
    let selected = values[field.id] || field.default || "system";
    const colors = field.colorFields || [];
    const drafts = {};
    colors.forEach(function (target) { drafts[target.id] = values[target.id] || ""; });
    let colorIndex = colors.length > 1 && CTX.dark ? 1 : 0;
    let colorPopover = null;
    const search = document.createElement("input");
    search.className = "onigiri-icon-search osw-fontpick-search";
    search.placeholder = str("search", "Search fonts");
    search.setAttribute("aria-label", str("search", "Search fonts"));
    const grid = el("div", "osw-fontpick-grid");
    shell.body.appendChild(search);
    shell.body.appendChild(grid);

    // The same always-visible swatch row as the icon picker, below the list.
    // Its editor stays inside this picker, retaining the font/color drafts.
    const colorStack = el("div", "onigiri-icon-color-stack osw-fontpick-color-stack");
    const slotsRow = el("div", "onigiri-icon-color-slots");
    colorStack.appendChild(slotsRow);
    if (colors.length) shell.modal.appendChild(colorStack);

    function effectiveColor(index) {
      const target = colors[index];
      const isDark = colors.length > 1 ? index === 1 : !!CTX.dark;
      const fallback = isDark ? "#f1f2f4" : "#202124";
      if (!target) return fallback;
      const colorField = fieldById[target.id];
      return drafts[target.id] || (colorField && colorField.default) ||
        values[isDark ? "theme_fg_dark" : "theme_fg_light"] || fallback;
    }
    function paint() {
      const filter = String(search.value || "").trim().toLowerCase();
      grid.innerHTML = "";
      (field.options || []).filter(function (option) {
        return !filter || String(option.label || "").toLowerCase().indexOf(filter) !== -1;
      }).forEach(function (option) {
        const cell = el("button", "osw-fontpick-cell" + (option.value === selected ? " selected" : ""));
        cell.type = "button";
        cell.setAttribute("aria-pressed", option.value === selected ? "true" : "false");
        const name = el("span", "osw-fontpick-name", option.label || option.value);
        const sample = el("span", "osw-fontpick-sample", "Onigiri");
        if (option.family) sample.style.fontFamily = option.family;
        const ink = drafts[(colors[CTX.dark && colors.length > 1 ? 1 : 0] || {}).id];
        if (ink) sample.style.color = cssColorToHex(ink);
        cell.appendChild(name);
        cell.appendChild(sample);
        if (option.value === selected) {
          const check = el("span", "osw-fontpick-check");
          check.innerHTML = ICON_CHECK;
          cell.appendChild(check);
        }
        cell.addEventListener("click", function () { selected = option.value; paint(); });
        grid.appendChild(cell);
      });
    }
    function paintColorSlots() {
      slotsRow.innerHTML = "";
      colors.forEach(function (target, index) {
        const shown = effectiveColor(index);
        const slot = el("button", "onigiri-icon-color-slot" + (!drafts[target.id] ? " is-default" : ""));
        slot.type = "button";
        slot.setAttribute("aria-label", target.label + " " + str("color", "Color"));
        slot.setAttribute("aria-expanded", colorPopover && index === colorIndex ? "true" : "false");
        const swatch = el("span", "onigiri-icon-color-swatch");
        swatch.style.background = cssColorToHex(shown);
        slot.appendChild(swatch);
        const meta = el("span", "onigiri-icon-color-meta");
        const role = el("span", "onigiri-icon-color-role");
        if (colors.length > 1) role.innerHTML = index === 1 ? OSW_MOON_ICON : OSW_SUN_ICON;
        role.appendChild(document.createTextNode(target.label));
        meta.appendChild(role);
        meta.appendChild(el("span", "onigiri-icon-color-hex", String(cssColorToHex(shown)).toUpperCase()));
        slot.appendChild(meta);
        slot.addEventListener("click", function () {
          if (colorPopover && colorIndex === index) { closeColorEditor(); return; }
          colorIndex = index;
          openColorEditor();
        });
        slotsRow.appendChild(slot);
      });
    }
    function closeColorEditor(restoreFocus) {
      if (colorPopover) colorPopover.remove();
      colorPopover = null;
      paintColorSlots();
      if (restoreFocus && slotsRow.children[colorIndex]) slotsRow.children[colorIndex].focus();
    }
    function openColorEditor() {
      closeColorEditor();
      const target = colors[colorIndex];
      const original = drafts[target.id];
      colorPopover = el("div", "osw-fontpick-color-popover");
      colorPopover.setAttribute("role", "group");
      colorPopover.setAttribute("aria-label", target.label + " " + str("color", "Color"));
      const head = el("div", "osw-fontpick-color-head");
      const sample = el("span", "osw-fontpick-color-sample", "Onigiri");
      sample.style.background = (colors.length > 1 ? colorIndex === 1 : CTX.dark) ? "#202020" : "#f7f7f6";
      sample.style.color = cssColorToHex(effectiveColor(colorIndex));
      sample.style.fontFamily = designerFieldFontFamily(Object.assign({}, values, { [field.id]: selected }), field.id);
      head.appendChild(sample);
      const close = el("button", "onigiri-icon-modal-close");
      close.type = "button";
      close.setAttribute("aria-label", str("close", "Close"));
      close.innerHTML = ICON_CLOSE;
      close.addEventListener("click", function () { closeColorEditor(true); });
      head.appendChild(close);
      colorPopover.appendChild(head);
      const editorHost = el("div", "osw-fontpick-color-editor");
      colorPopover.appendChild(editorHost);
      let ready = false;
      const editor = mountColorEditor(editorHost, effectiveColor(colorIndex), function (hex) {
        if (!ready) return;
        drafts[target.id] = preserveColorAlpha(original, hex);
        sample.style.color = hex;
        paintColorSlots();
        paint();
      });
      ready = true;
      const restore = el("button", "osw-settings-picker-btn", str("restore_default", "Restore default"));
      restore.type = "button";
      restore.addEventListener("click", function () {
        drafts[target.id] = fieldById[target.id].default || "";
        paint();
        openColorEditor();
      });
      colorPopover.appendChild(restore);
      colorStack.appendChild(colorPopover);
      paintColorSlots();
      editor.input.focus();
    }
    shell.modal.addEventListener("mousedown", function (event) {
      if (colorPopover && !colorPopover.contains(event.target) && !slotsRow.contains(event.target)) closeColorEditor();
    });
    const footer = el("div", "osw-settings-picker-footer");
    const save = el("button", "osw-settings-picker-btn is-primary", str("save", "Save"));
    const cancel = el("button", "osw-settings-picker-btn", str("cancel", "Cancel"));
    const reset = el("button", "osw-settings-picker-btn", str("use_default", "Use Default"));
    save.type = cancel.type = reset.type = "button";
    footer.appendChild(save);
    footer.appendChild(cancel);
    footer.appendChild(reset);
    shell.modal.appendChild(footer);
    search.addEventListener("input", paint);
    function commit(font, colorValues) {
      deferringPreviewRefresh = true;
      try {
        setValue(field.id, font);
        if (field.colorDynamicField && colors.length > 1 &&
            colorValues[colors[1].id] && colorValues[colors[1].id] !== values[colors[1].id]) {
          setValue(field.colorDynamicField, true);
        }
        colors.forEach(function (target) {
          if (String(values[target.id] || "") !== String(colorValues[target.id] || "")) {
            setValue(target.id, colorValues[target.id]);
          }
        });
      } finally { deferringPreviewRefresh = false; }
      refreshSettingsPreviews();
      closeSettingsPicker();
    }
    save.addEventListener("click", function () { commit(selected, drafts); });
    installResetHold(reset, function () {
      const defaults = {};
      colors.forEach(function (target) { defaults[target.id] = fieldById[target.id].default || ""; });
      commit(field.default || "system", defaults);
    }, { title: str("use_default", "Use Default") });
    cancel.addEventListener("click", closeSettingsPicker);
    const onKey = function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (colorPopover) closeColorEditor(true);
        else closeSettingsPicker();
      }
    };
    settingsPicker = { root: shell.root, onKey: onKey };
    document.addEventListener("keydown", onKey, true);
    paintColorSlots();
    paint();
    search.focus();
  }

  // ── icon popover ───────────────────────────────────────────────────────────
  //
  // The old chip opened a native Qt IconPickerDialog over the bridge
  // (settings/_icon_picker.py) — a second modal on top of this one, and one
  // that was opening empty. Same visual language as the deck browser's own
  // "Edit Icon" popover (web/icon_modal.js: onigiri-icon-* classes) so the two
  // pickers read as one design, wired to this dialog's own bridge/setValue
  // instead of pycmd/a deckId.
  //
  // A field can list companion colour fields (its icon's own tint, an empty-
  // state tint, ...): those render inside this same popover, under the grid,
  // instead of as separate rows in the deck — the icon and the colours that
  // paint it are one decision, not two.
  const ICON_POPUP_COMPANIONS = {
    modern_menu_profile_picture_icon: ["modern_menu_profile_picture_icon_color"],
    heatmapShape: ["heatmap_color", "heatmap_color_zero"],
    heatmapStreakIcon: ["heatmapStreakIconColor", "heatmapStreakIconZeroColor"],
    swidget_icon_studied: ["swidget_color_studied"],
    swidget_icon_time: ["swidget_color_time"],
    swidget_icon_pace: ["swidget_color_pace"],
    swidget_icon_retention: ["swidget_color_retention"],
    swidget_icon_retention_star: ["swidget_color_retention_star", "swidget_color_retention_star_empty"]
  };

  // Sidebar: an action button's tint belongs to the glyph it paints, so it
  // lives in that glyph's popover rather than as its own colour row — which is
  // where the legacy right-click "customize" menu put it too. (The markers are
  // NOT listed here: their cards show the colour directly next to the glyph.)
  ["add", "browse", "stats", "sync", "settings", "gamification", "more",
   "get_shared", "create_deck", "import_file",
   // Deck-list glyphs too: same key, and patcher.generate_icon_css paints them
   // with it (falling back to --icon-color / --icon-color-filtered when unset).
   "folder", "deck", "subdeck", "filtered_deck", "options",
   "collapse_closed", "collapse_open"].forEach(function (key) {
    ICON_POPUP_COMPANIONS["modern_menu_icon_" + key] = ["modern_menu_icon_color_" + key];
  });

  // Ready-to-Go follows the same model: every shortcut owns its glyph and
  // its tint in one picker, instead of separating the two decisions in the
  // settings deck.
  ["inbox", "warm_up", "today", "cool_down"].forEach(function (key) {
    ICON_POPUP_COMPANIONS["modern_menu_icon_ready_" + key] = [
      "modern_menu_icon_color_ready_" + key
    ];
  });

  let iconPicker = null; // null when closed
  let userIcons = (CTX.iconPicker || []).filter(function (i) { return !i.system; });
  const systemIcons = (CTX.iconPicker || []).filter(function (i) { return i.system; });

  function iconPickerOpen() { return iconPicker !== null; }

  function iconAssetLabel(name) {
    const base = name.indexOf("system:") === 0 ? name.slice(7) : name;
    return base.replace(/\.(svg|png)$/i, "").replace(/[-_]/g, " ");
  }

  function openIconPicker(field) {
    if (settingsPicker) closeSettingsPicker();
    if (iconPicker) closeIconPicker();
    if (galleryOpen()) closeGallery();

    const companionIds = ICON_POPUP_COMPANIONS[field.id] || [];

    const root = el("div", "osw-gal");
    const modal = el("div", "onigiri-icon-modal osw-iconpick-modal");
    root.appendChild(modal);

    const header = el("div", "onigiri-icon-modal-header");
    header.appendChild(el("div", "onigiri-icon-modal-title", field.label || str("icon", "Icon")));
    const closeBtn = el("span", "onigiri-icon-modal-close");
    closeBtn.innerHTML = ICON_CLOSE;
    closeBtn.addEventListener("click", closeIconPicker);
    header.appendChild(closeBtn);
    modal.appendChild(header);

    const tabs = el("div", "onigiri-icon-tabs");
    const iconsTab = el("span", "onigiri-icon-tab active", str("icons", "Icons"));
    const uploadTab = el("span", "onigiri-icon-tab", str("upload", "Upload"));
    tabs.appendChild(iconsTab);
    tabs.appendChild(uploadTab);
    modal.appendChild(tabs);

    const body = el("div", "onigiri-icon-body");
    const iconsPane = el("div", "onigiri-icon-pane active");
    const searchRow = el("div", "onigiri-icon-search-row");
    const search = document.createElement("input");
    search.className = "onigiri-icon-search";
    search.placeholder = str("search_icons", "Search icons");
    searchRow.appendChild(search);
    iconsPane.appendChild(searchRow);
    const gridWrap = el("div", "onigiri-icon-grid-wrap");
    const grid = el("div", "onigiri-icon-grid");
    gridWrap.appendChild(grid);
    iconsPane.appendChild(gridWrap);
    body.appendChild(iconsPane);

    const uploadPane = el("div", "onigiri-icon-pane");
    [
      { label: str("upload_svg", "Upload SVG icon"), kind: "svg" },
      { label: str("upload_png", "Upload PNG image"), kind: "png" }
    ].forEach(function (opt) {
      const btn = el("span", "onigiri-icon-upload", opt.label);
      btn.addEventListener("click", function () { runUpload(opt.kind, btn); });
      uploadPane.appendChild(btn);
    });
    body.appendChild(uploadPane);
    modal.appendChild(body);

    function setTab(name) {
      iconsTab.classList.toggle("active", name === "icons");
      uploadTab.classList.toggle("active", name === "upload");
      iconsPane.classList.toggle("active", name === "icons");
      uploadPane.classList.toggle("active", name === "upload");
      // Same rule as the deck browser's Edit Icon modal: the colour section
      // is about the icon itself, so it only makes sense next to the grid.
      const stack = modal.querySelector(".onigiri-icon-color-stack");
      if (stack) stack.style.display = name === "icons" ? "" : "none";
    }
    iconsTab.addEventListener("click", function () { setTab("icons"); });
    uploadTab.addEventListener("click", function () { setTab("upload"); });

    /* The field's own companion colour (e.g. Heatmap Shape's "Color") stands
       in for the icon's actual paint colour — every tile tints to it instead
       of a flat neutral grey, so the grid previews what the icon will really
       look like, not just its silhouette. Read live rather than captured once:
       the colour can be changed while the popover is open, and the grid has to
       follow it (retintIconGrid below). An unset tint resolves to the colour it
       inherits, which is what the icon is actually painted with. */
    function currentTint() {
      if (!companionIds.length) return "";
      const primary = fieldById[companionIds[0]];
      if (!primary) return "";
      if (primary.type === "color_pair") {
        const targets = imageTargets(primary);
        const target = targets.find(function (item) {
          return item.role === (CTX.dark ? "dark" : "light");
        }) || targets[0];
        return imageValue(primary, target) || pairColorFallback(primary, target);
      }
      return values[primary.id] || iconColorFallback(primary);
    }

    if (companionIds.length) {
      // Heatmap's cell colour is one decision shared by both Dynamic Mode
      // (its own) and Sync with Widgets (Widget Color and Effect's, when
      // synced) — neither is a plain boolean field the pair can bind to
      // directly, so the effective on/off is resolved here and stashed on
      // the shared virtual dynamic field the pair actually reads.
      if (field.id === "heatmapShape" || field.id === "heatmapStreakIcon") {
        const widgetDynamic = designerDynamicOn(["onigiri_canvas_inset_color_theme_mode"]);
        const effectiveDynamic = values["heatmap_sync_box_effect"] !== false
          ? widgetDynamic
          : values["heatmap_dynamic"] !== false;
        values["heatmap_color_dynamic_virtual"] = effectiveDynamic;
        // pairLinked() falls back to "are the light/dark values equal" when
        // there's no explicit theme_mode on record — heatmap_color's own
        // light/dark defaults happen to start equal, which would read as
        // linked even with dynamic on. Force the explicit choice instead of
        // leaving it to that inference.
        const mode = effectiveDynamic ? "separate" : "single";
        values["heatmap_color_theme_mode"] = mode;
        values["heatmap_color_zero_theme_mode"] = mode;
      }
      const colorStack = el("div", "onigiri-icon-color-stack");
      companionIds.forEach(function (id) {
        const cf = fieldById[id];
        if (!cf) return;
        colorStack.appendChild(renderIconPopupColorSlots(cf));
      });
      modal.appendChild(colorStack);
    }

    document.body.appendChild(root);
    iconPicker = {
      field: field,
      root: root,
      // Called after the companion colour changes (renderIconPopupColorSlots'
      // paint), so the whole grid moves to the new colour instead of showing
      // the old one until the popover is reopened.
      retint: function () {
        const tint = currentTint();
        Array.prototype.forEach.call(root.querySelectorAll(".onigiri-icon-mask"), function (node) {
          node.style.backgroundColor = tint || "";
        });
      }
    };

    root.addEventListener("mousedown", function (event) { if (event.target === root) closeIconPicker(); });
    document.addEventListener("keydown", onIconPickerKey, true);

    search.addEventListener("input", function () { paintIconGrid(search.value.trim().toLowerCase()); });
    paintIconGrid("");

    function buildTile(item) {
      const tile = el("button", "onigiri-icon-cell");
      tile.type = "button";
      tile.title = iconAssetLabel(item.name);
      tile.setAttribute("data-name", item.name);
      const thumb = el("span", "onigiri-icon-mask");
      thumb.style.webkitMaskImage = "url('" + item.url + "')";
      thumb.style.maskImage = "url('" + item.url + "')";
      const tint = currentTint();
      if (tint) thumb.style.backgroundColor = tint;
      tile.appendChild(thumb);
      if (!item.system) {
        const del = el("span", "onigiri-icon-delete");
        del.innerHTML = ICON_CLOSE;
        del.addEventListener("click", function (event) {
          event.stopPropagation();
          runDelete(item.name);
        });
        tile.appendChild(del);
      }
      tile.classList.toggle("selected", values[field.id] === item.name);
      tile.addEventListener("click", function () { assign(item.name); });
      return tile;
    }

    function buildNoneTile() {
      const none = el("button", "onigiri-icon-cell onigiri-icon-cell-none");
      none.type = "button";
      none.title = str("gallery_none", "None");
      none.innerHTML = ICON_CLOSE;
      none.classList.toggle("selected", !values[field.id]);
      none.addEventListener("click", function () { assign(""); });
      return none;
    }

    function paintIconGrid(filter) {
      grid.innerHTML = "";
      // One flat grid, no section labels: user icons first, then system
      // icons. None is the first tile rather than a control bolted on above
      // the grid — it reads as one of the choices in the list.
      if (!filter) grid.appendChild(buildNoneTile());
      userIcons.concat(systemIcons)
        .filter(function (item) { return !filter || iconAssetLabel(item.name).indexOf(filter) !== -1; })
        .forEach(function (item) { grid.appendChild(buildTile(item)); });
    }

    function assign(name) {
      setValue(field.id, name || "");
      Array.prototype.forEach.call(grid.querySelectorAll(".onigiri-icon-cell"), function (tile) {
        tile.classList.toggle("selected", (tile.getAttribute("data-name") || "") === name);
      });
      // With companion colours the popover stays open — picking a shape and
      // then tuning its colour is one visit, not two. With none, the choice
      // is complete the moment it is made.
      if (!companionIds.length) closeIconPicker();
    }

    function runUpload(kind, btn) {
      btn.classList.add("is-busy");
      call("osw:icon_import:" + kind).then(function (res) {
        btn.classList.remove("is-busy");
        if (!res || !res.ok) {
          if (res && res.error) toast(res.error);
          return;
        }
        userIcons = (res.icons || []).map(function (i) { return { name: i.name, url: i.url, system: false }; });
        setTab("icons");
        const added = res.added || [];
        paintIconGrid(search.value.trim().toLowerCase());
        if (added.length) assign(added[0]);
      });
    }

    function runDelete(name) {
      call("osw:icon_delete:" + name).then(function (res) {
        if (!res || !res.ok) {
          if (res && res.error) toast(res.error);
          return;
        }
        userIcons = (res.icons || []).map(function (i) { return { name: i.name, url: i.url, system: false }; });
        if (values[field.id] === name) setValue(field.id, "");
        if (iconPicker) paintIconGrid(search.value.trim().toLowerCase());
      });
    }
  }

  function onIconPickerKey(event) {
    if (!iconPicker) return;
    if ((event.key || "").toLowerCase() === "escape") {
      event.preventDefault();
      closeIconPicker();
    }
  }

  function closeIconPicker() {
    if (!iconPicker) return;
    const root = iconPicker.root;
    document.removeEventListener("keydown", onIconPickerKey, true);
    iconPicker = null;
    root.classList.add("is-closing");
    root.style.pointerEvents = "none";
    setTimeout(function () {
      if (root.parentNode) root.parentNode.removeChild(root);
    }, 150);
  }

  /* A value Python has already written. Updating `values` without touching
     `pending` keeps the page in step without sending the same write back. */
  function applyExternalValue(id, value) {
    if (!(id in values)) return;
    values[id] = value;
    syncField(id);
  }

  // ── image list (Main Background's slideshow) ─────────────────────────────

  /* A compact popover reusing the gallery's `.osw-gal-*` chrome: click a tile to
     toggle it in/out of the list (no light/dark targeting, no per-tile delete —
     this is a smaller sibling of openGallery, not a mode of it, since the
     selection model — many-of-many rather than one-of-many-per-slot — doesn't
     fit assign()/imageTargets() without bending both around a case they were
     never written for). */
  function openImageListPicker(field) {
    if (settingsPicker) closeSettingsPicker();
    if (gallery) closeGallery();

    const root = el("div", "osw-gal");
    const card = el("div", "osw-gal-card");
    root.appendChild(card);

    const head = el("div", "osw-gal-head");
    const titles = el("div", "osw-gal-titles");
    titles.appendChild(el("div", "osw-gal-title", field.label || str("gallery", "Gallery")));
    const count = el("div", "osw-gal-count");
    titles.appendChild(count);
    head.appendChild(titles);

    const importBtn = el("button", "osw-gal-import");
    importBtn.type = "button";
    const importIcon = el("span", "osw-gal-import-icon");
    importIcon.innerHTML = ICON_PLUS;
    importBtn.appendChild(importIcon);
    importBtn.appendChild(el("span", null, str("gallery_import", "Import image")));
    importBtn.addEventListener("click", runImport);
    head.appendChild(importBtn);

    const closeBtn = el("button", "osw-gal-close");
    closeBtn.type = "button";
    closeBtn.innerHTML = ICON_CLOSE;
    closeBtn.addEventListener("click", close);
    head.appendChild(closeBtn);
    card.appendChild(head);

    const grid = el("div", "osw-gal-grid");
    card.appendChild(grid);

    const foot = el("div", "osw-gal-foot");
    foot.textContent = str("gallery_hint_list", "Click images to add or remove them.");
    card.appendChild(foot);

    document.body.appendChild(root);
    root.addEventListener("mousedown", function (event) {
      if (event.target === root) close();
    });
    document.addEventListener("keydown", onKey, true);

    function currentList() {
      return Array.isArray(values[field.id]) ? values[field.id].slice() : [];
    }

    function toggle(name) {
      const list = currentList();
      const at = list.indexOf(name);
      if (at === -1) list.push(name); else list.splice(at, 1);
      setValue(field.id, list, { debounce: true });
      paintGrid();
      if (field.__syncImageList) field.__syncImageList();
    }

    function paintGrid() {
      const images = galleryList(field.folder);
      grid.innerHTML = "";
      grid.classList.toggle("is-empty", !images.length);
      count.textContent = images.length === 1
        ? str("gallery_count_one", "1 image")
        : fmt(str("gallery_count", "{n} images"), { n: images.length });

      if (!images.length) {
        const empty = el("div", "osw-gal-empty");
        const icon = el("div", "osw-gal-empty-icon");
        icon.innerHTML = ICON_IMAGE;
        empty.appendChild(icon);
        empty.appendChild(el("div", "osw-gal-empty-title", str("gallery_empty_title", "No images yet")));
        empty.appendChild(el("div", "osw-gal-empty-desc",
          str("gallery_empty_desc", "Import a picture to start your gallery.")));
        grid.appendChild(empty);
        return;
      }

      const selected = currentList();
      images.forEach(function (image) {
      const tile = el("button", "osw-gal-tile" + (selected.indexOf(image.name) !== -1 ? " is-selected" : ""));
      tile.type = "button";
        tile.setAttribute("data-name", image.name);
        const thumb = el("span", "osw-gal-thumb");
        appendImageWithFallback(thumb, image.url);
        tile.appendChild(thumb);
        tile.appendChild(el("span", "osw-gal-name", image.name));
        const badges = el("span", "osw-gal-badges");
        if (selected.indexOf(image.name) !== -1) {
          const badge = el("span", "osw-gal-badge osw-gal-badge-check");
          badge.innerHTML = ICON_CHECK;
          badges.appendChild(badge);
        }
        tile.appendChild(badges);
        tile.addEventListener("click", function () {
          bridge("osw:haptic:1");
          toggle(image.name);
        });
        grid.appendChild(tile);
      });
    }

    function runImport() {
      importBtn.classList.add("is-busy");
      call("osw:gallery_import:" + JSON.stringify({ folder: field.folder })).then(function (res) {
        importBtn.classList.remove("is-busy");
        if (!res || !res.ok) {
          if (res && res.error) toast(res.error);
          return;
        }
        setGalleryList(field.folder, res.images);
        const added = res.added || [];
        const list = currentList();
        added.forEach(function (name) { if (list.indexOf(name) === -1) list.push(name); });
        if (added.length) setValue(field.id, list, { debounce: true });
        paintGrid();
        if (field.__syncImageList) field.__syncImageList();
      });
    }

    function close() {
      document.removeEventListener("keydown", onKey, true);
      gallery = null;
      root.classList.add("is-closing");
      root.style.pointerEvents = "none";
      setTimeout(function () { if (root.parentNode) root.parentNode.removeChild(root); }, 150);
    }

    function onKey(event) {
      if ((event.key || "").toLowerCase() === "escape") {
        event.preventDefault();
        close();
      }
    }

    // Reuses the same `gallery` slot as openGallery so the two popovers can
    // never both be open (closeGallery() above already guards the reverse case).
    gallery = { field: field, root: root, close: close };
    paintGrid();
  }

  function renderImageList(field) {
    const host = el("div", "osw-imagefield osw-imagelist");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "image_list");
    host.appendChild(makeFieldHead(field));

    const strip = el("div", "osw-imagelist-strip");
    host.appendChild(strip);

    function paint() {
      const list = Array.isArray(values[field.id]) ? values[field.id] : [];
      strip.innerHTML = "";
      list.forEach(function (name) {
        const thumb = el("div", "osw-imagelist-thumb");
        appendImageWithFallback(thumb, imageUrl(field.folder, name));
        const remove = el("button", "osw-imagelist-remove");
        remove.type = "button";
        remove.innerHTML = ICON_CLOSE;
        remove.addEventListener("click", function (event) {
          event.stopPropagation();
          const next = list.filter(function (n) { return n !== name; });
          setValue(field.id, next, { debounce: true });
          paint();
        });
        thumb.appendChild(remove);
        strip.appendChild(thumb);
      });
      const add = el("button", "osw-imagelist-add");
      add.type = "button";
      add.innerHTML = ICON_PLUS;
      add.addEventListener("click", function () { openImageListPicker(field); });
      strip.appendChild(add);
    }

    field.__syncImageList = paint;
    paint();
    return host;
  }

  // ── designer previews (Main menu: Background / Widget Effect / Stats
  // Widgets / Deck Stats / Heatmap) ─────────────────────────────────────────
  //
  // One mechanism for all five: a `designer_preview` section is a single
  // self-contained card (unlike Profile, whose preview pulls fields from
  // sibling sections into tabs — Main menu's designers are stacked cards, each
  // with its own controls right below its own stage). PREVIEW_PAINTERS maps
  // `section.preview_kind` to a function that paints the stage from the live
  // `values`; each phase of the port adds one entry.

  const PREVIEW_PAINTERS = {};

  // Preview-only Onigimon grid footprint. The live widget supports 1-4 rows
  // by 1-2 columns; keeping this local means inspecting a size never moves the
  // user's actual widget in Main Menu > Organize.
  let onigimonPreviewColumns = 1;
  let onigimonPreviewRows = 2;

  /* Resolves a light/dark pair the same way pairLinked()/imageTargets() do —
     used by preview painters, which read straight from `values` rather than
     going through a rendered field's own imageTargets() call. */
  function designerPairValue(values, lightKey, darkKey, themeModeKey, isDark, baseKey) {
    let linked = true;
    if (themeModeKey) {
      const explicit = values[themeModeKey];
      if (explicit === "separate") linked = false;
      else if (explicit === "single") linked = true;
      else linked = values[lightKey] === values[darkKey];
    }
    if (linked) return (baseKey && values[baseKey]) || values[lightKey] || values[darkKey] || "";
    return (isDark ? values[darkKey] : values[lightKey]) || (baseKey && values[baseKey]) || "";
  }

  /* Group dynamic-mode switch: "on" (separate) only when every key in the
     group agrees, exactly like Profile's PROFILE_DYNAMIC_KEYS/profileDynamicOn. */
  function designerDynamicOn(keys) {
    return keys.length > 0 && keys.every(function (key) { return values[key] === "separate"; });
  }

  /* Change a whole designer between shared and light/dark storage without
     losing pictures. Older code changed only the mode keys, leaving a blank
     base slot when Dynamic mode was disabled; renderers then appeared to lose
     the selected background. The themed slots remain as a reversible backup. */
  function setDesignerDynamicMode(section, enabled, previewMode) {
    const dynamicKeys = section.dynamic_keys || [];
    (section.fields || []).forEach(function (field) {
      if (field.type !== "image" || !field.lightField || !field.darkField) return;
      if (dynamicKeys.indexOf(field.themeModeField) === -1) return;
      const base = values[field.id] || "";
      if (enabled) {
        if (!values[field.lightField] && base) setValue(field.lightField, base);
        if (!values[field.darkField] && base) setValue(field.darkField, base);
        return;
      }
      const preferred = previewMode === "dark" ? field.darkField : field.lightField;
      const alternate = previewMode === "dark" ? field.lightField : field.darkField;
      const shared = values[preferred] || values[alternate] || base;
      if (shared) setValue(field.id, shared);
    });
    dynamicKeys.forEach(function (key) {
      setValue(key, enabled ? "separate" : "single");
    });
  }

  // Cards currently on screen, so a drag/toggle repaints only what's visible —
  // rebuilt every showPage().
  let activeDesignerPreviews = [];
  // The Organize page is not a designer card, but its grid is now a live
  // rendition of the Main Menu. Keep its painter alongside the designer
  // painters so sliders, colour slots and background picks update it as soon
  // as their ordinary fields write to `values`.
  let activeWidgetGridPreviews = [];
  let activeWidgetGridBackgroundReceiver = null;
  let widgetGridBackgroundTimer = null;
  let widgetGridTileRadiusObserver = null;

  function stopWidgetGridBackgroundSync() {
    if (widgetGridBackgroundTimer) clearInterval(widgetGridBackgroundTimer);
    widgetGridBackgroundTimer = null;
    activeWidgetGridBackgroundReceiver = null;
    if (widgetGridTileRadiusObserver) widgetGridTileRadiusObserver.disconnect();
    widgetGridTileRadiusObserver = null;
  }

  function registerDesignerPreview(card) {
    activeDesignerPreviews.push(card);
  }

  /* "Sync with widgets" on means those rows are not the ones in effect, so they
     collapse away instead of lingering greyed out. */
  function applySyncHidden(card) {
    const section = card.__section;
    const toggleId = section.sync_toggle_id;
    if (!toggleId) return;
    const on = section.id === "sidebar_background"
      ? values["modern_menu_sidebar_bg_mode"] === "custom" : !!values[toggleId];
    (section.sync_hidden_fields || []).forEach(function (id) {
      const host = card.__fieldsHost && card.__fieldsHost.querySelector('[data-field-host="' + id + '"]');
      if (!host) return;
      host.classList.toggle("is-hidden", on);
    });
  }

  // A Match Main Menu background inherits its image, colour, blur, and
  // opacity from Main Background. Its local settings deck is therefore not
  // merely conditionally empty: it should not occupy any space at all.
  function applyDesignerDeckVisibility(card) {
    const host = card.__fieldsHost;
    if (!host) return;
    const condition = (card.__section || {}).hide_deck_when;
    const matching = !!condition && Object.keys(condition).length > 0 && showWhenMatches(condition);
    host.classList.toggle("is-hidden", matching);
    if (card.__dynamicControl) card.__dynamicControl.classList.toggle("is-hidden", matching);
  }

  function paintDesignerPreview(card) {
    if (!card || !card.__stage) return;
    if (card.__syncPreviewTheme) card.__syncPreviewTheme();
    const section = card.__section;
    const painter = PREVIEW_PAINTERS[section.preview_kind];
    if (painter) {
      const isDark = card.__getMode() === "dark";
      painter(card.__stage, values, isDark);
    }
    applySyncHidden(card);
    applyDeckVisibility(card);
    applyDesignerDeckVisibility(card);
  }

  function updateDesignerPreviews() {
    activeDesignerPreviews.forEach(paintDesignerPreview);
    activeWidgetGridPreviews = activeWidgetGridPreviews.filter(function (paint) {
      return paint();
    });
  }

  /* A choice flagged `head` in the schema: the card's own subject, rendered as
     a labelled segmented control in the header instead of a row below the
     stage (STYLE / CHART / VIEW / START in the designs). */
  /* Below its natural width, a header row with abbreviatable segmented
     options (e.g. Heatmap's Start/View) swaps their full labels for short
     ones instead of wrapping or scrolling — full width is re-measured on
     every resize so widening the window brings the full words straight
     back. Options without a `short` never change. */
  function observeHeaderCompact(head) {
    function update() {
      head.classList.remove("is-compact");
      if (head.scrollWidth > head.clientWidth + 1) head.classList.add("is-compact");
    }
    update();
    if (window.ResizeObserver) {
      new ResizeObserver(update).observe(head);
    } else {
      window.addEventListener("resize", update);
    }
  }

  function renderHeadChoice(field, card) {
    const ctl = el("div", "osw-preview-ctl");
    ctl.setAttribute("data-field-host", field.id);
    if (field.headLabel) ctl.appendChild(el("span", "osw-preview-ctl-label", field.headLabel));
    const host = el("div", "osw-segmented-control osw-preview-seg");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "choice");
    (field.options || []).forEach(function (option) {
      const btn = el("div", "osw-segment-btn" + (option.value === values[field.id] ? " is-active" : ""));
      btn.setAttribute("role", "button");
      btn.setAttribute("tabindex", "0");
      btn.setAttribute("data-value", option.value);
      if (option.icon) {
        const glyph = el("span", "osw-segment-btn-icon");
        glyph.innerHTML = option.icon;
        btn.appendChild(glyph);
        btn.title = option.label;
      } else if (option.short) {
        btn.appendChild(el("span", "osw-segment-label osw-segment-label-full", option.label));
        btn.appendChild(el("span", "osw-segment-label osw-segment-label-short", option.short));
        btn.title = option.label;
      } else {
        btn.appendChild(el("span", "osw-segment-label", option.label));
      }
      btn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        // setValue -> syncField already repaints every active designer card
        // (updateDesignerPreviews); a second explicit paint here used to run
        // right behind it and immediately overwrite that first paint's fade,
        // which is why the Minimal <-> Expressive switch looked like a cut.
        setValue(field.id, option.value);
        Array.prototype.forEach.call(host.querySelectorAll(".osw-segment-btn"), function (b) {
          b.classList.toggle("is-active", b.getAttribute("data-value") === String(option.value));
        });
      });
      host.appendChild(btn);
    });
    ctl.appendChild(host);
    return ctl;
  }

  // Preview-only selectors use the exact same header treatment as schema
  // choices, but intentionally do not create a persisted setting. They choose
  // which real screen/state is being inspected, just like the legacy preview
  // tabs did.
  function renderLocalHeadChoice(label, options, activeValue, onChange) {
    const ctl = el("div", "osw-preview-ctl osw-preview-local-choice");
    ctl.appendChild(el("span", "osw-preview-ctl-label", label));
    const host = el("div", "osw-segmented-control osw-preview-seg");
    const buttons = [];
    options.forEach(function (option) {
      const btn = el("div", "osw-segment-btn" + (option.value === activeValue() ? " is-active" : ""), option.label);
      btn.setAttribute("role", "button");
      btn.setAttribute("tabindex", "0");
      btn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        onChange(option.value);
        buttons.forEach(function (item) { item.classList.toggle("is-active", item === btn); });
      });
      buttons.push(btn);
      host.appendChild(btn);
    });
    ctl.appendChild(host);
    return ctl;
  }

  /* A toggle flagged `head`: the same labelled square switch the Dynamic mode
     control uses, so "Sync with widgets" and "Dynamic mode" read as one row of
     switches in the card header. */
  function renderHeadToggle(field, card) {
    const ctl = el("div", "osw-preview-ctl");
    ctl.setAttribute("data-field-host", field.id);
    if (field.headLabel) ctl.appendChild(el("span", "osw-preview-ctl-label", field.headLabel));
    const btn = el("button", "osw-sq-switch-btn");
    btn.type = "button";
    btn.setAttribute("data-field", field.id);
    btn.setAttribute("aria-pressed", values[field.id] ? "true" : "false");
    const track = el("div", "osw-sq-switch" + (values[field.id] ? " is-on" : ""));
    btn.appendChild(track);
    btn.addEventListener("click", function () {
      bridge("osw:haptic:1");
      const next = !values[field.id];
      // keepDom's own branch already calls updateDesignerPreviews(); see the
      // note in renderHeadChoice's click handler above.
      setValue(field.id, next, { keepDom: true });
      track.classList.toggle("is-on", next);
      btn.setAttribute("aria-pressed", next ? "true" : "false");
    });
    ctl.appendChild(btn);
    return ctl;
  }

  // A number marked `head` stays directly editable in the preview toolbar.
  // Keep the normal autosave path so the preview and the stored value respond
  // exactly like the number field did in the deck below the stage.
  function renderHeadNumber(field) {
    const ctl = el("div", "osw-preview-ctl osw-preview-number-ctl osw-organize-ctl");
    ctl.setAttribute("data-field-host", field.id);
    const label = field.headLabel || field.label || "";
    if (label) ctl.appendChild(el("span", "osw-organize-ctl-label", label));

    const control = el("div", "osw-organize-ctl-box osw-preview-number");
    control.setAttribute("data-field", field.id);
    control.setAttribute("data-field-type", "number");
    const input = document.createElement("input");
    input.type = "number";
    input.inputMode = "numeric";
    input.className = "osw-organize-ctl-input";
    input.setAttribute("aria-label", label);
    const scale = field.scale > 0 ? field.scale : 1;
    input.value = Math.round((Number(values[field.id] == null ? field.default : values[field.id]) || 0) / scale);
    if (field.min != null) input.min = field.min;
    if (field.max != null) input.max = field.max;
    input.step = field.step != null ? field.step : 1;
    input.addEventListener("input", function () {
      const raw = parseFloat(input.value);
      if (isNaN(raw)) return;
      let next = raw;
      if (field.min != null) next = Math.max(Number(field.min), next);
      if (field.max != null) next = Math.min(Number(field.max), next);
      setValue(field.id, next * scale, { keepDom: true, debounce: true });
    });
    input.addEventListener("change", function () {
      const raw = parseFloat(input.value);
      let next = isNaN(raw) ? Number(values[field.id] || 0) / scale : raw;
      if (field.min != null) next = Math.max(Number(field.min), next);
      if (field.max != null) next = Math.min(Number(field.max), next);
      input.value = next;
      setValue(field.id, next * scale, { keepDom: true });
    });
    control.appendChild(input);
    if (field.suffix) control.appendChild(el("span", "osw-organize-ctl-suffix", field.suffix));
    ctl.appendChild(control);
    return ctl;
  }

  /* Rows that only make sense for some values of another field (the slideshow
     list under Slideshow, the per-metric accents only in Expressive, …).

     A condition is either a leaf ({field, values}) or a combinator
     ({all: [...]} / {any: [...]}), so "Expressive, or Minimal with the stars
     on" is expressible without a bespoke rule per field. */
  function showWhenMatches(condition) {
    if (!condition) return true;
    if (Array.isArray(condition.all)) return condition.all.every(showWhenMatches);
    if (Array.isArray(condition.any)) return condition.any.some(showWhenMatches);
    if (condition.not) return !showWhenMatches(condition.not);
    if (!condition.field) return true;
    const greaterThan = condition.greaterThan != null
      ? condition.greaterThan
      : condition.greater_than;
    if (greaterThan != null) {
      return Number(values[condition.field]) > Number(greaterThan);
    }
    return (condition.values || []).indexOf(values[condition.field]) !== -1;
  }

  /* Sync-hidden (applySyncHidden) and show_when decide the same class on the
     same node, and a field can be governed by both — Sidebar Background's
     Color row is taken over by "Sync with Widget Color and Effect" *and* is
     only relevant for some background styles. Either reason is enough, so the
     show_when pass has to ask about the sync one instead of overwriting it. */
  function isSyncHidden(card, fieldId) {
    const section = card.__section || {};
    const on = section.id === "sidebar_background"
      ? values["modern_menu_sidebar_bg_mode"] === "custom" : !!values[section.sync_toggle_id];
    if (!section.sync_toggle_id || !on) return false;
    return (section.sync_hidden_fields || []).indexOf(fieldId) !== -1;
  }

  function applyDeckVisibility(card) {
    const host = card.__fieldsHost;
    if (!host) return;
    ((card.__section || {}).fields || []).forEach(function (field) {
      if (!field.showWhen) return;
      const node = host.querySelector('[data-field-host="' + field.id + '"]');
      if (!node) return;
      const hidden = !showWhenMatches(field.showWhen) || isSyncHidden(card, field.id);
      node.classList.toggle(
        "is-hidden", hidden
      );
      // Action Buttons is a compact, single-column card. Its inactive
      // controls must leave the layout altogether; collapsing their visual
      // contents alone leaves empty flex/grid tracks before the icon groups.
      if ((card.__section || {}).id === "sidebar_actions") {
        node.style.display = hidden ? "none" : "";
      }
    });
    // Background Color is the base beneath both a bundled scene and a custom
    // image, so it remains useful at every opacity. Keep it visible even for
    // an already-open settings window whose schema predates that rule.
    if ((card.__section || {}).id === "onigimon_scene") {
      const sceneColor = host.querySelector('[data-field-host="g_onigimon_scene_color"]');
      if (sceneColor) sceneColor.classList.remove("is-hidden");
    }
    // Header-mounted controls (STYLE/CHART/… segments, Sync/Dynamic switches)
    // live outside __fieldsHost, in the card's own head row.
    ((card.__section || {}).fields || []).forEach(function (field) {
      if (!field.head || !field.showWhen) return;
      const node = card.querySelector('.osw-designer-preview-head [data-field-host="' + field.id + '"]');
      if (!node) return;
      node.classList.toggle("is-hidden", !showWhenMatches(field.showWhen));
    });
    rebalanceDeck(card);
    collapseEmptyDeckGroups(card);
  }

  /* A deck group whose every row is hidden still occupies a grid row, so the
     deck's row-gap is still drawn above the next group — the container then
     has more space above its first visible row than below its last one. It
     collapses to zero height rather than out of the grid because its rows are
     hidden individually (a group is never itself marked hidden). Take the
     whole group out of the flow once nothing in it is left to show. Direct
     children only: a paired row carries data-field-host itself as well as on
     each half, and only the outer one is toggled. */
  function collapseEmptyDeckGroups(card) {
    const host = card.__fieldsHost;
    if (!host) return;
    // Designer subsections are nested inside the two deck columns. Hide a
    // heading when all of its conditional rows disappear (for example, Box
    // Appearance while Sync is enabled), instead of leaving an empty label.
    Array.prototype.forEach.call(host.querySelectorAll(".osw-deck-subsection"), function (subsection) {
      const rows = subsection.querySelectorAll("[data-field-host]");
      const anyVisible = Array.prototype.some.call(rows, function (row) {
        return !row.classList.contains("is-hidden");
      });
      subsection.classList.toggle("is-empty", !anyVisible);
    });
    Array.prototype.forEach.call(host.children, function (group) {
      const rows = group.querySelectorAll(":scope > [data-field-host]");
      if (!rows.length) return;
      // Row spacing is an adjacent-sibling margin-top, and `+` still matches
      // across a hidden (or display:none) sibling — so when the rows that
      // happen to be first are the hidden ones, the first row the user can
      // actually see still carries that margin and the group sits lower than
      // its own padding. Flag the leading visible row so the margin can be
      // dropped from exactly that one.
      let seenVisible = false;
      Array.prototype.forEach.call(rows, function (row) {
        const hidden = row.classList.contains("is-hidden");
        row.classList.toggle("is-first-visible", !hidden && !seenVisible);
        if (!hidden) seenVisible = true;
      });
      group.classList.toggle("is-empty", !seenVisible);
    });
    // Every group empty (Silent mode hides both of the Notifications rows)
    // leaves the deck itself as a bare padded strip under the stage. Take the
    // container out too rather than drawing an empty card.
    const anyVisible = Array.prototype.some.call(host.children, function (group) {
      return !group.classList.contains("is-empty");
    });
    host.classList.toggle("is-empty", !anyVisible);
  }

  /* Which rows are visible shifts a lot on this card (Minimal vs Expressive,
     Sync on/off), and the deck's two columns are fixed-width DOM buckets — so
     whichever bucket lost more rows leaves a bare patch under the other one.
     Fields are already written in schema.py as three contiguous runs (the
     controls — toggles/sliders/font/choice —, then every colour, then every
     icon), so splitting the field list at each type-group change gives back
     those same three blocks. Whole blocks then get greedily assigned to
     whichever column is currently shorter: colours stay together, icons stay
     together, controls stay together, and the two columns still end up
     within a block's height of each other instead of one trailing off with a
     bare patch underneath. Re-run only when which fields are visible actually
     changed — every slider tick repaints the card, and none of that should
     reshuffle a column that already looks right. */
  const DECK_ROW_HEIGHT_ESTIMATE = { color_pair: 40, color: 40, image: 44, image_list: 44 };
  // Two tiles per row at ~64px each, not one row per icon at ~46px.
  const DECK_ICON_TILE_HEIGHT = 64;
  const ICON_GROUP_TITLES = {
    modern_menu_icon_header_search: "Deck-list header icons",
    modern_menu_icon_search: "Action Button icons",
    modern_menu_icon_ready_section: "Ready To Go header icon",
    modern_menu_icon_ready_inbox: "Ready To Go action icons",
  };

  function deckFieldGroup(field) {
    if (field.deckPlacement) return "pinned-" + field.deckPlacement;
    if (field.type === "color_pair" || field.type === "color") return "colors";
    if (field.type === "icon") return "icons";
    return "controls";
  }

  function rebalanceDeck(card) {
    const host = card.__fieldsHost;
    // Both columns come off the card, not out of the DOM: an empty one is left
    // detached at mount time (see renderDesignerPreview), and looking it up by
    // selector would then miss it and skip the whole pass — which is how a card
    // with no picture/colour slots at all (Action Buttons) ended up rendering
    // its ten icon fields as ten stacked full-width rows instead of one grid.
    const controlsCol = card.__controlsCol || (host && host.querySelector(".osw-deck-controls"));
    const slotsCol = card.__slotsCol || (host && host.querySelector(".osw-deck-slots"));
    if (!host || !controlsCol || !slotsCol) return;

    // Background always keeps sliders and colour/image pickers side by side —
    // the height-balancing heuristic below is tuned for the other designer
    // cards' longer, more varied field lists and collapses this one to a
    // single column whenever Color-only mode leaves just Color + two
    // sliders, which is exactly the layout that should stay two columns.
    // Widget Color and Effect keeps its sliders on the left and its two
    // colour pickers on the right — the same balancing heuristic would put
    // the (shorter) colour block first since both columns start even, which
    // is the opposite of the intended layout.
    // Deck Stats' colours are pulled into their own full-width grid at mount
    // time (see renderDesignerPreview) instead of living in either column —
    // this height-balancing pass only knows about controlsCol/slotsCol, so
    // running it here would try to pull those colour rows back in.
    if ((card.__section || {}).id === "mainmenu_background" ||
        (card.__section || {}).id === "mainmenu_widget_effect" ||
        (card.__section || {}).id === "mainmenu_deck_stats" ||
        // Sidebar Customization has fixed compact Layout subsections beside
        // its preview; moving rows for height balancing would unwrap them.
        (card.__section || {}).id === "sidebar_background" ||
        (card.__section || {}).id === "overview_background" ||
        (card.__section || {}).id === "reviewer_background" ||
        // Onigimon has two deliberate full-width rows: background type first,
        // then the scenario catalogue beneath the compact effect controls.
        (card.__section || {}).id === "onigimon_scene" ||
        // Overview Style deliberately has a fixed split: all sliders and
        // actions stay together in the left column, while colour pairs stay
        // together in the right. Rebalancing it by estimated height moves
        // later sliders underneath the palette, separating related controls.
        (card.__section || {}).id === "overview_style") return;

    // "hidden" fields (the light/dark storage keys behind a color_pair, a
    // theme_mode flag, ...) render no row at all — left in, they break up a
    // contiguous run of visible same-type fields (e.g. two colour rows with
    // a hidden field wedged between them) into separate one-field blocks
    // that then land in different columns instead of staying together.
    const fields = ((card.__section || {}).fields || [])
      .filter(function (f) {
        const isDetachedColor = card.__fullWidthColorGrid &&
          (f.type === "color_pair" || f.type === "color");
        return !f.head && f.type !== "hidden" && !isDetachedColor;
      });
    const visibleIds = [];
    fields.forEach(function (field) {
      const node = host.querySelector('[data-field-host="' + field.id + '"]');
      if (node && !node.classList.contains("is-hidden")) visibleIds.push(field.id);
    });
    const signature = visibleIds.join(",");
    if (card.__deckBalanceSig === signature) return;
    card.__deckBalanceSig = signature;

    // Split into runs of consecutive same-group fields, in schema order.
    const blocks = [];
    fields.forEach(function (field) {
      const group = deckFieldGroup(field);
      const last = blocks[blocks.length - 1];
      if (last && last.group === group) last.fields.push(field);
      else blocks.push({ group: group, fields: [field] });
    });

    // Below ~3-4 rows total (typically a show_when-heavy section with most
    // of its fields conditionally hidden — Background's "Color only" style
    // leaves just Color + two sliders), a 2-column split can only ever put
    // one tiny block against one taller one: not a balance, just a short
    // column next to a gap. Stack singly instead of forcing the split.
    let totalNonIconH = 0;
    blocks.forEach(function (block) {
      if (block.group === "icons") return;
      block.fields.forEach(function (field) {
        if (deckSkipField(field.id)) return;
        const node = host.querySelector('[data-field-host="' + field.id + '"]');
        if (node && !node.classList.contains("is-hidden")) totalNonIconH += DECK_ROW_HEIGHT_ESTIMATE[field.type] || 46;
      });
    });
    // A stage-side card is already only half the page wide; splitting its
    // controls again would leave two ~200px columns. It keeps one column, in
    // schema order (which is what the schema is written to express there).
    const singleColumn = !!(card.__section || {}).stage_side ||
      (totalNonIconH > 0 && totalNonIconH < 160);

    let leftH = 0;
    let rightH = 0;
    const pinnedNodes = [];
    blocks.forEach(function (block) {
      // A deliberately positioned item stays next to its related control.
      if (block.group === "pinned-right" || block.group === "pinned-left") {
        const target = singleColumn || block.group === "pinned-left" ? controlsCol : slotsCol;
        let blockH = 0;
        block.fields.forEach(function (field) {
          const node = host.querySelector('[data-field-host="' + field.id + '"]');
          if (node) pinnedNodes.push({ node: node, target: target });
          if (node && !node.classList.contains("is-hidden")) {
            blockH += field.deckIconTile ? DECK_ICON_TILE_HEIGHT : (DECK_ROW_HEIGHT_ESTIMATE[field.type] || 46);
          }
        });
        if (target === controlsCol) leftH += blockH; else rightH += blockH;
        return;
      }
      // An icon block moves as one tile grid, not as N stacked full-width
      // rows: half the height for the same fields, and the tiles read as one
      // picker cluster instead of a run of identical-looking list rows.
      if (block.group === "icons") {
        // Each contiguous icon category gets its own grid. Reusing one wrapper
        // here merged deck-header icons with the actual Action Button icons,
        // making the settings cards look like one undifferentiated catalogue.
        const groupKey = block.fields[0] && block.fields[0].id || "icons";
        card.__iconGridEls = card.__iconGridEls || {};
        const wrap = card.__iconGridEls[groupKey] || el("div", "osw-deck-icon-grid");
        card.__iconGridEls[groupKey] = wrap;
        wrap.classList.toggle("osw-sidebar-action-icons", (card.__section || {}).id === "sidebar_actions");
        const groupTitle = block.fields[0] && (
          block.fields[0].icon_group_title ||
          ICON_GROUP_TITLES[groupKey] ||
          (groupKey.indexOf("modern_menu_icon_ready_") === 0
            ? "Ready To Go action icons"
            : "Action Button icons")
        );
        if (groupTitle) {
          wrap.setAttribute("data-icon-group-title", groupTitle);
          wrap.setAttribute("data-icon-group", block.fields[0].icon_group || "");
          let title = wrap.querySelector(".osw-deck-icon-group-title");
          if (!title) {
            title = el("div", "osw-deck-icon-group-title", groupTitle);
            title.setAttribute("role", "heading");
            title.setAttribute("aria-label", groupTitle);
            wrap.insertBefore(title, wrap.firstChild);
          } else {
            title.textContent = groupTitle;
          }
        }
        wrap.classList.toggle(
          "is-header-group",
          groupKey === "modern_menu_icon_header_search" || groupKey === "modern_menu_icon_ready_section"
        );
        wrap.classList.toggle("is-ready-header-group", groupKey === "modern_menu_icon_ready_section");
        wrap.classList.toggle(
          "is-action-group",
          groupKey === "modern_menu_icon_search" || groupKey.indexOf("modern_menu_icon_ready_") === 0
        );
        if ((card.__section || {}).id === "mainmenu_stats_widgets") {
          wrap.classList.add("osw-stats-widget-icon-line");
        }
        // Look in `wrap` as well as in `host`: the tiles are moved into it
        // right here, and on the very first pass `wrap` is still detached — so
        // counting them back out of `host` afterwards found none of them and
        // collapsed a full ten-tile grid to the two-tile inline layout.
        let visibleCount = 0;
        block.fields.forEach(function (field) {
          const selector = '[data-field-host="' + field.id + '"]';
          const node = host.querySelector(selector) || wrap.querySelector(selector);
          if (!node) return;
          wrap.appendChild(node);
          if (!node.classList.contains("is-hidden")) visibleCount += 1;
        });
        if (visibleCount > 2) {
          // Four tiles read as one strip and need more room than a single
          // ~45%-wide column has — full deck width, outside the controls/
          // slots split (a third row spanning both columns), taking no part
          // in the leftH/rightH balance below.
          wrap.classList.remove("is-inline", "is-single");
          wrap.classList.remove("is-empty");
          host.appendChild(wrap);
        } else {
          // Two tiles or fewer (e.g. Heatmap Shape/Streak Icon) fit a single
          // column fine — sits with whichever side is shorter instead of
          // leaving a half-empty full-width row.
          wrap.classList.add("is-inline");
          wrap.classList.toggle("is-single", visibleCount === 1);
          wrap.classList.toggle("is-empty", visibleCount === 0);
          const target = singleColumn || leftH <= rightH ? controlsCol : slotsCol;
          if (wrap.parentElement !== target) target.appendChild(wrap);
          const blockH = DECK_ICON_TILE_HEIGHT;
          if (target === controlsCol) leftH += blockH; else rightH += blockH;
        }
        return;
      }
      // A long run of same-type rows with nothing else to balance it against
      // reads as one very tall column next to an empty one. Past a handful of
      // fields it splits into two halves — except a "colors" run, which stays
      // whole: colors read as one palette, and splitting it put Label Color on
      // one side of the deck and Value Color on the other.
      if (!singleColumn && block.fields.length > 4 && block.group !== "colors") {
        // Split where cumulative *visible* height crosses the halfway mark,
        // not at the halfway *index* — a block mixing hidden fields (a
        // toggle-only row here, a whole hidden colour run there) with visible
        // ones splits unevenly by count even though it reads evenly by
        // height, which is what actually shows up as a gap under one column.
        const heights = block.fields.map(function (field) {
          if (deckSkipField(field.id)) return 0;
          const node = host.querySelector('[data-field-host="' + field.id + '"]');
          if (!node || node.classList.contains("is-hidden")) return 0;
          return DECK_ROW_HEIGHT_ESTIMATE[field.type] || 46;
        });
        const halfH = heights.reduce(function (a, b) { return a + b; }, 0) / 2;
        let mid = block.fields.length;
        let running = 0;
        for (let i = 0; i < heights.length; i++) {
          running += heights[i];
          if (running > 0 && running >= halfH) { mid = i + 1; break; }
        }
        const firstCol = leftH <= rightH ? controlsCol : slotsCol;
        const secondCol = firstCol === controlsCol ? slotsCol : controlsCol;
        let firstH = 0;
        let secondH = 0;
        block.fields.forEach(function (field, index) {
          if (deckSkipField(field.id)) return;
          const node = host.querySelector('[data-field-host="' + field.id + '"]');
          const target = index < mid ? firstCol : secondCol;
          if (node && node.parentElement !== target) target.appendChild(node);
          if (node && !node.classList.contains("is-hidden")) {
            const h = DECK_ROW_HEIGHT_ESTIMATE[field.type] || 46;
            if (index < mid) firstH += h; else secondH += h;
          }
        });
        if (firstCol === controlsCol) leftH += firstH; else rightH += firstH;
        if (secondCol === controlsCol) leftH += secondH; else rightH += secondH;
        return;
      }
      let blockH = 0;
      block.fields.forEach(function (field) {
        if (deckSkipField(field.id)) return; // counted via its pair anchor
        const node = host.querySelector('[data-field-host="' + field.id + '"]');
        if (node && !node.classList.contains("is-hidden")) blockH += DECK_ROW_HEIGHT_ESTIMATE[field.type] || 46;
      });
      const target = singleColumn || leftH <= rightH ? controlsCol : slotsCol;
      block.fields.forEach(function (field) {
        if (deckSkipField(field.id)) return; // fused into its pair anchor's row, moves with it
        const node = host.querySelector('[data-field-host="' + field.id + '"]');
        if (node && node.parentElement !== target) target.appendChild(node);
      });
      if (target === controlsCol) leftH += blockH; else rightH += blockH;
    });

    // Other blocks may append controls to the same column after the pinned
    // block is encountered. Move pinned controls last so their visual order
    // matches their requested bottom placement on every rebalance.
    pinnedNodes.forEach(function (item) { item.target.appendChild(item.node); });

    // Attach/detach both columns based on final content rather than trusting
    // renderDesignerPreview's one-time initial placement: a column that ends
    // up empty (every field in it hidden, or this section just collapsed to
    // one column) must not sit in the grid as a blank second track, and one
    // that gained content after starting empty must not stay invisible.
    const iconWraps = blocks
        .filter(function (block) { return block.group === "icons" && block.fields[0] && card.__iconGridEls && card.__iconGridEls[block.fields[0].id]; })
        .map(function (block) { return card.__iconGridEls[block.fields[0].id]; });
    const colorGrid = card.__fullWidthColorGrid;
    if (controlsCol.parentElement === host) host.removeChild(controlsCol);
    if (slotsCol.parentElement === host) host.removeChild(slotsCol);
    if (controlsCol.childNodes.length) host.appendChild(controlsCol);
    if (!singleColumn && slotsCol.childNodes.length) host.appendChild(slotsCol);
    if (colorGrid && colorGrid.parentElement === host) host.appendChild(colorGrid);
    iconWraps.forEach(function (wrap) {
      if (wrap.parentElement === host) host.appendChild(wrap);
    });
    host.style.gridTemplateColumns = (singleColumn || !slotsCol.childNodes.length) ? "1fr" : "";
  }

  const DECK_SLOT_TYPES = { image: 1, image_list: 1, color_pair: 1, color: 1 };

  // Show icons + Show units share one row, and Show 7-day trend + Background
  // wash share the next one — two lines of two instead of four stacked full-
  // width rows. Key is the row that absorbs the paired field; the paired
  // field itself is never placed on its own — see deckSkipField below.
  const DECK_PAIR_WITH = {
    swidget_show_icons: "swidget_show_units",
    swidget_show_sparkline: "swidget_show_wash",
    heatmapShowStreak: "heatmapShowMonths",
    heatmapShowWeekdays: "heatmapShowWeekHeader",
    // Deck Stats' 4 effect sliders as a 2x2 grid instead of 4 stacked rows.
    dstats_blur: "dstats_radius",
    dstats_opacity: "dstats_stroke",
    // Decks' six short "hide this" switches as three rows of two. "Hide
    // default, show custom" stays full width: it is the only one that needs a
    // description line.
    hideDeckCounts: "hideAllDeckCounts",
    modern_menu_hide_folder_icon: "modern_menu_hide_subdeck_icon",
    modern_menu_hide_deck_icon: "modern_menu_hide_filtered_deck_icon",
    // Sidebar Customization keeps its item layout as a compact 2x2 edge grid
    // beside the preview. Widget layout now lives with Organize Widgets.
    modern_menu_sidebar_item_margin_top: "modern_menu_sidebar_item_margin_right",
    modern_menu_sidebar_item_margin_bottom: "modern_menu_sidebar_item_margin_left"
  };
  const DECK_PAIRED_AWAY = {};
  Object.keys(DECK_PAIR_WITH).forEach(function (id) { DECK_PAIRED_AWAY[DECK_PAIR_WITH[id]] = id; });

  // Colour fields listed as an icon field's popup companions (see the icon
  // popover above) render inside that popup, not as their own deck row.
  const ICON_POPUP_SKIP = {};
  Object.keys(ICON_POPUP_COMPANIONS).forEach(function (iconId) {
    ICON_POPUP_COMPANIONS[iconId].forEach(function (id) { ICON_POPUP_SKIP[id] = iconId; });
  });

  function deckSkipField(fieldId) {
    return !!DECK_PAIRED_AWAY[fieldId] || !!ICON_POPUP_SKIP[fieldId];
  }

  function renderDeckField(field) {
    const renderer = FIELD_RENDERERS[field.type];
    if (!renderer) return null;
    const node = renderer(field);
    node.setAttribute("data-field-host", field.id);
    return node;
  }

  /* Two independent full rows side by side, each keeping its own background/
     padding/radius — unlike a fused single-chip pairing, neither control here
     needs the other's context to read correctly, so there's nothing to build
     by hand. */
  function buildSideBySideRow(fieldA, fieldB) {
    const row = el("div", "osw-deck-pair-row");
    row.setAttribute("data-field-host", fieldA.id);
    const nodeA = renderDeckField(fieldA);
    if (nodeA) row.appendChild(nodeA);
    const nodeB = renderDeckField(fieldB);
    if (nodeB) row.appendChild(nodeB);
    return row;
  }

  function renderDesignerPreview(section, page) {
    const wrap = el("div", "osw-designer-page-wrap");
    // Stage beside the controls rather than above them: the card and the fields
    // host are already siblings here, so this is a two-column grid on the wrap.
    if (section.stage_side) wrap.classList.add("is-stage-side");

    const card = el("div", "osw-designer-preview-card");
    if (section.preview_kind) card.classList.add("osw-preview-kind-" + section.preview_kind);
    if (section.id) card.classList.add("osw-preview-section-" + section.id);
    wrap.appendChild(card);

    const previewDynamicField = section.preview_dynamic_field || "";
    if (previewDynamicField === "profile") syncProfileLevelDynamicMode();
    let previewMode = (previewDynamicField && previewDynamicField !== "profile" && !values[previewDynamicField])
      ? "light"
      : (CTX.dark ? "dark" : "light");
    card.classList.toggle("is-dark", previewMode === "dark");

    const head = el("div", "osw-designer-preview-head");
    head.appendChild(el("div", "osw-designer-preview-title", section.title || str("preview", "Preview")));

    const headControls = el("div", "osw-preview-head-controls");

    (section.fields || []).forEach(function (field) {
      if (!field.head || section.head_to_deck) return;
      if (field.type === "choice") headControls.appendChild(renderHeadChoice(field, card));
      else if (field.type === "toggle") headControls.appendChild(renderHeadToggle(field, card));
      else if (field.type === "number") headControls.appendChild(renderHeadNumber(field));
    });

    if (section.preview_kind === "reviewer_bottom_bar") {
      headControls.appendChild(renderLocalHeadChoice(
        "Preview",
        [["answer", "Answer Buttons"], ["pre_answer", "Pre-Answer Buttons"]].map(function (pair) {
          return { value: pair[0], label: pair[1] };
        }),
        function () { return bbarActiveMode; },
        function (value) {
          bbarActiveMode = value;
          paintDesignerPreview(card);
        }
      ));
    } else if (section.preview_kind === "overview_style") {
      headControls.appendChild(renderLocalHeadChoice(
        "Screen",
        [{ value: "overviewer", label: "Overview" }, { value: "congrats", label: "Congrats" }],
        function () { return ovstyleActiveScreen; },
        function (value) {
          ovstyleActiveScreen = value;
          paintDesignerPreview(card);
        }
      ));
    } else if (section.preview_kind === "onigimon_scene") {
      headControls.appendChild(renderLocalHeadChoice(
        str("columns", "Columns"),
        [1, 2].map(function (count) {
          return { value: String(count), label: String(count) };
        }),
        function () { return String(onigimonPreviewColumns); },
        function (value) {
          onigimonPreviewColumns = Math.max(1, Math.min(2, Number(value) || 1));
          paintDesignerPreview(card);
        }
      ));
      headControls.appendChild(renderLocalHeadChoice(
        str("rows", "Rows"),
        [1, 2, 3, 4].map(function (count) {
          return { value: String(count), label: String(count) };
        }),
        function () { return String(onigimonPreviewRows); },
        function (value) {
          onigimonPreviewRows = Math.max(1, Math.min(4, Number(value) || 1));
          paintDesignerPreview(card);
        }
      ));
    }

    const dynamicKeys = section.dynamic_keys || [];
    if (dynamicKeys.length) {
      const dynCtl = el("div", "osw-preview-ctl");
      dynCtl.appendChild(el("span", "osw-preview-ctl-label", str("dynamic_mode", "Dynamic mode")));
      const dynBtn = el("button", "osw-sq-switch-btn");
      dynBtn.type = "button";
      dynBtn.setAttribute("aria-label", str("dynamic_mode", "Dynamic mode"));
      dynBtn.setAttribute("aria-pressed", designerDynamicOn(dynamicKeys) ? "true" : "false");
      const dynTrack = el("div", "osw-sq-switch" + (designerDynamicOn(dynamicKeys) ? " is-on" : ""));
      dynBtn.appendChild(dynTrack);
      dynBtn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        const next = !designerDynamicOn(dynamicKeys);
        setDesignerDynamicMode(section, next, previewMode);
        dynTrack.classList.toggle("is-on", next);
        dynBtn.setAttribute("aria-pressed", next ? "true" : "false");
        refreshImageFields();
        refreshPairFields();
        paintDesignerPreview(card);
      });
      dynCtl.appendChild(dynBtn);
      headControls.appendChild(dynCtl);
      card.__dynamicControl = dynCtl;
    }

    const toggleBtn = el("button", "osw-profile-preview-toggle-btn osw-designer-preview-toggle-btn");
    toggleBtn.type = "button";
    function paintToggleIcon() {
      toggleBtn.innerHTML = previewMode === "dark" ? OSW_SUN_ICON : OSW_MOON_ICON;
      toggleBtn.title = previewMode === "dark" ? str("light_mode", "Light") : str("dark_mode", "Dark");
    }
    paintToggleIcon();

    // A shared Profile palette still sits on Anki's current sidebar backdrop.
    // Other single-palette previews retain their light-only presentation.
    function syncPreviewTheme() {
      const dynamicOn = previewDynamicField === "profile"
        ? profileDynamicOn()
        : (!previewDynamicField || !!values[previewDynamicField]);
      if (!dynamicOn) previewMode = previewDynamicField === "profile" && CTX.dark ? "dark" : "light";
      card.classList.toggle("is-dark", previewMode === "dark");
      toggleBtn.classList.toggle("is-hidden", !dynamicOn);
      paintToggleIcon();
    }
    card.__syncPreviewTheme = syncPreviewTheme;
    syncPreviewTheme();

    toggleBtn.addEventListener("click", function () {
      previewMode = previewMode === "dark" ? "light" : "dark";
      paintDesignerPreview(card);
    });
    // Section-scoped reset: every field this card owns goes back to the
    // schema default, hidden companions included, so a half-reset can't leave
    // a colour pair pointing at a theme mode that no longer matches.
    const resetLabel = str("reset", "Reset");
    const resetBtn = el("button", "osw-btn osw-designer-reset");
    resetBtn.type = "button";
    resetBtn.setAttribute("aria-label", resetLabel);
    resetBtn.title = resetLabel;
    resetBtn.appendChild(el("span", "osw-designer-reset-label", resetLabel));
    const resetIcon = el("span", "osw-designer-reset-icon");
    resetIcon.innerHTML = OSW_RESET_ICON;
    resetBtn.appendChild(resetIcon);
    installResetHold(resetBtn, function () {
      (section.fields || []).forEach(function (field) {
        if (field.default === undefined) return;
        setValue(field.id, field.default, { silent: true, keepDom: true });
      });
      showPage(currentPage);
    }, { title: resetLabel });

    // Theme toggle + Reset are one utility pair, not two separate groups —
    // a tighter gap between just these two than the 26px headControls uses
    // between Style/Sync/Dynamic.
    const utilityCtl = el("div", "osw-preview-utility-ctl");
    utilityCtl.appendChild(toggleBtn);
    utilityCtl.appendChild(resetBtn);
    headControls.appendChild(utilityCtl);

    head.appendChild(headControls);
    card.appendChild(head);
    observeHeaderCompact(head);

    const stage = el("div", "osw-designer-preview-stage");
    card.appendChild(stage);

    card.__stage = stage;
    card.__section = section;
    card.__getMode = function () { return previewMode; };

    /* Below the stage: sliders and switches on the left, picture/colour slots
       on the right — the designs' two-column deck. Head-mounted choices are
       skipped here; they already live in the card header. */
    const fields = el("div", "osw-designer-deck osw-designer-preview-fields");
    if (section.id) fields.classList.add("osw-preview-section-" + section.id);
    const controlsCol = el("div", "osw-deck-col osw-deck-controls");
    const slotsCol = el("div", "osw-deck-col osw-deck-slots");
    const onigimonModeCol = section.id === "onigimon_scene"
      ? el("div", "osw-onigimon-mode-row osw-deck-full-width")
      : null;
    const onigimonScenarioCol = section.id === "onigimon_scene"
      ? el("div", "osw-onigimon-scenario-row osw-deck-full-width")
      : null;
    const compactFontFieldIds = {};
    (section.fontRoles || []).forEach(function (role) {
      (role.field_ids || []).forEach(function (fieldId) {
        compactFontFieldIds[fieldId] = true;
      });
    });
    const compactColorFieldIds = {};
    (section.colorGroups || []).forEach(function (group) {
      (group.field_ids || []).forEach(function (fieldId) {
        compactColorFieldIds[fieldId] = true;
      });
    });
    // A section with a compact color catalogue uses one full-width action
    // strip for both Fonts and Colors. The dense editor stays out of the two
    // balancing columns and the entry points remain immediately scannable.
    const compactMenuCol = (section.colorGroups || []).length
      ? el("div", "osw-designer-compact-menus osw-deck-full-width")
      : null;
    if ((section.modeParity || SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && (section.fontRoles || []).length) {
      const fontMenuRow = el("div", "osw-designer-font-menu-row");
      fontMenuRow.appendChild(compactFontMenuButton(section));
      (compactMenuCol || controlsCol).appendChild(fontMenuRow);
    }
    if ((section.colorGroups || []).length) {
      const colorMenuRow = el("div", "osw-designer-font-menu-row osw-designer-color-menu-row");
      colorMenuRow.appendChild(compactColorMenuButton(section));
      compactMenuCol.appendChild(colorMenuRow);
    }
    const subsectionByField = {};
    (section.subsections || []).forEach(function (subsection) {
      (subsection.fields || []).forEach(function (fieldId) {
        subsectionByField[fieldId] = subsection;
      });
    });
    function appendDeckNode(target, field, node) {
      const subsection = subsectionByField[field.id];
      // A designer can pin a whole labelled group to a column. Overview Style
      // uses this after its colors move into the compact gallery, placing
      // Notifications and Body in the newly available right-hand space.
      if (!section.stage_side && subsection && subsection.column === "left") {
        target = controlsCol;
      } else if (!section.stage_side && subsection && subsection.column === "right") {
        target = slotsCol;
      }
      if (!subsection) {
        target.appendChild(node);
        return;
      }
      if (!target.__subsections) target.__subsections = {};
      let group = target.__subsections[subsection.id];
      if (!group) {
        group = el("div", "osw-deck-subsection");
        group.setAttribute("data-subsection", subsection.id);
        group.appendChild(el("div", "osw-deck-subsection-title", subsection.title || ""));
        target.__subsections[subsection.id] = group;
        target.appendChild(group);
      }
      group.appendChild(node);
    }
    // Deck Stats has a large palette, while Hashi Notes has a compact palette
    // that otherwise leaves half its designer deck unused. Both use a
    // full-width grid below their regular controls.
    const isDeckStats = section.id === "mainmenu_deck_stats";
    const useFullWidthColorGrid = isDeckStats || !!section.full_width_color_grid;
    const colorGridCol = useFullWidthColorGrid ? el("div", "osw-deck-color-grid") : null;
    (section.fields || []).forEach(function (field) {
      if (field.head && !section.head_to_deck) return;
      if (compactFontFieldIds[field.id]) return;
      if (compactColorFieldIds[field.id]) return;
      if (deckSkipField(field.id)) return; // rendered below, next to its pair anchor
      const partnerId = DECK_PAIR_WITH[field.id];
      let placed = partnerId
        ? buildSideBySideRow(field, fieldById[partnerId])
        : renderDeckField(field);
      if (!placed) return;
      if (onigimonModeCol && field.id === "g_onigimon_scene_mode") {
        onigimonModeCol.appendChild(placed);
        return;
      }
      if (onigimonScenarioCol && field.id === "g_onigimon_scene_preset") {
        onigimonScenarioCol.appendChild(placed);
        return;
      }
      if (section.icon_colors_inline && field.type === "icon") {
        const colorsRow = placed;
        (ICON_POPUP_COMPANIONS[field.id] || []).forEach(function (id) {
          const companion = fieldById[id];
          if (companion) colorsRow.appendChild(renderIconTileColors(companion));
        });
      }
      if (colorGridCol && (field.type === "color_pair" || field.type === "color")) {
        appendDeckNode(colorGridCol, field, placed);
        return;
      }
      // Stage-side cards are one column in schema order — no slot/control
      // split to make (rebalanceDeck keeps it that way).
      if (section.stage_side) {
        appendDeckNode(controlsCol, field, placed);
        return;
      }
      if (field.deckPlacement === "right") {
        appendDeckNode(slotsCol, field, placed);
        return;
      }
      if (field.deckPlacement === "left") {
        appendDeckNode(controlsCol, field, placed);
        return;
      }
      appendDeckNode(DECK_SLOT_TYPES[field.type] ? slotsCol : controlsCol, field, placed);
    });
    // The scene's color fills behind either image type. Keep the visible right
    // column in a stable, intentional order even when an existing dialog was
    // built from an older field ordering: image, backdrop color, stats panel.
    if (section.id === "onigimon_scene") {
      [
        "g_onigimon_scene_image",
        "g_onigimon_scene_color",
        "g_onigimon_bottom_color"
      ].forEach(function (fieldId) {
        const node = slotsCol.querySelector('[data-field-host="' + fieldId + '"]');
        if (node) slotsCol.appendChild(node);
      });
    }
    // Deck Stats never populates slotsCol (every colour_pair went to
    // colorGridCol above), so controlsCol would otherwise sit alone in the
    // deck's 0.9fr column, cropped to under half width with a blank 1.1fr
    // column beside it — the two sliders in each fused row would only get a
    // quarter of the container each. Span it full width like colorGridCol.
    if (isDeckStats) controlsCol.classList.add("osw-deck-full-width");
    if (onigimonModeCol && onigimonModeCol.childNodes.length) fields.appendChild(onigimonModeCol);
    if (compactMenuCol && compactMenuCol.childNodes.length) fields.appendChild(compactMenuCol);
    if (controlsCol.childNodes.length) fields.appendChild(controlsCol);
    if (slotsCol.childNodes.length) fields.appendChild(slotsCol);
    if (onigimonScenarioCol && onigimonScenarioCol.childNodes.length) fields.appendChild(onigimonScenarioCol);
    if (colorGridCol && colorGridCol.childNodes.length) fields.appendChild(colorGridCol);
    wrap.appendChild(fields);
    card.__fieldsHost = fields;
    // rebalanceDeck moves rows between these two; keep references so it can
    // still find a column that started out empty and was never appended.
    card.__controlsCol = controlsCol;
    card.__slotsCol = slotsCol;
    card.__fullWidthColorGrid = section.full_width_color_grid ? colorGridCol : null;

    registerDesignerPreview(card);
    paintDesignerPreview(card);

    return wrap;
  }

  // ── Phase 1: Main Background preview ──────────────────────────────────────
  //
  // CSS does the cover-fit/blur/opacity compositing the Qt version hand-rolled
  // with QPainter (_page_backgrounds.py _render_main_background_preview_pixmap);
  // drag-to-pan is a plain background-position tweak, kept in-memory only (the
  // legacy pan offset isn't persisted either — it's a per-session dialog nicety).
  /* The Main Menu backdrop, painted exactly as the Background section paints
     it. Every other designer stage sits on it too — the widgets they preview
     are drawn over this background in the real menu, so judging a glass card
     or a stat tile against a flat grey would be judging the wrong thing.
     Returns the image layer (the Background section attaches drag-to-pan). */
  // Default (Main Background) field-id set. A second caller (Overviewer
  // Background — same generic designer, its own config-backed keys) passes
  // its own set rather than duplicating this whole function.
  const MAIN_BG_KEYS = {
    mode: "modern_menu_background_mode",
    colorLight: "modern_menu_bg_color_light",
    colorDark: "modern_menu_bg_color_dark",
    colorThemeMode: "modern_menu_bg_color_theme_mode",
    slideshowImages: "modern_menu_slideshow_images",
    imageLight: "modern_menu_background_image_light",
    imageDark: "modern_menu_background_image_dark",
    imageBase: "modern_menu_background_image",
    imageThemeMode: "modern_menu_bg_image_theme_mode",
    blur: "modern_menu_background_blur",
    opacity: "modern_menu_background_opacity",
    imageFolder: "main_bg",
  };

  const OVERVIEW_BG_KEYS = {
    mode: "overview_background_mode",
    colorLight: "overview_bg_color_light",
    colorDark: "overview_bg_color_dark",
    colorThemeMode: "overview_bg_color_theme_mode",
    imageLight: "overview_background_image_light",
    imageDark: "overview_background_image_dark",
    imageBase: "overview_background_image",
    imageThemeMode: "overview_bg_image_theme_mode",
    blur: "overview_background_blur",
    opacity: "overview_background_opacity",
    // Same shared folder as Main Background, not a separate "overview_bg" one
    // — see the folder comment on the overview_background_image field.
    imageFolder: "main_bg",
  };

  const REVIEWER_BG_KEYS = {
    mode: "reviewer_background_mode",
    colorLight: "reviewer_bg_color_light",
    colorDark: "reviewer_bg_color_dark",
    colorThemeMode: "reviewer_bg_color_theme_mode",
    slideshowImages: "reviewer_slideshow_images",
    imageLight: "reviewer_background_image_light",
    imageDark: "reviewer_background_image_dark",
    imageBase: "reviewer_background_image",
    imageThemeMode: "reviewer_bg_image_theme_mode",
    blur: "reviewer_background_blur",
    opacity: "reviewer_background_opacity",
    // Its own folder (not shared with Main/Overviewer) — matches the "reviewer_bg"
    // FOLDERS entry in settings_web/gallery.py.
    imageFolder: "reviewer_bg",
  };

  function designerPaintBackdrop(stage, vals, isDark, keys) {
    keys = keys || MAIN_BG_KEYS;
    const mode = vals[keys.mode] || "image_color";

    // Matching reads the live source, so subsequent source edits propagate too.
    if (mode === "main" && keys !== MAIN_BG_KEYS) {
      return designerPaintBackdrop(stage, vals, isDark, MAIN_BG_KEYS);
    }

    const colorLayer = el("div", "osw-bg-preview-layer");
    const color = designerPairValue(
      vals, keys.colorLight, keys.colorDark, keys.colorThemeMode, isDark
    ) || "#eeeeee";
    colorLayer.style.position = "absolute";
    colorLayer.style.inset = "0";
    colorLayer.style.background = color;
    stage.appendChild(colorLayer);

    if (mode === "color") return null;

    let imgName = "";
    if (mode === "slideshow") {
      const list = Array.isArray(vals[keys.slideshowImages]) ? vals[keys.slideshowImages] : [];
      imgName = list[0] || "";
    } else {
      imgName = designerPairValue(
        vals, keys.imageLight, keys.imageDark, keys.imageThemeMode, isDark, keys.imageBase
      );
    }
    if (!imgName) return null;
    const url = imageUrl(keys.imageFolder, imgName);
    if (!url) return null;

    const blur = Number(vals[keys.blur] || 0);
    let opacity = Number(vals[keys.opacity]);
    if (isNaN(opacity)) opacity = 100;

    const imgLayer = el("div", "osw-bg-preview-image");
    imgLayer.style.position = "absolute";
    imgLayer.style.inset = "0";
    imgLayer.style.backgroundImage = "url(\"" + url.replace(/"/g, "") + "\")";
    imgLayer.style.backgroundSize = "cover";
    imgLayer.style.backgroundPosition = stage.__bgPan || "center";
    imgLayer.style.filter = blur > 0 ? "blur(" + (blur * 0.18).toFixed(1) + "px)" : "";
    imgLayer.style.opacity = String(Math.max(0, Math.min(100, opacity)) / 100);
    stage.appendChild(imgLayer);
    return imgLayer;
  }

  function designerFieldFontFamily(vals, fieldId, fallbackRoleKey) {
    const selectedFontKey = vals[fieldId] || (fallbackRoleKey ? "sync" : "system");
    const fontKey = selectedFontKey === "sync" && fallbackRoleKey
      ? (vals["onigiri_font_" + fallbackRoleKey] || "system")
      : selectedFontKey;
    const field = fieldById[fieldId];
    let family = "";
    if (field && field.options) {
      const opt = field.options.filter(function (o) { return o.value === fontKey; })[0];
      if (opt && opt.family) family = opt.family;
    }
    if (!family && fontKey !== "system") family = fontKey;
    return family || "inherit";
  }

  /* Font family + size + colour of a font role. In Advanced mode, Sync with
     theme applies to the family only; the component's px size stays locally
     adjustable. Simple mode still uses only its three shared scales. */
  function designerFontRole(vals, roleKey, isDark, fallbackRoleKey, modeParity) {
    const selectedFontKey = vals["onigiri_font_" + roleKey] || "sync";
    const componentMode = modeParity || SETTINGS_MODE_PARITY || settingsComplexity === "advanced";
    const useFallbackFamily = fallbackRoleKey && (
      !componentMode || selectedFontKey === "sync"
    );
    const sizeRoleKey = componentMode || !fallbackRoleKey
      ? roleKey
      : fallbackRoleKey;
    return {
      family: useFallbackFamily
        ? designerFieldFontFamily(vals, "onigiri_font_" + fallbackRoleKey)
        : designerFieldFontFamily(vals, "onigiri_font_" + roleKey, fallbackRoleKey),
      size: Number(vals["onigiri_font_size_" + sizeRoleKey]) || 14,
      customColor: fontFieldColor(vals, "onigiri_font_" + roleKey, isDark),
      color: fontFieldColor(vals, "onigiri_font_" + roleKey, isDark) || designerPairValue(
        vals, "font_color_light_" + (fallbackRoleKey || roleKey),
        "font_color_dark_" + (fallbackRoleKey || roleKey),
        "font_color_" + (fallbackRoleKey || roleKey) + "_theme_mode", isDark
      ) || (isDark ? "#f4f4f5" : "#1f2933")
    };
  }

  function designerBackgroundPainter(stage, vals, isDark, keys) {
    stage.innerHTML = "";
    const imgLayer = designerPaintBackdrop(stage, vals, isDark, keys);
    if (!imgLayer) return;

    // Drag-to-pan: purely visual, not staged/persisted.
    let dragging = false;
    let startX = 0;
    let startY = 0;
    let startPos = { x: 50, y: 50 };
    function parsePan() {
      const parts = String(stage.__bgPan || "50% 50%").split(" ");
      return { x: parseFloat(parts[0]) || 50, y: parseFloat(parts[1]) || 50 };
    }
    stage.style.cursor = "grab";
    stage.onpointerdown = function (event) {
      dragging = true;
      stage.style.cursor = "grabbing";
      startX = event.clientX;
      startY = event.clientY;
      startPos = parsePan();
      stage.setPointerCapture(event.pointerId);
    };
    stage.onpointermove = function (event) {
      if (!dragging) return;
      const rect = stage.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const dx = ((event.clientX - startX) / rect.width) * -100;
      const dy = ((event.clientY - startY) / rect.height) * -100;
      const x = Math.max(0, Math.min(100, startPos.x + dx));
      const y = Math.max(0, Math.min(100, startPos.y + dy));
      stage.__bgPan = x.toFixed(1) + "% " + y.toFixed(1) + "%";
      imgLayer.style.backgroundPosition = stage.__bgPan;
    };
    stage.onpointerup = function () {
      dragging = false;
      stage.style.cursor = "grab";
    };
  }

  PREVIEW_PAINTERS.background = function (stage, vals, isDark) {
    designerBackgroundPainter(stage, vals, isDark, MAIN_BG_KEYS);
  };

  PREVIEW_PAINTERS.overview_background = function (stage, vals, isDark) {
    designerBackgroundPainter(stage, vals, isDark, OVERVIEW_BG_KEYS);
  };

  PREVIEW_PAINTERS.reviewer_background = function (stage, vals, isDark) {
    designerBackgroundPainter(stage, vals, isDark, REVIEWER_BG_KEYS);
  };

  // ── Phase 2: Widget Color and Effect preview ──────────────────────────────
  //
  // One sample "glass card" — box color/opacity/blur/radius/stroke plus a
  // 5-star row, mirroring _draw_box_effect_sample (settings/_infra.py:1608).
  // CSS backdrop-filter + rgba() replace the Qt blur-backdrop-sample + alpha
  // compositing the legacy renderer did by hand.

  const OSW_STAR_PATH = "M12 2.5l2.9 6.5 7.1.7-5.4 4.7 1.6 7-6.2-3.7-6.2 3.7 1.6-7-5.4-4.7 7.1-.7z";

  function designerStarRow(colorOn, colorOff, filledCount) {
    const row = el("div", "osw-preview-star-row");
    for (let i = 0; i < 5; i += 1) {
      const star = el("span", "osw-preview-star");
      star.style.background = i < filledCount ? colorOn : colorOff;
      star.style.webkitMaskImage = "url('data:image/svg+xml;utf8," +
        "<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22>" +
        "<path d=%22" + OSW_STAR_PATH + "%22/></svg>')";
      star.style.maskImage = star.style.webkitMaskImage;
      row.appendChild(star);
    }
    return row;
  }

  function designerGlassCardStyle(vals, isDark, opacityKey, blurKey, radiusKey, strokeKey, boxColor, borderColor) {
    const opacity = Math.max(0, Math.min(100, Number(vals[opacityKey])));
    const blur = Math.max(0, Number(vals[blurKey] || 0));
    const radius = Math.max(0, Number(vals[radiusKey] || 0));
    const stroke = Math.max(0, Number(vals[strokeKey] || 0));
    const alpha = Math.min((isNaN(opacity) ? 100 : opacity) / 100, blur > 0 ? 0.62 : 1);
    return {
      background: rgba(boxColor || "#ffffff", alpha),
      borderRadius: radius + "px",
      clipPath: "inset(0 round " + radius + "px)",
      border: stroke + "px solid " + (borderColor || "rgba(0,0,0,0.12)"),
      backdropFilter: blur > 0 ? "blur(" + ((blur / 100) * 20).toFixed(1) + "px)" : "",
      WebkitBackdropFilter: blur > 0 ? "blur(" + ((blur / 100) * 20).toFixed(1) + "px)" : ""
    };
  }

  PREVIEW_PAINTERS.widget_effect = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const boxColor = designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark);
    const borderColor = designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark);

    const holder = el("div", "osw-preview-stage-center");
    const card = el("div", "osw-preview-glass-card");
    const style = designerGlassCardStyle(
      vals, isDark, "onigiri_canvas_inset_effect_opacity", "onigiri_canvas_inset_effect_blur",
      "onigiri_canvas_inset_border_radius", "onigiri_canvas_inset_border_width", boxColor, borderColor
    );
    Object.keys(style).forEach(function (key) { card.style[key] = style[key]; });

    // Representative theme typography; this page now focuses only on the
    // shared widget surface and effects.
    [
      ["small_title", str("widget_titles", "Widget title")],
      ["main", str("widget_small_fonts", "Widget text")]
    ].forEach(function (entry) {
      const role = designerFontRole(vals, entry[0], isDark);
      const line = el("div", "osw-preview-glass-line", entry[1]);
      line.style.fontFamily = role.family;
      line.style.fontSize = role.size + "px";
      line.style.color = role.color;
      if (entry[0] === "small_title") line.style.fontWeight = "700";
      card.appendChild(line);
    });

    holder.appendChild(card);
    stage.appendChild(holder);
  };

  // ── Hashi Notes dashboard widget preview ─────────────────────────────────
  //
  // `render.py` injects the marked Hashi block from menu.css verbatim. Keep
  // this DOM identical to hashi_notes.render_widget_html(): the preview is a
  // real Main Menu widget given representative note content, not a separate
  // settings-only implementation that can drift over time.
  PREVIEW_PAINTERS.hashi_widget = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const dynamic = vals["hashi_widget_dynamic"] !== false;
    const themedDark = dynamic && isDark;
    const synced = vals["hashi_widget_sync"] !== false;
    function hashiColor(key, fallbackLight, fallbackDark) {
      return vals["hashi_widget_color_" + key + (themedDark ? "_dark" : "_light")]
        || (themedDark ? fallbackDark : fallbackLight);
    }

    const boxColor = synced
      ? designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      : hashiColor("box_bg", "#ffffff", "#2c2c2c");
    const borderColor = synced
      ? designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      : hashiColor("box_border", "#e0e0e0", "#424242");
    const cardColor = hashiColor("card_bg", "#f5f5f5", "#363636");
    const titleColor = hashiColor("title", "#212121", "#f0f0f0");
    const excerptColor = hashiColor("excerpt", "#757575", "#9c9c9c");
    const accentColor = hashiColor("accent", "#0077C8", "#4da3e8");
    const opacityKey = synced ? "onigiri_canvas_inset_effect_opacity" : "hashi_widget_opacity";
    const blurKey = synced ? "onigiri_canvas_inset_effect_blur" : "hashi_widget_blur";
    const radiusKey = synced ? "onigiri_canvas_inset_border_radius" : "hashi_widget_radius";
    const strokeKey = synced ? "onigiri_canvas_inset_border_width" : "hashi_widget_stroke";
    const blur = Math.max(0, Math.min(100, Number(vals[blurKey] || 0)));
    const opacity = Math.max(0, Math.min(100, Number(vals[opacityKey] == null ? 100 : vals[opacityKey])));
    const radius = Math.max(0, Math.min(60, Number(vals[radiusKey] || 0)));
    const stroke = Math.max(0, Math.min(10, Number(vals[strokeKey] || 0)));
    // This is patcher.py's _hw_rules() calculation: a blur caps the backdrop
    // alpha at .62, then the real menu CSS consumes the resulting variables.
    const boxAlpha = Math.min(opacity / 100, blur > 0 ? 0.62 : 1);
    const smallTitle = designerFontRole(vals, "small_title", isDark);
    const noteFontSize = Math.max(12, Math.min(24, Number(vals["hashi_note_font_size"]) || 14));

    const holder = el("div", "osw-preview-stage-center");
    const widget = el("div", "hashi-notes-widget");
    widget.style.width = "min(500px, 100%)";
    widget.style.height = "100%";
    widget.style.minHeight = "0";
    widget.style.setProperty("--onigiri-widget-pad", "19.6px");
    widget.style.setProperty("--hashiw-box-bg", rgba(boxColor, boxAlpha));
    widget.style.setProperty("--hashiw-box-border", borderColor);
    widget.style.setProperty("--hashiw-box-radius", radius + "px");
    widget.style.setProperty("--hashiw-box-stroke", stroke + "px");
    widget.style.setProperty("--hashiw-box-blur", ((blur / 100) * 20).toFixed(2) + "px");
    widget.style.setProperty("--hashiw-card-bg", cardColor);
    widget.style.setProperty("--hashiw-title-color", titleColor);
    widget.style.setProperty("--hashiw-excerpt-color", excerptColor);
    widget.style.setProperty("--hashiw-accent", accentColor);
    widget.style.setProperty("--font-small-title", smallTitle.family);
    widget.style.setProperty("--font-size-small-title", smallTitle.size + "px");
    widget.style.setProperty("--font-small-title-color", smallTitle.color);
    widget.style.setProperty("--fg", titleColor);
    widget.style.setProperty("--fg-subtle", excerptColor);
    widget.style.setProperty("--hashiw-card-excerpt-size", noteFontSize + "px");
    widget.style.setProperty("--hashiw-single-text-size", noteFontSize + "px");
    const single = (vals["hashi_widget_mode"] || "gallery") === "single";
    widget.classList.add(single ? "is-single" : "is-gallery");

    const head = el("div", "onigiri-widget-head");
    const heading = el("h3", "", str("hashi_notes_title", "Hashi Notes"));
    head.appendChild(heading);

    // These are regular Hashi paper colours, not settings-only card colours.
    // They deliberately have no title or icon, so the preview reads as a
    // collection of note papers and makes the Gallery's colour variety clear.
    const notes = [
      { light: "#fff0a8", dark: "#67582d", excerpt: "Link it to yesterday's topic." },
      { light: "#c9efcf", dark: "#345e48", excerpt: "Try it before checking the answer." },
      { light: "#c7e8f7", dark: "#315569", excerpt: "Keep this one handy for next time." },
      { light: "#f5d0e0", dark: "#6b4156", excerpt: "A quick note worth remembering." },
    ];
    function applySamplePaper(noteEl, note) {
      const paper = themedDark ? note.dark : note.light;
      const ink = themedDark ? "#fffdf7" : "#241f1b";
      noteEl.style.setProperty("--hashiw-note-fill", paper);
      noteEl.style.setProperty("--hashiw-note-fg", ink);
      noteEl.style.setProperty("--hashiw-note-fg2", ink);
      noteEl.style.setProperty("--hashiw-note-fg3", ink);
      noteEl.style.setProperty("--hashiw-note-edge", rgba(ink, 0.12));
    }
    function makeGalleryCard(note, index) {
      const noteEl = el("div", "hashi-widget-card");
      applySamplePaper(noteEl, note);
      if (vals["hashi_widget_show_excerpt"] !== false) {
        noteEl.appendChild(el("p", "hashi-widget-card-excerpt", note.excerpt));
      }
      if (vals["hashi_widget_show_date"] !== false) {
        noteEl.appendChild(el("span", "hashi-widget-card-date", index === 0 ? "Today" : "Yesterday"));
      }
      return noteEl;
    }

    if (single) {
      if (vals["hashi_widget_show_date"] !== false) {
        head.appendChild(el("span", "hashi-widget-date", "Today"));
      }
      widget.appendChild(head);
      const note = notes[0];
      const noteBody = el("div", "hashi-widget-single");
      applySamplePaper(widget, note);
      if (vals["hashi_widget_show_excerpt"] !== false) {
        noteBody.appendChild(el("p", "hashi-widget-excerpt", note.excerpt));
      }
      widget.appendChild(noteBody);
    } else {
      widget.appendChild(head);
      const cards = el("div", "hashi-widget-cards");
      const limit = Math.max(1, Math.min(4, Number(vals["hashi_widget_limit"]) || 4));
      notes.slice(0, limit).forEach(function (note, index) {
        cards.appendChild(makeGalleryCard(note, index));
      });
      widget.appendChild(cards);
    }
    holder.appendChild(widget);
    stage.appendChild(holder);
  };

  // Prep Station uses the same Main Menu classes and marked menu.css block as
  // the live widget. Only the plan data is representative; every appearance
  // control follows the same sync/local choice as the runtime widget.
  PREVIEW_PAINTERS.prep_widget = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);
    const dynamic = vals["prep_widget_dynamic"] !== false;
    const themedDark = dynamic && isDark;
    const synced = vals["prep_widget_sync"] !== false;
    function prepColor(key, fallbackLight, fallbackDark) {
      return vals["prep_widget_color_" + key + (themedDark ? "_dark" : "_light")]
        || (themedDark ? fallbackDark : fallbackLight);
    }
    const boxColor = synced
      ? designerPairValue(
          vals, "widget_box_color_light", "widget_box_color_dark",
          "onigiri_canvas_inset_color_theme_mode", isDark
        ) || (isDark ? "#2c2c2c" : "#ffffff")
      : prepColor("box_bg", "#ffffff", "#2c2c2c");
    const borderColor = synced
      ? designerPairValue(
          vals, "widget_border_color_light", "widget_border_color_dark",
          "onigiri_canvas_inset_color_theme_mode", isDark
        ) || (isDark ? "#424242" : "#e0e0e0")
      : prepColor("box_border", "#e0e0e0", "#424242");
    const opacityKey = synced ? "onigiri_canvas_inset_effect_opacity" : "prep_widget_opacity";
    const blurKey = synced ? "onigiri_canvas_inset_effect_blur" : "prep_widget_blur";
    const radiusKey = synced ? "onigiri_canvas_inset_border_radius" : "prep_widget_radius";
    const strokeKey = synced ? "onigiri_canvas_inset_border_width" : "prep_widget_stroke";
    const blur = Math.max(0, Math.min(100, Number(vals[blurKey] || 0)));
    const opacity = Math.max(0, Math.min(100, Number(vals[opacityKey] == null ? 100 : vals[opacityKey])));
    const radius = Math.max(0, Math.min(60, Number(vals[radiusKey] == null ? 20 : vals[radiusKey])));
    const stroke = Math.max(0, Math.min(10, Number(vals[strokeKey] == null ? 1 : vals[strokeKey])));
    const alpha = Math.min(opacity / 100, blur > 0 ? 0.62 : 1);
    const holder = el("div", "osw-preview-stage-center");
    const widget = el("div", "prep-station-widget");
    widget.style.width = "min(560px, 100%)";
    widget.style.height = "100%";
    widget.style.minHeight = "0";
    widget.style.setProperty("--onigiri-widget-pad", "19.6px");
    widget.style.setProperty("--prep-fs", String(Math.max(60, Math.min(160, Number(vals["prep_widget_font_scale"] || 100))) / 100));
    widget.style.setProperty("--prepw-box-bg", rgba(boxColor, alpha));
    widget.style.setProperty("--prepw-box-border", borderColor);
    widget.style.setProperty("--prepw-box-radius", radius + "px");
    widget.style.setProperty("--prepw-box-stroke", stroke + "px");
    widget.style.setProperty("--prepw-box-blur", ((blur / 100) * 20).toFixed(1) + "px");
    const head = el("div", "onigiri-widget-head");
    head.appendChild(el("h3", "", str("prep_widget_title", "Study Plans")));
    widget.appendChild(head);
    const cards = el("div", "prep-plan-cards");
    const plans = [
      ["#d97757", "12 days", "Biology", "24", "cards/day", "18/30", "60%"],
      ["#4b92c6", "20 days", "History", "16", "cards/day", "12/24", "50%"],
      ["#8768c7", "31 days", "Physics", "12", "cards/day", "21/28", "75%"],
      ["#49a579", "45 days", "Language", "8", "cards/day", "9/20", "45%"],
    ];
    plans.forEach(function (plan) {
      const card = el("div", "prep-plan-card");
      const band = el("div", "prep-card-band");
      band.style.backgroundColor = plan[0];
      const bandTop = el("div", "prep-card-band-top");
      bandTop.appendChild(el("span", "prep-card-badge", plan[1]));
      const name = el("div", "prep-card-name-row");
      name.appendChild(el("span", "prep-card-name", plan[2]));
      band.appendChild(bandTop);
      band.appendChild(name);
      const body = el("div", "prep-card-body");
      const pace = el("div", "prep-card-pace");
      const num = el("span", "prep-card-pace-num", plan[3]);
      num.style.color = plan[0];
      pace.appendChild(num);
      pace.appendChild(el("span", "prep-card-pace-unit", plan[4]));
      const progress = el("div", "prep-card-progress");
      const track = el("span", "prep-card-progress-track");
      const fill = el("i", "prep-card-progress-fill");
      fill.style.width = plan[6];
      fill.style.background = plan[0];
      track.appendChild(fill);
      progress.appendChild(track);
      progress.appendChild(el("span", "prep-card-progress-label", plan[5]));
      body.appendChild(pace);
      body.appendChild(progress);
      card.appendChild(band);
      card.appendChild(body);
      cards.appendChild(card);
    });
    widget.appendChild(cards);
    holder.appendChild(widget);
    stage.appendChild(holder);
  };

  PREVIEW_PAINTERS.pomodoro = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);
    const dynamic = vals["pomodoro_dynamic"] !== false;
    const mode = dynamic && isDark ? "dark" : "light";
    // Chrome follows the displayed theme; Dynamic Mode only selects explicit
    // appearance overrides, matching the native timer's palette resolution.
    const fallback = isDark
      ? { shell: "#2b2c30", accent: CTX.accent || "#00A982", digits: "#f1f2f4", icon: "#b0b3ba", border: "#45464b" }
      : { shell: "#f8f8f7", accent: CTX.accent || "#00A982", digits: "#202124", icon: "#63666c", border: "#e3e4e7" };
    function color(role) { return vals["pomodoro_color_" + role + "_" + mode] || fallback[role]; }
    const style = vals["pomodoro_style"] === "dashboard" ? "dashboard" : "minimal";
    const preset = {
      minimal: {
        width: 230, height: 200, pad: [14, 10, 14, 14], spacing: 8,
        radius: 18, topbar: 26, icon: 16, chip: 22, time: 40,
        phase: 11, dot: 13, play: 38, button: 30
      },
      dashboard: {
        width: 270, height: 264, pad: [16, 12, 16, 16], spacing: 9,
        radius: 20, topbar: 28, icon: 17, chip: 24, time: 48,
        phase: 11, dot: 14, play: 42, button: 32
      },
    }[style];
    const opacity = Math.max(0, Math.min(100, Number(vals["pomodoro_opacity"] == null ? 100 : vals["pomodoro_opacity"])));
    const blur = Math.max(0, Math.min(100, Number(vals["pomodoro_blur"] || 0)));
    const fontField = fieldById["pomodoro_font"] || {};
    const font = (fontField.options || []).filter(function (option) { return option.value === vals["pomodoro_font"]; })[0];

    // Use the floating timer's real state. When it is running, advance the
    // captured remainder locally so the preview stays in lockstep without a
    // bridge round-trip every second.
    const source = CTX.pomodoroState || {};
    const phase = ["focus", "short_break", "long_break"].indexOf(source.phase) >= 0
      ? source.phase : "focus";
    const total = Math.max(1, Number(source.total) || 1);
    const elapsed = source.running
      ? Math.max(0, Math.floor((Date.now() - Number(source.capturedAtMs || Date.now())) / 1000))
      : 0;
    // A timer cannot persist at exactly zero (PomodoroTimer immediately moves
    // to the next phase). Treat a zero captured during that transition as the
    // freshly prepared phase, matching the native view on its next paint.
    const capturedRemaining = Number(source.remaining);
    const baselineRemaining = capturedRemaining > 0 ? capturedRemaining : total;
    const remaining = Math.max(0, Math.min(total, baselineRemaining - elapsed));
    const cycleTotal = Math.max(1, Number(source.cycleTotal) || 4);
    const focusCount = Math.max(0, Number(source.focusCount) || 0);
    function phaseName(value) {
      return {
        focus: str("pomodoro_focus", "Focus"),
        short_break: str("pomodoro_short_break", "Short Break"),
        long_break: str("pomodoro_long_break", "Long Break")
      }[value] || value;
    }
    function nextPhase() {
      if (phase !== "focus") return "focus";
      return focusCount + 1 >= cycleTotal ? "long_break" : "short_break";
    }
    function formatTime(seconds) {
      const minutes = Math.floor(seconds / 60);
      return String(minutes).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
    }

    const holder = el("div", "osw-preview-stage-center osw-pomo-preview-holder");
    const windowFrame = el("div", "osw-pomo-window is-" + style);
    const island = el("div", "osw-pomo-island is-" + style);
    island.style.setProperty("--pomo-shell", rgba(color("shell"), opacity / 100));
    island.style.setProperty("--pomo-accent", color("accent"));
    island.style.setProperty("--pomo-digits", color("digits"));
    island.style.setProperty("--pomo-icon", color("icon"));
    island.style.setProperty("--pomo-border", fallback.border);
    island.style.setProperty("--pomo-track", rgba(color("icon"), 0.22));
    island.style.setProperty("--pomo-tile", rgba(color("icon"), 0.10));
    island.style.setProperty("--pomo-tile-border", rgba(color("icon"), 0.18));
    windowFrame.style.setProperty("--pomo-window-width", preset.width + "px");
    windowFrame.style.setProperty("--pomo-window-height", preset.height + "px");
    island.style.setProperty("--pomo-pad-left", preset.pad[0] + "px");
    island.style.setProperty("--pomo-pad-top", preset.pad[1] + "px");
    island.style.setProperty("--pomo-pad-right", preset.pad[2] + "px");
    island.style.setProperty("--pomo-pad-bottom", preset.pad[3] + "px");
    island.style.setProperty("--pomo-spacing", preset.spacing + "px");
    island.style.setProperty("--pomo-radius", preset.radius + "px");
    island.style.setProperty("--pomo-topbar", preset.topbar + "px");
    island.style.setProperty("--pomo-icon-size", preset.icon + "px");
    island.style.setProperty("--pomo-chip", preset.chip + "px");
    island.style.setProperty("--pomo-dot", preset.dot + "px");
    island.style.setProperty("--pomo-time", preset.time + "px");
    island.style.setProperty("--pomo-phase", preset.phase + "px");
    island.style.setProperty("--pomo-play", preset.play + "px");
    island.style.setProperty("--pomo-button", preset.button + "px");
    island.style.setProperty("--pomo-font", font && font.family ? font.family : "Poppins, sans-serif");
    island.style.backdropFilter = blur > 0 ? "blur(" + ((blur / 100) * 20).toFixed(1) + "px)" : "";
    island.style.WebkitBackdropFilter = island.style.backdropFilter;
    const top = el("div", "osw-pomo-top");
    const timerIcon = designerIconGlyph(iconValue("pomodoro_icon"), color("accent"), preset.icon);
    timerIcon.classList.add("osw-pomo-icon");
    top.appendChild(timerIcon);
    top.appendChild(el("span", "osw-pomo-phase", phaseName(phase)));
    const topActions = el("span", "osw-pomo-top-actions");
    const statsButton = el("button", "osw-pomo-top-button");
    statsButton.type = "button";
    statsButton.tabIndex = -1;
    statsButton.appendChild(designerIconGlyph("system:stats.svg", color("icon"), preset.icon - 2));
    const closeButton = el("button", "osw-pomo-top-button osw-pomo-close", "✕");
    closeButton.type = "button";
    closeButton.tabIndex = -1;
    topActions.appendChild(statsButton);
    topActions.appendChild(closeButton);
    top.appendChild(topActions);
    island.appendChild(top);
    island.appendChild(el("div", "osw-pomo-time", formatTime(remaining)));
    if (style !== "minimal") {
      const progress = el("div", "osw-pomo-progress");
      const fill = el("i", "", "");
      fill.style.width = ((1 - remaining / total) * 100).toFixed(3) + "%";
      if (remaining < total) fill.style.minWidth = "6px";
      progress.appendChild(fill);
      island.appendChild(progress);
    }
    const dots = el("div", "osw-pomo-dots");
    for (let index = 0; index < cycleTotal; index += 1) {
      const filled = index < Math.min(focusCount, cycleTotal);
      const dot = designerIconGlyph(
        iconValue("pomodoro_icon"), filled ? color("accent") : color("icon"), preset.dot
      );
      if (!filled) dot.style.opacity = ".35";
      dots.appendChild(dot);
    }
    island.appendChild(dots);
    if (style !== "minimal") {
      const session = str("pomodoro_session_of", "Session {n} of {total}")
        .replace("{n}", String(Math.min(focusCount + 1, cycleTotal)))
        .replace("{total}", String(cycleTotal));
      island.appendChild(el(
        "div", "osw-pomo-meta",
        session + "  ·  " + str("pomodoro_next", "Next:") + " " + phaseName(nextPhase())
      ));
    }
    const controls = el("div", "osw-pomo-controls");
    controls.appendChild(el("button", "", "⟲"));
    controls.appendChild(el("button", "osw-pomo-play", source.running ? "⏸" : "▶"));
    controls.appendChild(el("button", "", "⏭"));
    island.appendChild(controls);
    windowFrame.appendChild(island);
    holder.appendChild(windowFrame);
    stage.appendChild(holder);

    stage.__pomoTickDark = isDark;
    if (!stage.__pomoTickTimer) {
      stage.__pomoTickTimer = setInterval(function () {
        if (!document.body.contains(stage)) {
          clearInterval(stage.__pomoTickTimer);
          stage.__pomoTickTimer = null;
          return;
        }
        if (source.running) {
          PREVIEW_PAINTERS.pomodoro(stage, values, stage.__pomoTickDark);
        }
      }, 1000);
    }
  };

  // ── Games > Notifications preview ─────────────────────────────────────────
  //
  // The real toast, not a lookalike: render.py embeds web/notifications.css and
  // web/notifications.js, and both the preview and reviewer call that script's
  // element factory. Only the positioner is local because the live stack is
  // fixed to the window; `.osw-notifstage-stack` maps the same six anchors into
  // the bounded preview screen.

  /* The reviewer header's button chips as patcher.py draws them: the
     --onigiri-box-effect-* vars, which are the Widget Color and Effect fields
     plus the palette's own --fg. Mini notifications live inside that row, so
     the row has to be there for the preview to mean anything. */
  function notifHeaderButtonStyle(vals, isDark) {
    const boxColor = designerPairValue(
      vals, "widget_box_color_light", "widget_box_color_dark",
      "onigiri_canvas_inset_color_theme_mode", isDark
    );
    const borderColor = designerPairValue(
      vals, "widget_border_color_light", "widget_border_color_dark",
      "onigiri_canvas_inset_color_theme_mode", isDark
    );
    const style = designerGlassCardStyle(
      vals, isDark, "onigiri_canvas_inset_effect_opacity", "onigiri_canvas_inset_effect_blur",
      "onigiri_canvas_inset_border_radius", "onigiri_canvas_inset_border_width",
      boxColor || (isDark ? "#2c2c2c" : "#ffffff"),
      borderColor || (isDark ? "#3a3a3a" : "#d9d9d9")
    );
    style.color = (isDark ? vals["gal_fg_dark"] : vals["gal_fg_light"])
      || (isDark ? "#e0e0e0" : "#212121");
    return style;
  }

  function createLiveNotificationElement(payload, mini) {
    const notifications = window.OnigiriNotifications;
    if (!notifications || typeof notifications.createElement !== "function") return null;
    const card = notifications.createElement(payload, mini ? "mini" : "classic");
    card.classList.add("is-visible");
    return card;
  }

  function buildNotificationHeader(vals, isDark) {
    const header = el("div", "osw-notifstage-header");
    const btnStyle = notifHeaderButtonStyle(vals, isDark);
    const buttons = el("div", "osw-notifstage-buttons");
    ["Decks", "Add", "Browse", "Stats", "Sync"].forEach(function (label) {
      const chip = el("span", "osw-notifstage-btn", label);
      Object.keys(btnStyle).forEach(function (key) { chip.style[key] = btnStyle[key]; });
      buttons.appendChild(chip);
    });
    buttons.style.setProperty(
      "--onigiri-box-effect-radius", btnStyle.borderRadius || "8px"
    );
    header.appendChild(buttons);
    return { header: header, buttons: buttons };
  }

  /* Paints a review-screen notification with the live runtime's own DOM
     factory and stylesheet. The stage only substitutes absolute positioning
     for the reviewer's fixed viewport positioning. */
  function paintLiveNotification(stage, vals, isDark, payload) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark, REVIEWER_BG_KEYS);

    const surface = el("div", "osw-notifstage" + (isDark ? " night-mode" : ""));
    // A preview reflects the notification-style setting itself. It supplies
    // Mini's required header mount locally, so unrelated reviewer-layout
    // settings can never make a selected Mini preview look like Classic.
    const mini = (vals.g_notification_mode || "classic") === "mini";
    const silent = !!vals.g_silent_mode;
    let headerButtons = null;

    if (mini) {
      const headerParts = buildNotificationHeader(vals, isDark);
      headerButtons = headerParts.buttons;
      surface.appendChild(headerParts.header);
    }

    const card = createLiveNotificationElement(payload, mini);
    const notificationInk = fontFieldColor(vals, "onigiri_font_notifications", isDark);
    if (card && notificationInk) card.style.setProperty("color", notificationInk, "important");
    if (card && mini && headerButtons) {
      headerButtons.appendChild(card);
    } else if (card) {
      const position = vals.g_notification_position || "top-center";
      const stack = el("div", "osw-notifstage-stack is-" + position);
      stack.appendChild(card);
      surface.appendChild(stack);
    }

    if (silent) {
      surface.classList.add("is-silent");
      surface.appendChild(el(
        "div", "osw-notifstage-silent",
        str("notif_preview_silent", "Silent mode: nothing is shown")
      ));
    }

    stage.appendChild(surface);
  }

  PREVIEW_PAINTERS.notification = function (stage, vals, isDark) {
    paintLiveNotification(stage, vals, isDark, {
      name: str("notif_preview_title", "Onigiri"),
      description: str("notif_preview_desc", "Level 4 reached — nice work!"),
      icon: "On"
    });
  };

  // ── Phase 3: Stats Widgets preview ────────────────────────────────────────
  //
  // Four sample cards (Studied/Time/Pace/Retention) with demo values, mirroring
  // _draw_stats_widgets_card (settings/_page_stats_widgets.py:935). "Sync with
  // Widget Color and Effect" reads Phase 2's fields instead of its own when on
  // (_stats_widgets_effect_values in the legacy dialog).

  function statsWidgetsEffectValues(vals, isDark) {
    if (vals["swidget_sync_box_effect"]) {
      return {
        blur: vals["onigiri_canvas_inset_effect_blur"],
        opacity: vals["onigiri_canvas_inset_effect_opacity"],
        radius: vals["onigiri_canvas_inset_border_radius"],
        stroke: vals["onigiri_canvas_inset_border_width"],
        boxBg: designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark),
        boxBorder: designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      };
    }
    return {
      blur: vals["swidget_blur"], opacity: vals["swidget_opacity"],
      radius: vals["swidget_radius"], stroke: vals["swidget_stroke"],
      boxBg: designerPairValue(vals, "swidget_color_box_bg_light", "swidget_color_box_bg_dark", null, isDark),
      boxBorder: designerPairValue(vals, "swidget_color_box_border_light", "swidget_color_box_border_dark", null, isDark)
    };
  }

  // Value and unit are separate exactly as the real card splits them, so the
  // "Show units" switch has the same effect here as on the menu.
  const SW_DEMO = {
    studied: { label: str("studied", "Studied"), value: "128", unit: str("cards", "cards"), series: [40, 55, 48, 70, 62, 90, 82] },
    time: { label: str("time", "Time"), value: "42.0", unit: str("minutes_short", "min"), series: [20, 35, 30, 45, 40, 55, 50] },
    pace: { label: str("pace", "Pace"), value: "1.8", unit: str("seconds_per_card", "s/card"), series: [10, 18, 15, 22, 19, 26, 24] },
    retention: { label: str("retention", "Retention"), value: "87%", unit: "", series: [70, 75, 72, 80, 78, 85, 87] }
  };

  const OSW_STAR_MASK = "url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22>" +
    "<path d=%22M12 2.5l2.9 6.5 7.1.7-5.4 4.7 1.6 7-6.2-3.7-6.2 3.7 1.6-7-5.4-4.7 7.1-.7z%22/></svg>')";

  /* Data URI for an icon value ("system:check.svg", "mine.svg", "emoji:🍙").
     Python ships the whole picker's inventory in CTX.iconAssets, so a value
     picked mid-session resolves without another round trip. */
  function iconAssetUrl(value) {
    const key = String(value || "");
    if (!key || key.indexOf("emoji:") === 0) return "";
    const bundled = (CTX.iconAssets || {})[key];
    if (bundled) return bundled;
    // Icons imported while Settings is already open are returned by the
    // picker bridge and live in userIcons, but are not part of the immutable
    // boot context. Preview painters must be able to use them immediately.
    const imported = userIcons.filter(function (item) { return item.name === key; })[0];
    return imported ? imported.url : "";
  }

  // Some icon fields' schema default is a bare filename (e.g. heatmapShape's
  // "square.svg") rather than the "system:square.svg" form the picker itself
  // always writes — heatmap.py's own shape_file_path() is lenient about this
  // (falls back to the system dir when there's no prefix), but the asset map
  // only ever keys system icons with the prefix. A plain iconAssetUrl() on an
  // untouched default field would come back empty and paint as "—" instead
  // of the actual default icon.
  function resolveIconAssetUrl(value) {
    const raw = String(value || "");
    if (!raw || raw.indexOf("emoji:") === 0) return "";
    return iconAssetUrl(raw) || (raw.indexOf(":") === -1 ? iconAssetUrl("system:" + raw) : "");
  }

  /* The stored value for an icon a user has never changed is an empty string,
     not the bundled filename — legacy wrote "" to mean "use the default"
     (settings/_page_sidebar.py:1601). So an icon slot, and every preview that
     draws one, has to fall back to the schema default or the deck browser shows
     its folder/deck/subdeck glyphs while the settings dialog shows nothing. */
  function iconValue(fieldId) {
    const raw = values[fieldId];
    if (raw !== undefined && raw !== null && raw !== "") return raw;
    const field = fieldById[fieldId];
    return (field && field.default) || "";
  }

  function sparklinePath(series, w, h) {
    if (!series.length) return "";
    const min = Math.min.apply(null, series);
    const max = Math.max.apply(null, series);
    const span = (max - min) || 1;
    const pts = series.map(function (v, i) {
      return [ (i / (series.length - 1)) * w, h - ((v - min) / span) * h ];
    });
    let d = "M" + pts[0][0].toFixed(1) + "," + pts[0][1].toFixed(1);
    for (let i = 1; i < pts.length; i += 1) {
      const mx = (pts[i - 1][0] + pts[i][0]) / 2;
      d += " Q" + pts[i - 1][0].toFixed(1) + "," + pts[i - 1][1].toFixed(1) + " " + mx.toFixed(1) + "," + ((pts[i - 1][1] + pts[i][1]) / 2).toFixed(1);
    }
    d += " L" + pts[pts.length - 1][0].toFixed(1) + "," + pts[pts.length - 1][1].toFixed(1);
    return d;
  }

  /* Same markup and the same CSS the menu uses (_stats_widget_card_html in
     onigiri_renderer.py + the marked block of menu.css), driven by the same
     --swidget-* variables patcher.generate_dynamic_css emits. Changing a colour
     here therefore changes the preview exactly the way it changes the menu. */
  /* Colour lookup with the same rule the real CSS generator uses: with Dynamic
     mode off every theme reads the light palette (patcher._sw_color), so the
     preview must not quietly take the dark one. */
  function swidgetColor(vals, key, isDark, fallbackLight, fallbackDark) {
    const dynamic = vals["swidget_dynamic"] !== false;
    const useDark = dynamic && isDark;
    return values_or(vals["swidget_color_" + key + (useDark ? "_dark" : "_light")],
                     useDark ? fallbackDark : fallbackLight);
  }

  function values_or(value, fallback) {
    return (typeof value === "string" && value) ? value : fallback;
  }

  function swidgetVars(vals, isDark) {
    const eff = statsWidgetsEffectValues(vals, isDark);
    const opacity = Math.max(0, Math.min(100, Number(eff.opacity)));
    const blur = Math.max(0, Number(eff.blur || 0));
    let boxBg = eff.boxBg || (isDark ? "#2c2c2c" : "#ffffff");
    if (!vals["swidget_sync_box_effect"]) {
      boxBg = swidgetColor(vals, "box_bg", isDark, "#ffffff", "#2c2c2c");
    }
    if (!vals["swidget_sync_box_effect"]) {
      let alpha = (isNaN(opacity) ? 100 : opacity) / 100;
      if (blur > 0) alpha = Math.min(alpha, 0.62);
      if (alpha < 1) boxBg = rgba(boxBg, alpha);
    }
    const widgetRoleSize = function (role, fallback) {
      if (!SETTINGS_MODE_PARITY && settingsComplexity !== "advanced") {
        const baseRole = role === "widget_title" ? "small_title" : "main";
        return Math.max(8, Math.min(72, Number(vals["onigiri_font_size_" + baseRole]) || fallback));
      }
      return Math.max(8, Math.min(72, Number(vals["onigiri_font_size_" + role]) || fallback));
    };
    const labelSize = (SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && vals["swidget_label_size_sync"] === false
      ? Math.max(8, Math.min(72, Number(vals["swidget_label_size"]) || 15))
      : widgetRoleSize("widget_title", 15);
    const valueSize = (SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && vals["swidget_value_size_sync"] === false
      ? Math.max(8, Math.min(72, Number(vals["swidget_value_size"]) || 30))
      : widgetRoleSize("widget_small", 14);
    const numberSize = (SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && vals["swidget_number_size_sync"] === false
      ? Math.max(8, Math.min(72, Number(vals["swidget_number_size"]) || 30))
      : widgetRoleSize("widget_small", 14);
    const statsRoleFont = function (fieldId, widgetRole, simpleRole) {
      if ((SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && (vals[fieldId] || "sync") !== "sync") {
        return designerFieldFontFamily(vals, fieldId);
      }
      return designerFontRole(vals, widgetRole, isDark, simpleRole).family;
    };
    const out = {
      "--swidget-box-bg": boxBg,
      "--swidget-box-border": vals["swidget_sync_box_effect"]
        ? (eff.boxBorder || (isDark ? "#424242" : "#e0e0e0"))
        : swidgetColor(vals, "box_border", isDark, "#e0e0e0", "#424242"),
      "--swidget-box-radius": Math.max(0, Number(eff.radius || 0)) + "px",
      "--swidget-box-stroke": Math.max(0, Number(eff.stroke || 0)) + "px",
      "--swidget-box-blur": ((blur / 100) * 20).toFixed(2) + "px",
      "--swidget-label-font": statsRoleFont("swidget_label_font", "widget_title", "small_title"),
      "--swidget-value-font": statsRoleFont("swidget_value_font", "widget_small", "main"),
      "--swidget-number-font": statsRoleFont("swidget_number_font", "widget_small", "main"),
      "--swidget-label-size": labelSize.toFixed(2) + "px",
      "--swidget-label-color": fontFieldColor(vals, "swidget_label_font", isDark) || swidgetColor(vals, "label", isDark, "#757575", "#9c9c9c"),
      "--swidget-value-color": fontFieldColor(vals, "swidget_value_font", isDark) || swidgetColor(vals, "value", isDark, "#212121", "#f0f0f0"),
      "--swidget-value-size": valueSize.toFixed(2) + "px",
      "--swidget-number-size": numberSize.toFixed(2) + "px",
      // Same base gutter as menu.css's --onigiri-widget-pad (before the user's
      // pad scale, which the dialog does not expose).
      "--onigiri-widget-pad": "14px",
      // Stars have their own editable colours — see the .star rules in the
      // marked menu.css block.
      "--star-color": "currentColor",
      "--empty-star-color": "currentColor"
    };
    const accentFallback = {
      studied: ["#5eaadf", "#6bb6ec"], time: ["#8b7bd8", "#a294ea"],
      pace: ["#f5a05a", "#f7ad6b"], retention: ["#26a641", "#35b850"]
    };
    ["studied", "time", "pace", "retention"].forEach(function (key) {
      const accent = swidgetColor(vals, key, isDark, accentFallback[key][0], accentFallback[key][1]);
      out["--swidget-" + key + "-accent"] = accent;
      out["--swidget-" + key + "-chip"] = rgba(accent, 0.16);
      out["--swidget-" + key + "-wash"] = rgba(accent, 0.10);
      if (key === "retention") {
        out["--swidget-retention-star"] = swidgetColor(vals, "retention_star", isDark, "#FFD700", "#FFD700");
        out["--swidget-retention-empty-star"] = swidgetColor(vals, "retention_star_empty", isDark, "#e0e0e0", "#4a4a4a");
      }
    });
    return out;
  }

  /* Catmull-Rom in cubic form — the JS twin of _stats_widget_smooth_path, so a
     curved trend line bends the same way in both places. */
  function swidgetSmoothPath(points) {
    if (points.length < 2) return "";
    let d = "M " + points[0][0].toFixed(1) + "," + points[0][1].toFixed(1);
    for (let i = 0; i < points.length - 1; i += 1) {
      const p0 = i > 0 ? points[i - 1] : points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = i + 2 < points.length ? points[i + 2] : points[i + 1];
      const c1x = p1[0] + (p2[0] - p0[0]) / 6;
      const c1y = p1[1] + (p2[1] - p0[1]) / 6;
      const c2x = p2[0] - (p3[0] - p1[0]) / 6;
      const c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += " C " + c1x.toFixed(1) + "," + c1y.toFixed(1) + " " + c2x.toFixed(1) + "," + c2y.toFixed(1) +
           " " + p2[0].toFixed(1) + "," + p2[1].toFixed(1);
    }
    return d;
  }

  function swidgetSparkHtml(series, smooth) {
    const values = (series || []).map(function (v) { return Math.max(0, Number(v) || 0); });
    if (values.length < 2) return "";
    const low = Math.min.apply(null, values);
    const high = Math.max.apply(null, values);
    const flat = (high - low) < 1e-9;
    const width = 100;
    const height = 28;
    const step = width / (values.length - 1);
    const points = values.map(function (value, index) {
      const fraction = flat ? 0.5 : (value - low) / (high - low);
      return [index * step, height - 3 - fraction * (height - 6)];
    });
    const line = (smooth && !flat)
      ? swidgetSmoothPath(points)
      : "M " + points.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" L ");
    const fill = flat ? "" :
      '<path class="stat-spark-fill" d="' + line + " L " + width + "," + height + " L 0," + height + ' Z"></path>';
    return '<svg class="stat-spark" viewBox="0 0 ' + width + " " + height + '" preserveAspectRatio="none" aria-hidden="true">' +
      fill + '<path class="stat-spark-line" d="' + line + '"></path></svg>';
  }

  /* The star row owns its own Stats Widgets picker and colours. It deliberately
     avoids the menu-wide `.star` class, whose icon belongs to legacy cards. */
  function swidgetStarsHtml(vals, filled) {
    const raw = String(vals["swidget_icon_retention_star"] || "system:star.svg");
    const emoji = raw.indexOf("emoji:") === 0
      ? raw.slice(6)
      : (raw && raw.length <= 8 && raw.indexOf(".") === -1 && raw.indexOf("system:") !== 0 ? raw : "");
    const url = emoji ? "" : (iconAssetUrl(raw) || iconAssetUrl("system:star.svg"));
    let out = '<div class="star-rating">';
    for (let i = 0; i < 5; i += 1) {
      const cls = "stats-widget-star" + (i < filled ? "" : " empty");
      if (emoji) {
        out += '<span class="' + cls + ' is-emoji">' + emoji + "</span>";
      } else {
        out += '<span class="' + cls + '" style="-webkit-mask-image:url(\'' + url + '\');mask-image:url(\'' + url + '\')"></span>';
      }
    }
    return out + "</div>";
  }

  PREVIEW_PAINTERS.stats_widgets = function (stage, vals, isDark) {
    // A structural change (Style/Chart) rebuilds every card's markup — icon
    // chip and sparkline appear or vanish, nothing to tween. Crossfading the
    // whole row in is what keeps that read as a transition instead of a cut;
    // colour/slider edits repaint too often for a fade to be worth doing then.
    const structuralKey = vals["swidget_design"] + "|" + vals["swidget_chart_shape"];
    const shouldFade = stage.__swidgetKey !== undefined && stage.__swidgetKey !== structuralKey;
    stage.__swidgetKey = structuralKey;

    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const row = el("div", "osw-preview-stage-center osw-preview-swidget-row" + (shouldFade ? " is-fading-in" : ""));
    if (shouldFade) {
      requestAnimationFrame(function () { row.classList.remove("is-fading-in"); });
    }
    const vars = swidgetVars(vals, isDark);
    Object.keys(vars).forEach(function (key) { row.style.setProperty(key, vars[key]); });

    const design = vals["swidget_design"] === "expressive" ? "expressive" : "minimal";
    const showUnits = vals["swidget_show_units"] !== false;
    const showIcons = vals["swidget_show_icons"] !== false;
    const showSpark = vals["swidget_show_sparkline"] !== false;
    const showWash = vals["swidget_show_wash"] !== false;
    const showStars = vals["swidget_show_retention_stars"] !== false;
    const smooth = vals["swidget_chart_shape"] === "smooth";

    ["studied", "time", "pace", "retention"].forEach(function (key) {
      const demo = SW_DEMO[key];
      const card = el("div", "stat-card onigiri-stat-card is-" + design + (design === "expressive" && !showWash ? " no-wash" : "") + " " + key + "-card");
      card.setAttribute("data-stat", key);

      let head = "<h3>" + demo.label + "</h3>";
      if (design === "expressive" && showIcons) {
        const url = iconAssetUrl(vals["swidget_icon_" + key]);
        const glyph = url
          ? '<span class="stat-icon" style="-webkit-mask-image:url(\'' + url + '\');mask-image:url(\'' + url + '\')"></span>'
          : "";
        head = '<div class="stat-head"><span class="stat-icon-chip">' + glyph + "</span>" + head + "</div>";
      }

      const unit = showUnits && demo.unit ? '<span class="stat-unit">' + demo.unit + "</span>" : "";
      let extra = "";
      if (key === "retention" && showStars) extra = swidgetStarsHtml(vals, 4);
      else if (design === "minimal" && showStars) extra = '<div class="star-rating is-placeholder" aria-hidden="true"></div>';

      let spark = "";
      if (design === "expressive" && showSpark) {
        spark = swidgetSparkHtml(demo.series, smooth);
        if (spark) card.classList.add("has-trend");
      }

      card.innerHTML = head +
        '<div class="stat-body"><p class="stat-value">' + demo.value + unit + "</p>" + extra + "</div>" +
        spark;
      const numberInk = fontFieldColor(vals, "swidget_number_font", isDark);
      if (numberInk) card.querySelector(".stat-value").style.color = numberInk;
      const unitInk = fontFieldColor(vals, "swidget_value_font", isDark) ||
        (numberInk ? vars["--swidget-value-color"] : "");
      if (unitInk) card.querySelectorAll(".stat-unit, .stat-sub").forEach(function (node) { node.style.color = unitInk; });
      row.appendChild(card);
    });

    stage.appendChild(row);
  };

  // ── Phase 4: Deck Stats preview ───────────────────────────────────────────
  //
  // Renders the real widget's own markup (learner_stats_widget.py's "grouped"
  // view) inside the settings card, driven by the same --stats-* variables
  // patcher.py emits and the same .learner-stat(s)-* CSS (loaded wholesale —
  // see settings_web/render.py real_widget_css). The preview is that markup,
  // not a redrawing of it, so it cannot drift from what the menu actually
  // renders. Bars/donut views and the deck-picker modal are the real widget's
  // own interactive features, not settings this page edits — only the
  // "grouped" view (the one Chart Type/colours here actually affect) is
  // built.

  // Fixed demo counts, matching the very first prototype's numbers exactly
  // (total 249) so this reads as a real collection, not placeholder zeros.
  const DSTATS_DEMO_COUNTS = {
    new: 42, learning: 8, relearning: 3, young: 61, mature: 128, unseen: 42, suspended: 5, buried: 2
  };
  // total_cnt in the real widget excludes Unseen (it overlaps New) — see the
  // comment on full_categories in learner_stats_widget.py.
  const DSTATS_DEMO_TOTAL = DSTATS_DEMO_COUNTS.new + DSTATS_DEMO_COUNTS.learning + DSTATS_DEMO_COUNTS.relearning +
    DSTATS_DEMO_COUNTS.young + DSTATS_DEMO_COUNTS.mature + DSTATS_DEMO_COUNTS.buried + DSTATS_DEMO_COUNTS.suspended;
  const DSTATS_DEMO_IN_PROGRESS = DSTATS_DEMO_COUNTS.new + DSTATS_DEMO_COUNTS.learning + DSTATS_DEMO_COUNTS.relearning;
  const DSTATS_DEMO_MASTERED = DSTATS_DEMO_COUNTS.young + DSTATS_DEMO_COUNTS.mature;

  const DSTATS_CATEGORY_KEYS = ["new", "learning", "relearning", "young", "mature", "unseen", "suspended", "buried"];
  const DSTATS_LABEL_KEY = {
    new: "lstats_new", learning: "lstats_learning", relearning: "lstats_relearning", young: "lstats_young",
    mature: "lstats_mature", unseen: "lstats_unseen", suspended: "lstats_suspended", buried: "lstats_buried"
  };
  const DSTATS_TONE_FALLBACK = {
    new: "#5eaadf", learning: "#f5a05a", relearning: "#f4685f", young: "#7cc87c", mature: "#26a641",
    unseen: "#b0b4b9", suspended: "#ffdc41", buried: "#9e9e9e", total: "#6f7177"
  };

  function deckStatsEffectValues(vals, isDark) {
    if (vals["dstats_sync_box_effect"]) {
      return {
        blur: vals["onigiri_canvas_inset_effect_blur"], opacity: vals["onigiri_canvas_inset_effect_opacity"],
        radius: vals["onigiri_canvas_inset_border_radius"], stroke: vals["onigiri_canvas_inset_border_width"],
        boxBg: designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark),
        boxBorder: designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      };
    }
    // designerPairValue's "no theme_mode_field" branch defaults to linked
    // (always the light value) — right for fields that share a section-wide
    // Dynamic mode switch, wrong here, where Dynamic mode is Deck Stats' own
    // dstats_dynamic toggle. dstatsColor already reads that correctly (used
    // below for every category tone), so box_bg/box_border reuse it instead
    // of designerPairValue.
    return {
      blur: vals["dstats_blur"], opacity: vals["dstats_opacity"], radius: vals["dstats_radius"], stroke: vals["dstats_stroke"],
      boxBg: dstatsColor(vals, "box_bg", isDark),
      boxBorder: dstatsColor(vals, "box_border", isDark)
    };
  }

  /* Dynamic mode off: a single palette, the light entry standing in for both
     themes — same rule patcher._deck_stats_color applies for the real widget. */
  function dstatsColor(vals, key, isDark) {
    const dynamic = vals["dstats_dynamic"] !== false;
    const useDark = dynamic && isDark;
    const raw = vals["dstats_color_" + key + (useDark ? "_dark" : "_light")];
    return (typeof raw === "string" && raw) ? raw : (DSTATS_TONE_FALLBACK[key] || "#808080");
  }

  function dstatsTile(vals, isDark, labelText, value, tone, flat, wide) {
    const color = tone ? dstatsColor(vals, tone, isDark) : "";
    let cls = "learner-stat-card";
    if (color) cls += " is-toned";
    if (flat) cls += " is-flat";
    if (wide) cls += " is-wide";
    const style = color ? ' style="--stat-tone: ' + color + ';"' : "";
    return '<div class="' + cls + '"' + style + '>' +
      '<span class="learner-stat-label">' + labelText + '</span>' +
      '<span class="learner-stat-val">' + value + '</span></div>';
  }

  const OSW_CHEVRON_ICON = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
  // Same three icons the real widget's switcher uses (learner_stats_widget.py
  // icon_grouped/icon_bars/icon_donut) — reproduced verbatim for pixel parity.
  const DSTATS_ICON_GROUPED = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h16M4 12h16M4 19h16"/></svg>';
  const DSTATS_ICON_BARS = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 5h12M4 12h16M4 19h8" transform="rotate(-90 12 12)"/></svg>';
  const DSTATS_ICON_DONUT = '<svg width="15" height="15" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="none"/><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/></svg>';

  // Full chart mode's bar/ring is 7 mutually exclusive categories — Unseen is
  // deliberately excluded (it overlaps New), matching full_categories in
  // learner_stats_widget.py exactly.
  const DSTATS_FULL_BAR_KEYS = ["new", "learning", "relearning", "young", "mature", "buried", "suspended"];
  const DSTATS_RING_CIRC = Math.round(2 * Math.PI * 15.5 * 100) / 100;

  // Bars/Donut are the real widget's own interactive views (not settings this
  // page edits), so which one is showing is local UI state, not a field value.
  let dstatsActiveView = "grouped";

  function dstatsPctOf(count) {
    if (DSTATS_DEMO_TOTAL <= 0) return 0;
    return Math.min(100, Math.round((count / DSTATS_DEMO_TOTAL) * 10000) / 100);
  }

  function dstatsBarRow(vals, isDark, labelText, value, tone) {
    const pct = dstatsPctOf(value);
    return '<div class="learner-stats-bar-row">' +
      '<span class="learner-stats-bar-label">' + labelText + '</span>' +
      '<span class="learner-stats-bar-track"><span class="learner-stats-bar-fill" style="width: ' + pct +
        '%; --stat-tone: ' + dstatsColor(vals, tone, isDark) + ';"></span></span>' +
      '<span class="learner-stats-bar-value">' + value + '</span></div>';
  }

  // Fixed 6-row list — unlike Grouped/Donut's ring, Bars doesn't branch on
  // Chart Type in the real widget (bar_rows in learner_stats_widget.py).
  function dstatsBuildBarsView(vals, isDark) {
    const spacer = '<div class="learner-stats-bar-spacer"></div>';
    const rows = [
      [str("lstats_new", "New"), DSTATS_DEMO_COUNTS.new, "new"],
      [str("lstats_learning", "Learning"), DSTATS_DEMO_COUNTS.learning, "learning"],
      [str("lstats_relearning", "Relearning"), DSTATS_DEMO_COUNTS.relearning, "relearning"],
      [str("lstats_young", "Young"), DSTATS_DEMO_COUNTS.young, "young"],
      [str("lstats_mature", "Mature"), DSTATS_DEMO_COUNTS.mature, "mature"],
      [str("lstats_unseen", "Unseen"), DSTATS_DEMO_COUNTS.unseen, "unseen"]
    ].map(function (r) { return dstatsBarRow(vals, isDark, r[0], r[1], r[2]); }).join(spacer);
    const footer =
      '<div class="learner-stats-footer-row">' +
        '<span class="learner-stats-footer-item">' + str("lstats_buried", "Buried") + ' <b>' + DSTATS_DEMO_COUNTS.buried + '</b></span>' +
        '<span class="learner-stats-footer-item">' + str("lstats_suspended", "Suspended") + ' <b>' + DSTATS_DEMO_COUNTS.suspended + '</b></span>' +
        '<span class="learner-stats-footer-item is-total">' + str("lstats_total", "Total") + ' <b>' + DSTATS_DEMO_TOTAL + '</b></span>' +
      '</div>';
    return '<div class="learner-stats-view learner-stats-view-bars" data-view="bars">' +
      '<div class="learner-stats-bar-list">' + spacer + rows + '</div>' + footer + '</div>';
  }

  function dstatsBuildDonutView(vals, isDark, isFull) {
    let arcsHtml, legendHtml;
    if (isFull) {
      let consumed = 0;
      const arcs = [];
      const legend = [];
      DSTATS_FULL_BAR_KEYS.forEach(function (key) {
        const color = dstatsColor(vals, key, isDark);
        const pct = dstatsPctOf(DSTATS_DEMO_COUNTS[key]);
        const arc = Math.round(DSTATS_RING_CIRC * pct) / 100;
        arcs.push('<circle class="learner-stats-donut-arc-cat" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="' +
          arc + ' ' + DSTATS_RING_CIRC + '" stroke-dashoffset="' + (-Math.round(consumed * 100) / 100) +
          '" stroke-linecap="butt" style="--stat-tone: ' + color + ';"></circle>');
        consumed += arc;
        legend.push('<span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-cat" style="--stat-tone: ' +
          color + ';"></span>' + str(DSTATS_LABEL_KEY[key], key) + '</span>');
      });
      arcsHtml = arcs.join("");
      legendHtml = legend.join("");
    } else {
      const ipArc = Math.round(DSTATS_RING_CIRC * dstatsPctOf(DSTATS_DEMO_IN_PROGRESS)) / 100;
      const mArc = Math.round(DSTATS_RING_CIRC * dstatsPctOf(DSTATS_DEMO_MASTERED)) / 100;
      arcsHtml =
        '<circle class="learner-stats-donut-arc-inprogress" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="' + ipArc + ' ' + DSTATS_RING_CIRC + '" stroke-dashoffset="0" stroke-linecap="round"></circle>' +
        '<circle class="learner-stats-donut-arc-mastered" cx="18" cy="18" r="15.5" fill="none" stroke-width="4" stroke-dasharray="' + mArc + ' ' + DSTATS_RING_CIRC + '" stroke-dashoffset="' + (-ipArc) + '" stroke-linecap="round"></circle>';
      legendHtml =
        '<span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-inprogress"></span>' + str("lstats_group_in_progress", "In Progress") + '</span>' +
        '<span class="learner-stats-donut-legend-item"><span class="learner-stats-donut-legend-dot is-mastered"></span>' + str("lstats_group_mastered", "Mastered") + '</span>';
    }
    const tiles =
      dstatsTile(vals, isDark, str("lstats_new", "New"), DSTATS_DEMO_COUNTS.new, "new", true, true) +
      dstatsTile(vals, isDark, str("lstats_learning", "Learning"), DSTATS_DEMO_COUNTS.learning, "learning", true, false) +
      dstatsTile(vals, isDark, str("lstats_relearning", "Relearning"), DSTATS_DEMO_COUNTS.relearning, "relearning", true, false) +
      dstatsTile(vals, isDark, str("lstats_young", "Young"), DSTATS_DEMO_COUNTS.young, "young", true, false) +
      dstatsTile(vals, isDark, str("lstats_mature", "Mature"), DSTATS_DEMO_COUNTS.mature, "mature", true, false) +
      dstatsTile(vals, isDark, str("lstats_buried", "Buried"), DSTATS_DEMO_COUNTS.buried, "buried", true, false) +
      dstatsTile(vals, isDark, str("lstats_suspended", "Suspended"), DSTATS_DEMO_COUNTS.suspended, "suspended", true, false);
    const footer =
      '<div class="learner-stats-footer-row">' +
        '<span class="learner-stats-footer-item">' + str("lstats_unseen", "Unseen") + ' <b>' + DSTATS_DEMO_COUNTS.unseen + '</b></span>' +
        '<span class="learner-stats-footer-item is-total">' + str("lstats_total", "Total") + ' <b>' + DSTATS_DEMO_TOTAL + '</b></span>' +
      '</div>';
    return '<div class="learner-stats-view learner-stats-view-donut" data-view="donut">' +
      '<div class="learner-stats-donut-content">' +
        '<div class="learner-stats-donut-top">' +
          '<svg width="52" height="52" viewBox="0 0 36 36" class="learner-stats-donut-ring">' +
            '<circle class="learner-stats-donut-track" cx="18" cy="18" r="15.5" fill="none" stroke-width="4"></circle>' +
            arcsHtml +
          '</svg>' +
          '<div class="learner-stats-donut-total">' +
            '<div class="learner-stats-donut-num">' + DSTATS_DEMO_TOTAL + ' <span>' + str("lstats_total_short", "total") + '</span></div>' +
            '<div class="learner-stats-donut-legend">' + legendHtml + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="learner-stats-tile-grid learner-stats-tile-grid-2">' + tiles + '</div>' +
      '</div>' +
      footer +
    '</div>';
  }

  function dstatsSwitcherHtml() {
    function btn(view, icon) {
      const label = str("lstats_view_" + view, view);
      return '<button type="button" class="osw-preview-dstats-switch-btn learner-stats-switcher-btn" data-view="' + view +
        '" aria-label="' + label + '" title="' + label + '">' + icon + '</button>';
    }
    return '<div class="learner-stats-switcher" role="tablist" aria-label="' + str("lstats_view_switcher", "Stats view") + '">' +
      '<div class="learner-stats-switcher-indicator"></div>' +
      btn("grouped", DSTATS_ICON_GROUPED) + btn("bars", DSTATS_ICON_BARS) + btn("donut", DSTATS_ICON_DONUT) +
    '</div>';
  }

  PREVIEW_PAINTERS.deck_stats = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const isFull = vals["dstats_chart_type"] === "full";
    const eff = deckStatsEffectValues(vals, isDark);
    const opacity = Math.max(0, Math.min(100, Number(eff.opacity)));
    const blurPx = Math.max(0, Number(eff.blur || 0));
    let boxBg = eff.boxBg || (isDark ? "#2c2c2c" : "#ffffff");
    if (!vals["dstats_sync_box_effect"]) {
      let alpha = (isNaN(opacity) ? 100 : opacity) / 100;
      if (blurPx > 0) alpha = Math.min(alpha, 0.62);
      if (alpha < 1) boxBg = rgba(boxBg, alpha);
    }

    const inProgressColor = dstatsColor(vals, "in_progress", isDark);
    const masteredColor = dstatsColor(vals, "mastered", isDark);

    let groupbarSegments;
    if (isFull) {
      groupbarSegments = DSTATS_FULL_BAR_KEYS.map(function (key) {
        const pct = ((DSTATS_DEMO_COUNTS[key] / DSTATS_DEMO_TOTAL) * 100).toFixed(2);
        return '<div class="learner-stats-groupbar-seg learner-stats-groupbar-cat" style="width: ' + pct +
          '%; --stat-tone: ' + dstatsColor(vals, key, isDark) + ';"></div>';
      }).join("");
    } else {
      const ipPct = ((DSTATS_DEMO_IN_PROGRESS / DSTATS_DEMO_TOTAL) * 100).toFixed(2);
      const mPct = ((DSTATS_DEMO_MASTERED / DSTATS_DEMO_TOTAL) * 100).toFixed(2);
      groupbarSegments =
        '<div class="learner-stats-groupbar-seg learner-stats-groupbar-inprogress" style="width: ' + ipPct + '%;"></div>' +
        '<div class="learner-stats-groupbar-seg learner-stats-groupbar-mastered" style="width: ' + mPct + '%;"></div>';
    }
    const groupbarHtml = '<div class="learner-stats-groupbar">' + groupbarSegments + "</div>";

    let groupsHtml;
    if (isFull) {
      const tiles = DSTATS_CATEGORY_KEYS.map(function (key) {
        return dstatsTile(vals, isDark, str(DSTATS_LABEL_KEY[key], key), DSTATS_DEMO_COUNTS[key], key);
      }).join("") + dstatsTile(vals, isDark, str("lstats_total", "Total"), DSTATS_DEMO_TOTAL, "total");
      groupsHtml = '<div class="learner-stats-group"><div class="learner-stats-tile-grid learner-stats-tile-grid-3">' + tiles + "</div></div>";
    } else {
      groupsHtml =
        '<div class="learner-stats-group">' +
          '<div class="learner-stats-group-title is-toned" style="--stat-tone: ' + inProgressColor + ';">' + str("lstats_group_in_progress", "In Progress") + '</div>' +
          '<div class="learner-stats-tile-grid learner-stats-tile-grid-3">' +
            dstatsTile(vals, isDark, str("lstats_new", "New"), DSTATS_DEMO_COUNTS.new, "new") +
            dstatsTile(vals, isDark, str("lstats_learning", "Learning"), DSTATS_DEMO_COUNTS.learning, "learning") +
            dstatsTile(vals, isDark, str("lstats_relearning", "Relearning"), DSTATS_DEMO_COUNTS.relearning, "relearning") +
          "</div></div>" +
        '<div class="learner-stats-group">' +
          '<div class="learner-stats-group-title is-toned" style="--stat-tone: ' + masteredColor + ';">' + str("lstats_group_mastered", "Mastered") + '</div>' +
          '<div class="learner-stats-tile-grid learner-stats-tile-grid-2">' +
            dstatsTile(vals, isDark, str("lstats_young", "Young"), DSTATS_DEMO_COUNTS.young, "young") +
            dstatsTile(vals, isDark, str("lstats_mature", "Mature"), DSTATS_DEMO_COUNTS.mature, "mature") +
          "</div></div>" +
        '<div class="learner-stats-group">' +
          '<div class="learner-stats-group-title is-neutral">' + str("lstats_group_others", "Others") + '</div>' +
          '<div class="learner-stats-tile-grid learner-stats-tile-grid-4">' +
            dstatsTile(vals, isDark, str("lstats_unseen", "Unseen"), DSTATS_DEMO_COUNTS.unseen, "unseen") +
            dstatsTile(vals, isDark, str("lstats_buried", "Buried"), DSTATS_DEMO_COUNTS.buried, "buried") +
            dstatsTile(vals, isDark, str("lstats_suspended", "Suspended"), DSTATS_DEMO_COUNTS.suspended, "suspended") +
            dstatsTile(vals, isDark, str("lstats_total", "Total"), DSTATS_DEMO_TOTAL, "total") +
          "</div></div>";
    }

    const widgetStyle = [
      "--stats-box-bg: " + boxBg, "--stats-box-border: " + (eff.boxBorder || (isDark ? "#424242" : "#e0e0e0")),
      "--stats-box-radius: " + Math.max(0, Number(eff.radius || 0)) + "px",
      "--stats-box-stroke: " + Math.max(0, Number(eff.stroke || 0)) + "px",
      "--stats-box-blur: " + ((blurPx / 100) * 20).toFixed(2) + "px",
      "--stats-in-progress-color: " + inProgressColor, "--stats-mastered-color: " + masteredColor,
      "--onigiri-widget-pad: 14px"
    ].join("; ");

    const grouped_view_html =
      '<div class="learner-stats-view learner-stats-view-grouped" data-view="grouped">' +
        groupbarHtml + '<div class="learner-stats-grouped-groups">' + groupsHtml + "</div>" +
      "</div>";

    const holder = el("div", "osw-preview-stage-center");
    const wrap = el("div", "osw-preview-dstats-wrap");
    if (isDark) wrap.classList.add("night-mode");
    wrap.innerHTML =
      '<div class="learner-stats-widget" data-active-view="' + dstatsActiveView + '" data-chart-type="' + (isFull ? "full" : "minimal") + '" style="' + widgetStyle + '">' +
        '<div class="learner-stats-header"><div class="learner-stats-header-row onigiri-widget-head">' +
          "<h3>" + str("lstats_title", "Stats") + "</h3>" +
          '<div class="learner-stats-header-controls">' + dstatsSwitcherHtml() +
            '<div class="learner-stats-deck-trigger">' +
              '<span class="learner-stats-deck-trigger-label">' + str("lstats_all_decks", "All Decks") + "</span>" +
              '<span class="learner-stats-deck-trigger-chevron">' + OSW_CHEVRON_ICON + "</span>" +
            "</div>" +
          "</div>" +
        "</div></div>" +
        '<div class="learner-stats-body">' +
          grouped_view_html + dstatsBuildBarsView(vals, isDark) + dstatsBuildDonutView(vals, isDark, isFull) +
        "</div>" +
      "</div>";

    // Match the exact label/value split used by patcher.py so the typography
    // menu on this page previews the same elements it changes in Main Menu.
    const labelRole = designerFontRole(vals, "stats_labels", isDark, "main");
    const valueRole = designerFontRole(vals, "stats_values", isDark, "main");
    wrap.querySelectorAll([
      ".learner-stats-deck-trigger", ".learner-stat-label",
      ".learner-stats-compact-total span", ".learner-stats-mini-ring-cap",
      ".learner-stats-mini-row-label", ".learner-stats-group-title",
      ".learner-stats-bar-label", ".learner-stats-footer-item",
      ".learner-stats-donut-num span", ".learner-stats-donut-legend-item"
    ].join(",")).forEach(function (node) {
      node.style.fontFamily = labelRole.family;
      node.style.fontSize = labelRole.size + "px";
      if (labelRole.customColor) node.style.color = labelRole.customColor;
    });
    wrap.querySelectorAll([
      ".learner-stat-val", ".learner-stats-compact-total",
      ".learner-stats-mini-ring-num", ".learner-stats-mini-row-value",
      ".learner-stats-bar-value", ".learner-stats-footer-item b",
      ".learner-stats-donut-num"
    ].join(",")).forEach(function (node) {
      node.style.fontFamily = valueRole.family;
      node.style.fontSize = valueRole.size + "px";
      if (valueRole.customColor) node.style.color = valueRole.customColor;
    });
    wrap.querySelectorAll(".osw-preview-dstats-switch-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        dstatsActiveView = btn.getAttribute("data-view");
        PREVIEW_PAINTERS.deck_stats(stage, vals, isDark);
      });
    });
    holder.appendChild(wrap);
    stage.appendChild(holder);
  };

  // ── Phase 5: Heatmap preview ──────────────────────────────────────────────
  //
  // The illustrative 90-day activity is intentionally synthetic, but it is
  // fed through web/heatmap.js itself. Markup, intensity classification,
  // locale-aware labels, navigation, responsive fitting, tooltips and icon
  // handling therefore cannot drift from the deck-browser widget.

  function hexToHsl(hex) {
    const rgb = hexToRgb(hex || "#007aff");
    const r = rgb[0] / 255, g = rgb[1] / 255, b = rgb[2] / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
    }
    return [h, s, l];
  }

  function hslToHex(h, s, l) {
    h = Math.max(0, Math.min(1, h)); s = Math.max(0, Math.min(1, s)); l = Math.max(0, Math.min(1, l));
    if (s === 0) { const v = Math.round(l * 255); return rgbToHex(v, v, v); }
    function hue(p, q, t) {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    }
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    return rgbToHex(
      Math.round(hue(p, q, h + 1 / 3) * 255),
      Math.round(hue(p, q, h) * 255),
      Math.round(hue(p, q, h - 1 / 3) * 255)
    );
  }

  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map(function (v) { return Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0"); }).join("");
  }

  // Mirrors patcher.py's _mix_colors: ratio is c1's weight.
  function mixColors(c1, c2, ratio) {
    const a = hexToRgb(c1), b = hexToRgb(c2);
    return "rgb(" + [0, 1, 2].map(function (i) { return Math.round(a[i] * ratio + b[i] * (1 - ratio)); }).join(",") + ")";
  }

  // Verbatim port of patcher.py's _generate_heatmap_colors so the preview's
  // 9-step level ramp matches the real widget's CSS vars exactly.
  function heatmapLevelVars(colorFull, colorZero, isNight) {
    const vars = { "--heatmap-level-0": colorZero, "--heatmap-future-0": colorZero };
    const hsl = hexToHsl(colorFull);
    const h = hsl[0], s = hsl[1];
    for (let i = 1; i <= 8; i += 1) {
      const t = i / 8;
      let levelL, levelS;
      if (isNight) { levelL = 0.38 + t * 0.46; levelS = s * Math.max(0.75, 1.0 - t * 0.22); }
      else { levelL = 0.90 - t * 0.53; levelS = s * (0.55 + t * 0.45); }
      vars["--heatmap-level-" + i] = hslToHex(h, levelS, levelL);
      const futureRatio = 0.08 + t * 0.62;
      vars["--heatmap-future-" + i] = isNight
        ? mixColors("#ffffff", colorZero, futureRatio)
        : mixColors("#000000", colorZero, futureRatio);
    }
    return vars;
  }

  // Keep the established example: every day in the last 90 has activity and
  // the current streak reads 12. Counts are chosen to exercise all eight
  // production intensity bands when heatmap.js classifies them.
  const HEATMAP_DEMO_WINDOW_DAYS = 90;
  const HEATMAP_DEMO_STREAK = 12;
  const HEATMAP_DEMO_COUNTS = [1, 2, 4, 6, 8, 10, 12, 13];

  function heatmapDateKey(date) {
    return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" +
      String(date.getDate()).padStart(2, "0");
  }

  function heatmapDemoData() {
    const today = new Date();
    const calendar = {};
    for (let daysAgo = 0; daysAgo < HEATMAP_DEMO_WINDOW_DAYS; daysAgo += 1) {
      const date = new Date(today);
      date.setDate(today.getDate() - daysAgo);
      calendar[heatmapDateKey(date)] = HEATMAP_DEMO_COUNTS[daysAgo % HEATMAP_DEMO_COUNTS.length];
    }
    return {
      calendar: calendar,
      due_calendar: {},
      today_date_key: heatmapDateKey(today),
      daily_average: 5,
      streak: HEATMAP_DEMO_STREAK,
      longest_streak: HEATMAP_DEMO_STREAK,
      firstYear: today.getFullYear()
    };
  }
  const HEATMAP_PREVIEW_DATA = heatmapDemoData();

  // heatmap.py's own shape_file_path() accepts a bare "square.svg" too (it
  // falls back to the system dir when there's no "system:" prefix); the icon
  // asset map only keys system icons as "system:square.svg", so a raw lookup
  // alone would miss the field's own default. Mirror that same leniency here.
  function heatmapShapeMaskUrl(vals) {
    const raw = String(vals["heatmapShape"] || "");
    if (raw.indexOf("emoji:") === 0) {
      const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text x="16" y="24" text-anchor="middle" font-size="24">' +
        raw.slice(6) + "</text></svg>";
      return "data:image/svg+xml," + encodeURIComponent(svg);
    }
    return resolveIconAssetUrl(raw) || iconAssetUrl("system:square.svg");
  }

  function heatmapSvgFromAsset(value, fallbackValue, allowEmoji) {
    let raw = String(value || "");
    if (raw.indexOf("emoji:") === 0) {
      if (allowEmoji) {
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text x="16" y="24" text-anchor="middle" font-size="24">' +
          raw.slice(6) + "</text></svg>";
      }
      raw = fallbackValue;
    }
    const url = resolveIconAssetUrl(raw) || resolveIconAssetUrl(fallbackValue);
    if (!url) return "";
    if (/^data:image\/svg\+xml;base64,/i.test(url)) {
      try {
        const binary = atob(url.slice(url.indexOf(",") + 1));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
        return new TextDecoder("utf-8").decode(bytes);
      } catch (_) { return ""; }
    }
    if (/^data:image\/svg\+xml,/i.test(url)) {
      try { return decodeURIComponent(url.slice(url.indexOf(",") + 1)); }
      catch (_) { return ""; }
    }
    const safeUrl = url.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><image href="' + safeUrl +
      '" width="32" height="32" preserveAspectRatio="xMidYMid meet"/></svg>';
  }

  function heatmapPreviewConfig(vals) {
    return {
      heatmapShapeMaskUrl: heatmapShapeMaskUrl(vals),
      heatmapStreakIconSvgContent: heatmapSvgFromAsset(
        vals["heatmapStreakIcon"] || "system:fire.svg", "system:fire.svg", false
      ),
      heatmapStreakIconColor: vals["heatmapStreakIconColor"] || "#ff6b35",
      heatmapStreakIconZeroColor: vals["heatmapStreakIconZeroColor"] || "#8f8f8f",
      heatmapShowStreak: vals["heatmapShowStreak"] !== false,
      heatmapShowMonths: vals["heatmapShowMonths"] !== false,
      heatmapShowWeekdays: vals["heatmapShowWeekdays"] !== false,
      heatmapShowWeekHeader: vals["heatmapShowWeekHeader"] !== false,
      heatmapParticlesAnimation: vals["heatmapParticlesAnimation"] === true,
      heatmapDefaultView: vals["heatmapDefaultView"] || "year",
      heatmapWeekStart: vals["heatmapWeekStart"] || "monday",
      locale: CTX.heatmapLocale || undefined,
      i18n: {
        activity: str("heatmap_activity_label", "Activity"),
        year: str("view_year", "Year"),
        month: str("view_month", "Month"),
        week: str("view_week", "Week"),
        day_streak: str("heatmap_day_streak", "day streak"),
        browse: str("browse", "Browse")
      }
    };
  }

  function sizeHeatmapPreview(wrap, vals) {
    const layout = vals["onigiriWidgetLayout"] || {};
    const placed = (layout.grid || {}).heatmap || {};
    const columnWidth = Math.max(200, Math.min(340, Number(layout.grid_width) || 250));
    const rowHeight = Math.max(120, Math.min(320, Number(layout.widget_height) || 150));
    const columnSpan = Math.max(2, Math.min(4, Number(placed.col) || 4));
    const rowSpan = 2;
    const gridGap = 15;
    wrap.style.maxWidth = (columnWidth * columnSpan + gridGap * (columnSpan - 1)) + "px";
    wrap.style.height = (rowHeight * rowSpan + gridGap * (rowSpan - 1)) + "px";
  }

  // Python modules stay resident until Anki restarts, while web/settings.* is
  // read fresh whenever this dialog opens. During add-on development that can
  // produce a mixed generation: new settings.js calls the shared renderer,
  // but the old in-memory render.py did not yet inline heatmap.js. Load the
  // same production asset client-side in that case so the preview never turns
  // into an empty box and a Python restart is not required for web-only edits.
  let heatmapRendererPromise = null;
  function ensureHeatmapRenderer() {
    if (window.OnigiriHeatmap && typeof window.OnigiriHeatmap.render === "function") {
      return Promise.resolve();
    }
    if (heatmapRendererPromise) return heatmapRendererPromise;
    heatmapRendererPromise = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = (CTX.addonBase || "") + "web/heatmap.js?settings-preview=1";
      script.onload = function () {
        if (window.OnigiriHeatmap && typeof window.OnigiriHeatmap.render === "function") resolve();
        else reject(new Error("Heatmap renderer did not initialize"));
      };
      script.onerror = function () { reject(new Error("Heatmap renderer could not be loaded")); };
      document.head.appendChild(script);
    });
    return heatmapRendererPromise;
  }

  // Sync on (default): follows Widget Color and Effect, same as legacy. Off:
  // the card's own heatmap_blur/opacity/radius/stroke/box colours — same
  // shape as deckStatsEffectValues.
  function heatmapEffectValues(vals, isDark) {
    if (vals["heatmap_sync_box_effect"] !== false) {
      return {
        blur: vals["onigiri_canvas_inset_effect_blur"], opacity: vals["onigiri_canvas_inset_effect_opacity"],
        radius: vals["onigiri_canvas_inset_border_radius"], stroke: vals["onigiri_canvas_inset_border_width"],
        boxBg: designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark),
        boxBorder: designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      };
    }
    return {
      blur: vals["heatmap_blur"], opacity: vals["heatmap_opacity"], radius: vals["heatmap_radius"], stroke: vals["heatmap_stroke"],
      boxBg: designerPairValue(vals, "heatmap_color_box_bg_light", "heatmap_color_box_bg_dark", null, isDark),
      boxBorder: designerPairValue(vals, "heatmap_color_box_border_light", "heatmap_color_box_border_dark", null, isDark)
    };
  }

  // The production heatmap inherits these tokens from Anki's active Onigiri
  // palette. The settings dialog has a separate chrome palette, so publish
  // the saved theme values explicitly instead of approximating them with
  // preview-only colours. This keeps header-right (streak, navigation, and
  // view controls) visually identical to the live widget.
  function heatmapThemeVars(vals, isDark) {
    const suffix = isDark ? "_dark" : "_light";
    return {
      fg: vals["theme_fg" + suffix] || (isDark ? "#e0e0e0" : "#212121"),
      fgSubtle: vals["theme_subtle" + suffix] || (isDark ? "#9e9e9e" : "#757575"),
      highlightBg: vals["sb_highlight_bg" + suffix] || (isDark ? "#3c3c3c" : "#eeeeee"),
      border: vals["theme_border" + suffix] || (isDark ? "#424242" : "#e0e0e0"),
      accent: vals["theme_accent" + suffix] || CTX.accent || "#0077C8"
    };
  }

  // Every value that can change without touching the DOM's *shape* (view,
  // week start, which optional rows exist, the theme toggle) — repainting
  // these just updates CSS custom properties on the existing container
  // instead of tearing down and rebuilding the ~370-cell year grid, which is
  // what made toggling Dynamic Mode (a colour-only change) visibly lag.
  function heatmapPaintCosmetics(container, vals, isDark) {
    const eff = heatmapEffectValues(vals, isDark);
    const themeVars = heatmapThemeVars(vals, isDark);
    const opacity = Math.max(0, Math.min(100, Number(eff.opacity)));
    const blurPx = Math.max(0, Number(eff.blur || 0));
    const boxBg = rgba(eff.boxBg || "#ffffff", Math.min((isNaN(opacity) ? 100 : opacity) / 100, blurPx > 0 ? 0.62 : 1));
    const backdrop = blurPx > 0 ? "blur(" + ((blurPx / 100) * 20).toFixed(1) + "px)" : "none";
    container.style.background = boxBg;
    container.style.borderRadius = Math.max(0, Number(eff.radius || 0)) + "px";
    container.style.clipPath = "inset(0 round " + container.style.borderRadius + ")";
    container.style.border = Math.max(0, Number(eff.stroke || 0)) + "px solid " + (eff.boxBorder || "rgba(0,0,0,0.12)");
    container.style.backdropFilter = backdrop;
    container.style.webkitBackdropFilter = backdrop;
    // heatmap.css uses the same menu-theme variables for the year dropdown,
    // active accents and tooltips. Publish them on the preview container so
    // nested UI is identical too, including after a live colour edit.
    container.style.setProperty("--fg", themeVars.fg);
    container.style.setProperty("--fg-subtle", themeVars.fgSubtle);
    container.style.setProperty("--heatmap-title-color",
      vals["heatmap_sync_box_effect"] !== false
        ? swidgetColor(vals, "label", isDark, "#757575", "#9c9c9c")
        : themeVars.fg);
    container.style.setProperty("--highlight-bg", themeVars.highlightBg);
    container.style.setProperty("--border", themeVars.border);
    container.style.setProperty("--canvas-inset", eff.boxBg || (isDark ? "#2c2c2c" : "#ffffff"));
    container.style.setProperty("--accent-color", themeVars.accent);
    container.style.setProperty("--onigiri-tooltip-bg",
      mixColors(isDark ? "#000000" : "#ffffff", eff.boxBg || (isDark ? "#2c2c2c" : "#ffffff"), 0.20));
    container.style.setProperty("--onigiri-tooltip-fg", themeVars.fg);
    container.style.setProperty("--onigiri-tooltip-border", themeVars.border);

    // Dynamic Mode off: the light entry stands in for both themes, same rule
    // patcher.py's _generate_heatmap_colors applies for the real widget.
    const heatmapColorDark = (vals["heatmap_dynamic"] !== false) && isDark;
    const heatmapColorMode = heatmapColorDark ? "dark" : "light";
    // Level zero follows the same source mode as the active-color ramp, so a
    // separate dark-mode empty-cell color is reflected in this preview.
    const colorZero = vals["heatmap_color_zero_" + heatmapColorMode]
      || (isDark ? "#2A2A2A" : "#E6E6E6");
    const colorFull = vals["heatmap_color_" + heatmapColorMode] || "#0077C8";
    const levelVars = heatmapLevelVars(colorFull, colorZero, isDark);
    Object.keys(levelVars).forEach(function (k) { container.style.setProperty(k, levelVars[k]); });

    const shapeMask = heatmapShapeMaskUrl(vals);
    if (shapeMask) {
      const safeMask = String(shapeMask).replace(/"/g, "%22");
      container.style.setProperty("--heatmap-shape-mask", 'url("' + safeMask + '")');
    }

    const hasStreak = HEATMAP_DEMO_STREAK > 0;
    const streakColor = hasStreak ? (vals["heatmapStreakIconColor"] || "#ff6b35") : (vals["heatmapStreakIconZeroColor"] || "#8f8f8f");
    const streakIcon = container.querySelector(".streak-icon");
    if (streakIcon) streakIcon.setAttribute("style", "color:" + streakColor + ";fill:currentColor;");

    // Heatmap's compact Fonts menu has a title role and a role for the
    // calendar controls. Apply them inline so the preview matches the live
    // widget's explicitly-sized labels.
    const componentRole = function (roleKey, fallbackRoleKey, fallbackSize) {
      const role = designerFontRole(vals, roleKey, isDark, fallbackRoleKey, true);
      const sizeRoleKey = roleKey;
      role.size = Math.max(
        8,
        Math.min(
          72,
          Number(vals["onigiri_font_size_" + sizeRoleKey]) || fallbackSize
        )
      );
      return role;
    };
    const applyRole = function (selector, role) {
      container.querySelectorAll(selector).forEach(function (node) {
        node.style.setProperty("font-family", role.family, "important");
        node.style.setProperty("font-size", role.size + "px", "important");
        if (role.customColor) node.style.setProperty("color", role.customColor, "important");
      });
    };
    const titleRole = componentRole("heatmap_title", "small_title", 15);
    const labelsRole = componentRole("heatmap_labels", "main", 14);
    applyRole(".heatmap-title", titleRole);
    applyRole([
      ".streak-counter", ".heatmap-nav .nav-title",
      ".heatmap-nav .year-select-btn", ".year-dropdown-item",
      ".heatmap-filters .filter-btn", ".heatmap-months", ".heatmap-months .month-label",
      ".heatmap-weekdays", ".heatmap-weekdays .weekday-label",
      ".month-weekdays-header", ".month-weekdays-header .weekday-label",
      ".week-days-header", ".week-days-header .weekday-label", ".week-days-header .day-label"
    ].join(", "), labelsRole);
  }

  PREVIEW_PAINTERS.heatmap = function (stage, vals, isDark) {
    if (!window.OnigiriHeatmap || typeof window.OnigiriHeatmap.render !== "function") {
      stage.innerHTML = "";
      const loading = el("div", "osw-preview-stage-center");
      loading.appendChild(el("div", "osw-preview-heatmap-loading", str("loading", "Loading…")));
      stage.appendChild(loading);
      ensureHeatmapRenderer().then(function () {
        if (stage.isConnected) PREVIEW_PAINTERS.heatmap(stage, vals, isDark);
      }).catch(function (error) {
        if (!stage.isConnected) return;
        loading.innerHTML = "";
        loading.appendChild(el("div", "osw-preview-heatmap-loading is-error", error.message));
      });
      return;
    }
    const previewConfig = heatmapPreviewConfig(vals);
    const structKey = [
      previewConfig.heatmapDefaultView, previewConfig.heatmapWeekStart,
      previewConfig.heatmapShowMonths, previewConfig.heatmapShowWeekdays,
      previewConfig.heatmapShowWeekHeader, previewConfig.heatmapShowStreak,
      previewConfig.heatmapParticlesAnimation,
      vals["heatmapStreakIcon"] || "system:fire.svg", isDark
    ].join("|");

    if (stage.__heatmapContainer && stage.__heatmapStructKey === structKey) {
      heatmapPaintCosmetics(stage.__heatmapContainer, vals, isDark);
      if (stage.__heatmapContainer.__particles) stage.__heatmapContainer.__particles.refresh();
      return;
    }
    stage.__heatmapStructKey = structKey;
    if (stage.__heatmapContainer && stage.__heatmapContainer.__particles) {
      stage.__heatmapContainer.__particles.destroy();
    }

    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const holder = el("div", "osw-preview-stage-center");
    const wrap = el("div", "osw-preview-heatmap-wrap");
    sizeHeatmapPreview(wrap, vals);
    wrap.classList.add(isDark ? "night-mode" : "light-mode");

    const container = document.createElement("div");
    container.id = "onigiri-heatmap-container";
    wrap.appendChild(container);
    holder.appendChild(wrap);
    stage.appendChild(holder);
    stage.__heatmapContainer = container;

    // renderDesignerPreview builds this card before its caller mounts it.
    // Pass the node itself so the production renderer can populate it now;
    // its requestAnimationFrame reflow measures the final mounted box.
    window.OnigiriHeatmap.render(
      container, HEATMAP_PREVIEW_DATA, previewConfig
    );
    heatmapPaintCosmetics(container, vals, isDark);
  };

  // ── Overview Style preview ─────────────────────────────────────────────────
  //
  // The Overviewer/Congrats card (settings/_page_overviews.py:587-1525): box,
  // Study Now button and the three card-count colours, floated on the same
  // backdrop as the Overviewer Background section's own preview (OVERVIEW_BG_KEYS)
  // so the two sections agree on what the box sits over. Title/count labels are
  // hardcoded demo text, matching the legacy Qt preview's own hardcoded sample
  // strings (_draw_overview_style_sample never runs them through tr()).

  const OVSTYLE_TONE_FALLBACK = {
    box_bg: "#f3f3f3", box_border: "#e0e0e0", study_button: "#0077C8",
    new_bubble: "#1e8cff", new_text: "#ffffff", learn_bubble: "#19c96b", learn_text: "#ffffff",
    review_bubble: "#ff5757", review_text: "#ffffff"
  };

  /* Overview Style keeps its own light/dark colours always split (legacy's
     "dynamic" flag is hardcoded True with no user-facing toggle) — unlike
     dstatsColor there is no "dynamic mode off" branch reading only the light
     value for both themes. */
  function ovstyleColor(vals, key, isDark) {
    const raw = vals["ovstyle_color_" + key + (isDark ? "_dark" : "_light")];
    return (typeof raw === "string" && raw) ? raw : (OVSTYLE_TONE_FALLBACK[key] || "#808080");
  }

  function ovstyleActionButtonColor(vals, key, isDark) {
    const raw = vals["ovstyle_color_" + key + (isDark ? "_dark" : "_light")];
    if (typeof raw === "string" && raw) return raw;
    return isDark ? "#2a2a2a" : "#f5f5f5";
  }

  /* Mirrors deckStatsEffectValues: Sync with Widget Color and Effect takes its
     blur/opacity/radius/stroke/box colours from the Widget Color and Effect
     section instead of this card's own sliders. */
  function ovstyleEffectValues(vals, isDark) {
    if (vals["ovstyle_sync_box_effect"]) {
      return {
        blur: vals["onigiri_canvas_inset_effect_blur"], opacity: vals["onigiri_canvas_inset_effect_opacity"],
        radius: vals["onigiri_canvas_inset_border_radius"], stroke: vals["onigiri_canvas_inset_border_width"],
        boxBg: designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark),
        boxBorder: designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark", "onigiri_canvas_inset_color_theme_mode", isDark)
      };
    }
    return {
      blur: vals["ovstyle_blur"], opacity: vals["ovstyle_opacity"], radius: vals["ovstyle_radius"], stroke: vals["ovstyle_stroke"],
      boxBg: ovstyleColor(vals, "box_bg", isDark),
      boxBorder: ovstyleColor(vals, "box_border", isDark)
    };
  }

  function ovstyleBubbleRow(labelText, count, bg, fg) {
    return '<div class="osw-preview-ovstyle-row">' +
      '<span class="osw-preview-ovstyle-row-label">' + labelText + '</span>' +
      '<span class="osw-preview-ovstyle-bubble" style="background:' + bg + ';color:' + fg + ';">' + count + '</span>' +
    '</div>';
  }

  function ovstyleNumber(value, fallback, minimum, maximum) {
    const number = Number(value);
    if (!isFinite(number)) return fallback;
    return Math.max(minimum, Math.min(maximum, number));
  }

  function ovstyleFontStack(fieldId, fallback) {
    const field = fieldById[fieldId] || {};
    const selected = values[fieldId];
    const option = (field.options || []).find(function (item) { return item.value === selected; });
    return (option && option.family) || fallback;
  }

  // Like the legacy preview's Overviewer/Congrats pair, this is deliberately
  // local preview state.  It must not create a config value just to choose
  // which of the two real screens is being inspected.
  let ovstyleActiveScreen = "overviewer";

  /* The designer is much narrower than Anki's overview webview.  Draw the
     sample on a fixed, overview-sized canvas and scale that canvas to the
     available preview width.  This preserves both the 280px/350px Mini/Pro
     size difference and the large vertical-placement difference that would
     otherwise disappear in a short preview stage. */
  const OVSTYLE_PREVIEW_VIEWPORT = { width: 1720, height: 1104 };

  function layoutOvstylePreviewViewport(stage, canvas) {
    function fit() {
      const availableWidth = stage.clientWidth || OVSTYLE_PREVIEW_VIEWPORT.width;
      const scale = Math.min(1, Math.max(0.25, availableWidth / OVSTYLE_PREVIEW_VIEWPORT.width));
      const previewHeight = Math.round(OVSTYLE_PREVIEW_VIEWPORT.height * scale);
      stage.style.height = previewHeight + "px";
      stage.style.minHeight = previewHeight + "px";
      canvas.style.setProperty("--ovstyle-preview-scale", scale.toFixed(4));
    }

    if (stage.__ovstylePreviewResizeObserver) stage.__ovstylePreviewResizeObserver.disconnect();
    if (typeof ResizeObserver !== "undefined") {
      stage.__ovstylePreviewResizeObserver = new ResizeObserver(fit);
      stage.__ovstylePreviewResizeObserver.observe(stage);
    }
    fit();
  }

  function ovstyleScreenSwitcher(stage, vals, isDark) {
    const switcher = el("div", "osw-preview-ovstyle-screen-switcher");
    [["overviewer", "Overview"], ["congrats", "Congrats"]].forEach(function (spec) {
      const btn = el("button", "osw-preview-ovstyle-screen-btn" + (ovstyleActiveScreen === spec[0] ? " is-active" : ""), spec[1]);
      btn.type = "button";
      btn.addEventListener("click", function () {
        ovstyleActiveScreen = spec[0];
        PREVIEW_PAINTERS.overview_style(stage, vals, isDark);
      });
      switcher.appendChild(btn);
    });
    return switcher;
  }

  PREVIEW_PAINTERS.overview_style = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark, OVERVIEW_BG_KEYS);

    const isMini = vals["ovstyle_design"] === "mini";
    const eff = ovstyleEffectValues(vals, isDark);
    const opacity = ovstyleNumber(eff.opacity, 100, 0, 100);
    const blurPx = ovstyleNumber(eff.blur, 0, 0, 100);
    let boxBg = eff.boxBg || (isDark ? "#2c2c2c" : "#f3f3f3");
    let alpha = (isNaN(opacity) ? 100 : opacity) / 100;
    if (blurPx > 0) alpha = Math.min(alpha, 0.82);
    if (alpha < 1) boxBg = rgba(boxBg, alpha);
    const boxBorder = eff.boxBorder || (isDark ? "#565656" : "#e0e0e0");
    const boxRadius = ovstyleNumber(eff.radius, 20, 0, 60);
    const boxStroke = ovstyleNumber(eff.stroke, 1, 0, 10);

    const studyBtnColorRaw = ovstyleColor(vals, "study_button", isDark);
    const studyBtnOpacityPct = ovstyleNumber(vals["ovstyle_study_button_opacity"], 100, 0, 100);
    const studyBtnColor = studyBtnOpacityPct < 100 ? rgba(studyBtnColorRaw, studyBtnOpacityPct / 100) : studyBtnColorRaw;
    const studyBtnRadiusPct = ovstyleNumber(vals["ovstyle_study_button_radius"], 100, 0, 100);
    const studyBtnStroke = ovstyleNumber(vals["ovstyle_study_button_stroke"], 0, 0, 10);
    const customStudyBtnStrokeColor = vals["ovstyle_color_study_button_stroke" + (isDark ? "_dark" : "_light")];
    const studyBtnStrokeColor = studyBtnStroke > 0 && typeof customStudyBtnStrokeColor === "string" && customStudyBtnStrokeColor
      ? customStudyBtnStrokeColor
      : boxBorder;
    const studyBtnDashed = !!vals["ovstyle_study_button_dashed"];
    const studyBtnAnimated = vals["ovstyle_study_button_animated"] !== false;
    const studyBtnBlurPx = vals["ovstyle_sync_box_effect"] && blurPx > 0 ? (blurPx / 100) * 20 : 0;
    const studyBtnHoverShadow = studyBtnAnimated ? "0 6px 18px rgba(0, 0, 0, 0.22)" : "none";
    const optionsButtonColor = ovstyleActionButtonColor(vals, "options_button", isDark);
    const customStudyButtonColor = ovstyleActionButtonColor(vals, "custom_study_button", isDark);
    const descriptionButtonColor = ovstyleActionButtonColor(vals, "description_button", isDark);

    const textColor = designerPairValue(vals, "font_color_light_main", "font_color_dark_main", "font_color_main_theme_mode", isDark) ||
      (isDark ? "#f4f4f5" : "#202124");
    const mainFontSize = ovstyleNumber(vals["onigiri_font_size_main"], 14, 8, 72);
    const mainFont = ovstyleFontStack(
      "onigiri_font_main",
      "'Poppins', -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    );
    const subtleFont = ovstyleFontStack("onigiri_font_subtle", mainFont);
    const profileType = vals["modern_menu_profile_type"] || "bar";
    const showProfileBar = vals["show_overview_profile_bar"] !== false && profileType === "bar";
    const showCongratsProfileBar = vals["show_congrats_profile_bar"] !== false && profileType === "bar";
    const studyText = (vals["overview_study_now_text"] || "").trim() || "Study Now";

    const wrapStyle = [
      "--ovstyle-box-bg: " + boxBg, "--ovstyle-box-border: " + boxBorder,
      "--ovstyle-box-radius: " + boxRadius + "px", "--ovstyle-box-stroke: " + boxStroke + "px",
      "--ovstyle-box-blur: " + ((blurPx / 100) * 20).toFixed(2) + "px",
      "--ovstyle-study-btn-bg: " + studyBtnColor,
      "--ovstyle-study-btn-radius: " + (studyBtnRadiusPct >= 100 ? "999px" : ((studyBtnRadiusPct / 100) * 24).toFixed(1) + "px"),
      "--ovstyle-study-btn-stroke: " + studyBtnStroke + "px",
      "--ovstyle-study-btn-stroke-style: " + (studyBtnDashed ? "dashed" : "solid"),
      "--ovstyle-study-btn-stroke-color: " + studyBtnStrokeColor,
      "--ovstyle-study-btn-lift: " + (studyBtnAnimated ? "-2px" : "0px"),
      "--ovstyle-study-btn-hover-shadow: " + studyBtnHoverShadow,
      "--ovstyle-study-btn-blur: " + studyBtnBlurPx.toFixed(2) + "px",
      "--ovstyle-options-btn-bg: " + optionsButtonColor,
      "--ovstyle-options-btn-fg: " + readableTextColor(optionsButtonColor),
      "--ovstyle-custom-study-btn-bg: " + customStudyButtonColor,
      "--ovstyle-custom-study-btn-fg: " + readableTextColor(customStudyButtonColor),
      "--ovstyle-description-btn-bg: " + descriptionButtonColor,
      "--ovstyle-description-btn-fg: " + readableTextColor(descriptionButtonColor),
      "--ovstyle-text: " + textColor,
      "--ovstyle-main-size: " + mainFontSize + "px",
      "--ovstyle-font-main: " + mainFont,
      "--ovstyle-font-subtle: " + subtleFont,
      "--ovstyle-profile-bg: " + rgba(boxBorder, isDark ? .58 : .48),
      "--ovstyle-profile-fg: " + textColor
    ].join("; ");

    const canvas = el("div", "osw-preview-ovstyle-canvas");
    const holder = el("div", "osw-preview-stage-center " + (isMini ? "is-mini" : "is-pro"));
    const wrap = el("div", "osw-preview-ovstyle-wrap " + (isMini ? "is-mini" : "is-pro"));
    wrap.setAttribute("style", wrapStyle);
    const profileBar =
      '<div class="osw-preview-ovstyle-profilebar"><span class="osw-preview-ovstyle-profile-avatar"></span>' +
      '<span class="osw-preview-ovstyle-profile-name">' + str("profile", "Profile") + '</span><span class="osw-preview-ovstyle-profile-streak">' + str("preview_day_streak", "12 day streak") + '</span></div>';
    if (ovstyleActiveScreen === "congrats") {
      const message = (vals["overview_congrats_message"] || "").trim() ||
        str("congrats_message", "Congratulations! You have finished this deck for now.");
      wrap.classList.add("osw-preview-ovstyle-congrats");
      wrap.innerHTML =
        (showCongratsProfileBar ? profileBar : "") +
        '<div class="osw-preview-ovstyle-box"><h3 class="osw-preview-ovstyle-congrats-title">' + str("congratulations", "Congratulations!") + '</h3>' +
        '<p class="osw-preview-ovstyle-congrats-message">' + message + "</p></div>";
    } else {
      const learningNotice = vals["show_overview_due_later_notice"] !== false
        ? '<div class="osw-preview-ovstyle-learning-notice">' +
            '<p>' + str("preview_next_learning_card", "The next learning card will be ready in 15 minutes.") + '</p>' +
            '<p>' + str("preview_due_later_today", "3 learning cards are due later today.") + '</p>' +
            '<button type="button" tabindex="-1" data-preview-inert="true">' + str("one_learning_card_ready_now", "One learning card is ready now.") + '</button>' +
          '</div>'
        : "";
      wrap.innerHTML =
        '<div class="osw-preview-ovstyle-title">' + str("title", "Title") + '</div>' +
        (showProfileBar ? profileBar : "") +
        '<div class="osw-preview-ovstyle-box">' +
          ovstyleBubbleRow(str("lstats_new", "New"), "123", ovstyleColor(vals, "new_bubble", isDark), ovstyleColor(vals, "new_text", isDark)) +
          '<div class="osw-preview-ovstyle-divider"></div>' +
          ovstyleBubbleRow(str("learning", "Learning"), "321", ovstyleColor(vals, "learn_bubble", isDark), ovstyleColor(vals, "learn_text", isDark)) +
          '<div class="osw-preview-ovstyle-divider"></div>' +
          ovstyleBubbleRow(str("to_review", "To Review"), "321", ovstyleColor(vals, "review_bubble", isDark), ovstyleColor(vals, "review_text", isDark)) +
          learningNotice +
        "</div>" +
        '<button type="button" tabindex="-1" data-preview-inert="true" class="osw-preview-ovstyle-button' + (studyBtnAnimated ? " is-animated" : "") + '">' + studyText + "</button>" +
        '<div class="osw-preview-ovstyle-actions-stack">' +
          '<div class="osw-preview-ovstyle-actions">' +
            '<button type="button" tabindex="-1" data-preview-inert="true" class="osw-preview-ovstyle-action-button is-options">' + str("options", "Options") + "</button>" +
            '<button type="button" tabindex="-1" data-preview-inert="true" class="osw-preview-ovstyle-action-button is-custom-study">' + str("custom_study", "Custom Study") + "</button>" +
            '<button type="button" tabindex="-1" data-preview-inert="true" class="osw-preview-ovstyle-action-button is-description">' + str("description", "Description") + "</button>" +
          "</div>" +
          '<div class="osw-preview-ovstyle-actions osw-preview-ovstyle-reveal-action">' +
            '<button type="button" tabindex="-1" data-preview-inert="true" class="osw-preview-ovstyle-action-button is-options osw-preview-ovstyle-reveal-button">' + str("click_to_reveal", "Click to reveal") + "</button>" +
          "</div>" +
        "</div>";
    }

    [
      ["overview_title", ".osw-preview-ovstyle-title"],
      ["overview_text", ".osw-preview-ovstyle-button, .osw-preview-ovstyle-action-button, .osw-preview-ovstyle-learning-notice"],
      ["congrats_title", ".osw-preview-ovstyle-congrats-title, .osw-preview-ovstyle-congrats-message"],
      ["congrats_text", ".osw-preview-ovstyle-congrats .osw-preview-ovstyle-action-button"]
    ].forEach(function (entry) {
      const ink = fontFieldColor(vals, "onigiri_font_" + entry[0], isDark);
      if (ink) wrap.querySelectorAll(entry[1]).forEach(function (node) { node.style.color = ink; });
    });
    holder.appendChild(wrap);
    canvas.appendChild(holder);
    stage.appendChild(canvas);
    layoutOvstylePreviewViewport(stage, canvas);
  };

  // ── Reviewer Bottom Bar preview ────────────────────────────────────────────
  //
  // Every Match mode inherits its complete source, including chained matches.

  /* Resolves one of the five background sources into {color, imageName,
     imageFolder, blur, opacity} — the shared shape paintResolvedBackdropState
     paints, whether the source is this section's own fields or another
     section's (Main menu / Overviewer / Reviewer Background all live in the
     same global `values`, so no field duplication is needed to read them). */
  function designerBgSourceState(vals, isDark, keys) {
    const mode = vals[keys.mode] || "image_color";
    if (mode === "main" && keys !== MAIN_BG_KEYS) {
      return designerBgSourceState(vals, isDark, MAIN_BG_KEYS);
    }
    const color = designerPairValue(vals, keys.colorLight, keys.colorDark, keys.colorThemeMode, isDark) ||
      (isDark ? "#2c2c2c" : "#f2f2f2");
    let imageName = "";
    if (mode === "slideshow") {
      const list = Array.isArray(vals[keys.slideshowImages]) ? vals[keys.slideshowImages] : [];
      imageName = list[0] || "";
    } else if (mode !== "color") {
      imageName = designerPairValue(
        vals, keys.imageLight, keys.imageDark, keys.imageThemeMode, isDark, keys.imageBase
      );
    }
    return {
      color: color,
      imageName: imageName,
      imageFolder: keys.imageFolder,
      blur: Number(vals[keys.blur] || 0),
      opacity: Number(vals[keys.opacity]),
    };
  }

  function bbarBackgroundState(vals, isDark) {
    const mode = vals["bbar_bg_mode"] || "match_reviewer_bg";
    if (mode === "main") {
      return designerBgSourceState(vals, isDark, MAIN_BG_KEYS);
    }
    if (mode === "match_overview_bg") {
      return designerBgSourceState(vals, isDark, OVERVIEW_BG_KEYS);
    }
    if (mode === "match_reviewer_bg") {
      return designerBgSourceState(vals, isDark, REVIEWER_BG_KEYS);
    }
    // "color" / "image_color": this section's own single-image source (no
    // light/dark image split — onigiri_reviewer_bottom_bar_bg_image is one key).
    return {
      color: designerPairValue(vals, "bbar_bg_color_light", "bbar_bg_color_dark", "bbar_bg_color_theme_mode", isDark) ||
        (isDark ? "#2C2C2C" : "#f2f2f2"),
      imageName: mode === "image_color" ? (vals["bbar_bg_image"] || "") : "",
      imageFolder: "reviewer_bar_bg",
      blur: Number(vals["bbar_bg_blur"] || 0),
      opacity: Number(vals["bbar_bg_opacity"]),
    };
  }

  /* Same colour/image-layer treatment as designerPaintBackdrop, but from an
     already-resolved state object instead of a live `keys` mapping — bbar's
     background source also supports a local single-image selection. */
  function paintResolvedBackdropState(stage, state) {
    const colorLayer = el("div", "osw-bg-preview-layer");
    colorLayer.style.position = "absolute";
    colorLayer.style.inset = "0";
    colorLayer.style.background = state.color || "#eeeeee";
    stage.appendChild(colorLayer);
    if (!state.imageName) return;
    const url = imageUrl(state.imageFolder, state.imageName);
    if (!url) return;
    const blur = Math.max(0, Number(state.blur || 0));
    let opacity = Number(state.opacity);
    if (isNaN(opacity)) opacity = 100;
    const imgLayer = el("div", "osw-bg-preview-image");
    imgLayer.style.position = "absolute";
    imgLayer.style.inset = "0";
    imgLayer.style.backgroundImage = "url(\"" + url.replace(/"/g, "") + "\")";
    imgLayer.style.backgroundSize = "cover";
    // The real review bar uses `center bottom` so a matched full-window image
    // shows its lower edge, not an unrelated crop from its centre.
    imgLayer.style.backgroundPosition = "center bottom";
    imgLayer.style.filter = blur > 0 ? "blur(" + (blur * 0.18).toFixed(1) + "px)" : "";
    imgLayer.style.opacity = String(Math.max(0, Math.min(100, opacity)) / 100);
    stage.appendChild(imgLayer);
  }

  /* Synced (default): the counts row rides on the Show Answer active colour.
     Off: its own bbar_stats_bar_bg pair. */
  function bbarStatsBarBg(vals, isDark, suffix) {
    const synced = vals["bbar_stats_sync"] !== false;
    if (synced) return vals["bbar_show_answer_hover_bg_" + suffix] || (isDark ? "#e0e0e0" : "#2c2c2c");
    return vals["bbar_stats_bar_bg_" + suffix] || (isDark ? "#e0e0e0" : "#2c2c2c");
  }

  // Which of the bar's two states is showing — local UI state, not a
  // persisted setting, same as Deck Stats' Bars/Donut/Grouped switcher.
  let bbarActiveMode = "answer";

  function bbarStatTextMode(vals) {
    const mode = vals["bbar_stattxt_mode"] || "hover";
    return ["hover", "inverted", "fixed", "off"].indexOf(mode) >= 0 ? mode : "hover";
  }

  function bbarUtilityButton(label) {
    const btn = el("button", "osw-preview-bbar-btn osw-preview-bbar-utility", label);
    btn.type = "button";
    return btn;
  }

  function bbarSideColumns(bar, vals, suffix, timerPos, timerPill, customEnabled) {
    const left = el("div", "osw-preview-bbar-side is-left");
    const right = el("div", "osw-preview-bbar-side is-right");
    const otherBg = customEnabled
      ? (vals["bbar_other_bg_" + suffix] || (suffix === "dark" ? "#3a3a3a" : "#ffffff"))
      : (suffix === "dark" ? "#454545" : "#f0f0f0");
    const otherFg = customEnabled
      ? (vals["bbar_other_text_" + suffix] || (suffix === "dark" ? "#e0e0e0" : "#2c2c2c"))
      : (suffix === "dark" ? "#eeeeee" : "#2c2c2c");
    const radius = Math.max(0, Number(vals["bbar_btn_radius"] || 0));
    const padding = Math.max(0, Number(vals["bbar_btn_padding"] || 0));
    const height = Math.max(0, Number(vals["bbar_btn_height"] || 0));
    const edit = bbarUtilityButton("Edit");
    edit.style.background = otherBg; edit.style.color = otherFg;
    edit.style.borderRadius = radius + "px"; edit.style.padding = padding + "px 10px"; edit.style.minHeight = height + "px";
    const more = bbarUtilityButton("More");
    more.style.background = otherBg; more.style.color = otherFg;
    more.style.borderRadius = radius + "px"; more.style.padding = padding + "px 10px"; more.style.minHeight = height + "px";
    left.appendChild(edit);
    // "Out" is the reviewer bar's right-side utility placement: keep the
    // timer immediately before More rather than treating it as a left-side
    // companion to Edit. It uses More's exact button geometry in the preview.
    if (timerPos === "out" && timerPill) {
      timerPill.style.borderRadius = radius + "px";
      timerPill.style.padding = padding + "px 10px";
      timerPill.style.minHeight = height + "px";
      right.appendChild(timerPill);
    }
    right.appendChild(more);
    bar.appendChild(left);
    return right;
  }

  PREVIEW_PAINTERS.reviewer_bottom_bar = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    paintResolvedBackdropState(stage, bbarBackgroundState(vals, isDark));

    const suffix = isDark ? "dark" : "light";
    const radius = Math.max(0, Number(vals["bbar_btn_radius"] || 0));
    const padding = Math.max(0, Number(vals["bbar_btn_padding"] || 0));
    const btnHeight = Math.max(0, Number(vals["bbar_btn_height"] || 0));
    const barHeight = Math.max(20, Math.min(220, Number(vals["bbar_bar_height"] || 60)));
    const timerPos = vals["bbar_timer_position"] || "right";
    const stattxtMode = bbarStatTextMode(vals);
    const customEnabled = vals["bbar_custom_enabled"] !== false;

    const timerPill = el("div", "osw-preview-bbar-timer" + (timerPos === "out" ? " is-out" : ""), "0:07");
    timerPill.style.background = vals["bbar_timer_bg_" + suffix] || (isDark ? "#3a3a3a" : "#e5e5e5");
    timerPill.style.color = vals["bbar_timer_text_" + suffix] || (isDark ? "#e0e0e0" : "#2c2c2c");

    const bar = el("div", "osw-preview-bbar-bar");
    bar.style.height = barHeight + "px";
    bar.style.padding = padding + "px " + (padding + 6) + "px";
    const rightSide = bbarSideColumns(
      bar, vals, suffix, timerPos, timerPos === "out" ? timerPill : null, customEnabled
    );

    if (bbarActiveMode === "answer") {
      const buttons = el("div", "osw-preview-bbar-buttons");
      [["again", "Again", "<1m"], ["hard", "Hard", "<6m"], ["good", "Good", "<10m"], ["easy", "Easy", "2a"]].forEach(function (spec) {
        const key = spec[0];
        const cell = el("div", "osw-preview-bbar-btn-cell osw-preview-bbar-answer is-" + stattxtMode);
        const interval = el("span", "osw-preview-bbar-interval", spec[2]);
        // The real fixed-mode interval inherits the ease button's own text
        // colour. Using the separate generic interval tint here made every
        // number grey even when its button text was brown, green, or blue.
        interval.style.color = "inherit";
        const btn = el("button", "osw-preview-bbar-btn");
        btn.type = "button";
        btn.style.background = customEnabled
          ? (vals["bbar_" + key + "_bg_" + suffix] || "#cccccc")
          : (isDark ? "#454545" : "#f0f0f0");
        btn.style.color = customEnabled
          ? (vals["bbar_" + key + "_text_" + suffix] || "#000000")
          : (isDark ? "#eeeeee" : "#2c2c2c");
        btn.style.borderRadius = radius + "px";
        btn.style.padding = padding + "px 15px";
        btn.style.minHeight = btnHeight + "px";
        btn.appendChild(el("span", "osw-preview-bbar-label", spec[1]));
        if (stattxtMode !== "off") btn.appendChild(interval);
        cell.appendChild(btn);
        buttons.appendChild(cell);
      });
      bar.appendChild(buttons);
      bar.appendChild(rightSide);
    } else {
      const otherBtn = el("button", "osw-preview-bbar-btn osw-preview-bbar-btn-other osw-preview-bbar-show is-" + stattxtMode);
      otherBtn.type = "button";
      otherBtn.style.background = customEnabled
        ? (vals["bbar_show_answer_bg_" + suffix] || (isDark ? "#3a3a3a" : "#ffffff"))
        : (isDark ? "#454545" : "#f0f0f0");
      otherBtn.style.color = customEnabled
        ? (vals["bbar_show_answer_text_" + suffix] || (isDark ? "#e0e0e0" : "#2c2c2c"))
        : (isDark ? "#eeeeee" : "#2c2c2c");
      otherBtn.style.borderRadius = radius + "px";
      otherBtn.style.padding = padding + "px 15px";
      otherBtn.style.minHeight = btnHeight + "px";
      otherBtn.style.setProperty("--osw-bbar-stats-bg", bbarStatsBarBg(vals, isDark, suffix));
      otherBtn.style.setProperty(
        "--osw-bbar-stats-fg",
        vals["bbar_show_answer_hover_text_" + suffix] || (isDark ? "#3a3a3a" : "#f0f0f0")
      );

      const counts = el("div", "osw-preview-bbar-counts");
      [["new_bubble", "new_text", "12"], ["learn_bubble", "learn_text", "4"], ["review_bubble", "review_text", "23"]]
        .forEach(function (spec) {
          const pill = el("span", "osw-preview-bbar-count-pill", spec[2]);
          pill.style.background = vals["ovstyle_color_" + spec[0] + "_" + suffix] || "#888888";
          pill.style.color = vals["ovstyle_color_" + spec[1] + "_" + suffix] || "#ffffff";
          counts.appendChild(pill);
        });

      if (customEnabled && timerPos === "left") counts.insertBefore(timerPill, counts.firstChild);
      if (customEnabled && timerPos === "right") counts.appendChild(timerPill);
      otherBtn.appendChild(el("span", "osw-preview-bbar-label", "Show Answer"));
      if (customEnabled && stattxtMode !== "off") otherBtn.appendChild(counts);
      if (customEnabled && (stattxtMode === "fixed" || stattxtMode === "inverted")) {
        otherBtn.style.background = bbarStatsBarBg(vals, isDark, suffix);
        otherBtn.style.color = vals["bbar_show_answer_hover_text_" + suffix] || (isDark ? "#3a3a3a" : "#f0f0f0");
      }
      bar.appendChild(otherBtn);
      bar.appendChild(rightSide);
    }

    // Reviewer Fonts is edited from this card, so the preview must use the
    // same component role as the live bottom webview. Apply it to every piece
    // of text inside the buttons, including intervals, counts, and the timer.
    const reviewerFont = designerFontRole(vals, "reviewer_controls", isDark, "main");
    bar.style.fontFamily = reviewerFont.family;
    bar.querySelectorAll([
      ".osw-preview-bbar-btn",
      ".osw-preview-bbar-btn *",
      ".osw-preview-bbar-timer",
      ".osw-preview-bbar-count-pill"
    ].join(",")).forEach(function (node) {
      node.style.fontFamily = reviewerFont.family;
      node.style.fontSize = reviewerFont.size + "px";
      if (reviewerFont.customColor) node.style.color = reviewerFont.customColor;
    });
    stage.appendChild(bar);

    if (!vals["bbar_custom_enabled"]) {
      stage.appendChild(el(
        "div", "osw-preview-bbar-disabled-note",
        "Custom buttons disabled — Anki's native buttons will be used."
      ));
    }
  };

  // ── Reviewer Header Progress Bar preview ───────────────────────────────────
  //
  // Draws the reviewer header the gauge actually lives in — the same floating
  // pill of buttons, with the chip on the chosen side — rather than the gauge
  // alone on an empty stage. Position, "same height as the buttons", and the
  // button-style chip are the three things most likely to be got wrong, and
  // none of them are visible without the buttons next to it.
  //
  // The sample numbers are fixed (12 done, 5 new / 3 learning / 20 review left)
  // so every style and label is compared against one dataset; patcher.py's
  // _reviewer_progress_counts is what supplies the real ones.

  const RPROG_SAMPLE = { done: 12, new: 5, learn: 3, review: 20 };

  function rprogSample() {
    const left = RPROG_SAMPLE.new + RPROG_SAMPLE.learn + RPROG_SAMPLE.review;
    const total = RPROG_SAMPLE.done + left;
    return {
      done: RPROG_SAMPLE.done,
      new: RPROG_SAMPLE.new,
      learn: RPROG_SAMPLE.learn,
      review: RPROG_SAMPLE.review,
      left: left,
      total: total,
      pct: total > 0 ? Math.round((100 * RPROG_SAMPLE.done) / total) : 100,
    };
  }

  function rprogLabelText(vals, data) {
    switch (vals["rprog_label"] || "fraction") {
      case "none": return "";
      case "percent": return data.pct + "%";
      case "remaining": return data.left + " left";
      case "done": return data.done + " done";
      default: return data.done + "/" + data.total;
    }
  }

  /* The segment colours follow the count bubbles unless this section has been
     switched to Custom — the same resolution _reviewer_progress_settings does,
     reading the very fields the Bottom Bar section already edits. */
  function rprogSegmentColor(vals, isDark, which) {
    const custom = (vals["rprog_segment_source"] || "counts") === "custom";
    const fallback = { new: ["#1e8cff", "#0a84ff"], learn: ["#ff5757", "#ff453a"], review: ["#19c96b", "#12b765"] }[which];
    if (custom) {
      return designerPairValue(vals, "rprog_seg_" + which + "_light", "rprog_seg_" + which + "_dark",
                               "rprog_seg_" + which + "_theme_mode", isDark) || (isDark ? fallback[1] : fallback[0]);
    }
    const bubble = { new: "new_bubble", learn: "learn_bubble", review: "review_bubble" }[which];
    return vals["ovstyle_color_" + bubble + "_" + (isDark ? "dark" : "light")] ||
      (isDark ? fallback[1] : fallback[0]);
  }

  function rprogFillImage(vals, isDark) {
    const fill = designerPairValue(vals, "rprog_fill_light", "rprog_fill_dark", "rprog_fill_theme_mode", isDark) ||
      (isDark ? "#12b765" : "#19c96b");
    if (vals["rprog_gradient"] === false) return { flat: fill, image: fill };
    const end = designerPairValue(vals, "rprog_fill_end_light", "rprog_fill_end_dark", "rprog_fill_end_theme_mode", isDark) ||
      (isDark ? "#4bc4de" : "#5ad6f0");
    return { flat: fill, image: "linear-gradient(90deg, " + fill + ", " + end + ")" };
  }

  function rprogChip(vals, isDark, data) {
    const style = vals["rprog_style"] || "bar";
    const thickness = Math.max(2, Math.min(20, designerNum(vals["rprog_thickness"], 6)));
    const radius = Math.max(0, Math.min(999, designerNum(vals["rprog_radius"], 999)));
    const width = Math.max(40, Math.min(320, designerNum(vals["rprog_width"], 96)));
    const ringSize = Math.max(12, Math.min(40, designerNum(vals["rprog_ring_size"], 16)));
    const track = designerPairValue(vals, "rprog_track_light", "rprog_track_dark", "rprog_track_theme_mode", isDark) ||
      (isDark ? "rgba(255, 255, 255, 0.16)" : "rgba(0, 0, 0, 0.12)");
    const text = designerPairValue(vals, "rprog_text_light", "rprog_text_dark", "rprog_text_theme_mode", isDark) ||
      (isDark ? "#e8e8e8" : "#2c2c2c");
    const fill = rprogFillImage(vals, isDark);

    const chip = el("div", "osw-preview-rprog-chip is-" + style);
    if (vals["rprog_chrome"] === false) chip.classList.add("is-bare");
    chip.style.color = text;

    if (style !== "text") {
      if (style === "ring") {
        const svgNs = "http://www.w3.org/2000/svg";
        const stroke = Math.max(1, Math.min(Math.floor(ringSize / 2), thickness));
        const r = (ringSize - stroke) / 2;
        const circumference = 2 * Math.PI * r;
        const svg = document.createElementNS(svgNs, "svg");
        svg.setAttribute("class", "osw-preview-rprog-ring");
        svg.setAttribute("viewBox", "0 0 " + ringSize + " " + ringSize);
        svg.setAttribute("width", String(ringSize));
        svg.setAttribute("height", String(ringSize));
        const mk = function (cls) {
          const c = document.createElementNS(svgNs, "circle");
          c.setAttribute("class", cls);
          c.setAttribute("cx", String(ringSize / 2));
          c.setAttribute("cy", String(ringSize / 2));
          c.setAttribute("r", r.toFixed(2));
          c.setAttribute("fill", "none");
          c.setAttribute("stroke-width", String(stroke));
          return c;
        };
        const trackCircle = mk("osw-preview-rprog-ring-track");
        trackCircle.setAttribute("stroke", track);
        const fillCircle = mk("osw-preview-rprog-ring-fill");
        fillCircle.setAttribute("stroke", fill.flat);
        fillCircle.setAttribute("stroke-linecap", "round");
        fillCircle.setAttribute("stroke-dasharray",
          (circumference * data.pct / 100).toFixed(2) + " " + circumference.toFixed(2));
        fillCircle.setAttribute("transform", "rotate(-90 " + ringSize / 2 + " " + ringSize / 2 + ")");
        svg.appendChild(trackCircle);
        svg.appendChild(fillCircle);
        chip.appendChild(svg);
      } else {
        const trackEl = el("span", "osw-preview-rprog-track");
        trackEl.style.width = width + "px";
        trackEl.style.height = thickness + "px";
        trackEl.style.borderRadius = radius + "px";
        trackEl.style.background = style === "segments" ? "transparent" : track;
        if (style === "segments") {
          trackEl.classList.add("is-segmented");
          const total = Math.max(1, data.total);
          [["done", fill.image], ["new", rprogSegmentColor(vals, isDark, "new")],
           ["learn", rprogSegmentColor(vals, isDark, "learn")],
           ["review", rprogSegmentColor(vals, isDark, "review")]].forEach(function (spec) {
            const seg = el("span", "osw-preview-rprog-seg");
            seg.style.width = (100 * data[spec[0]] / total).toFixed(3) + "%";
            seg.style.background = spec[1];
            seg.style.borderRadius = radius + "px";
            trackEl.appendChild(seg);
          });
        } else {
          const fillEl = el("span", "osw-preview-rprog-fill");
          fillEl.style.width = data.pct + "%";
          fillEl.style.background = fill.image;
          trackEl.appendChild(fillEl);
        }
        chip.appendChild(trackEl);
      }
    }

    const labelText = rprogLabelText(vals, data) || (style === "text" ? data.done + "/" + data.total : "");
    if (labelText) chip.appendChild(el("span", "osw-preview-rprog-text", labelText));
    else chip.classList.add("is-labelless");
    return chip;
  }

  PREVIEW_PAINTERS.reviewer_progress = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    // The reviewer's own backdrop, so the floating header reads as floating.
    paintResolvedBackdropState(stage, designerBgSourceState(vals, isDark, REVIEWER_BG_KEYS));

    const wrap = el("div", "osw-preview-rprog-wrap" + (isDark ? " is-dark" : ""));
    const header = el("div", "osw-preview-rprog-header");

    const data = rprogSample();
    const enabled = vals["rprog_enabled"] !== false;
    const chip = enabled ? rprogChip(vals, isDark, data) : null;
    if (chip && (vals["rprog_position"] || "right") === "left") header.appendChild(chip);
    ["Decks", "Add", "Browse", "Stats", "Sync"].forEach(function (label) {
      header.appendChild(el("span", "osw-preview-rprog-btn", label));
    });
    if (chip && (vals["rprog_position"] || "right") !== "left") header.appendChild(chip);

    wrap.appendChild(header);
    wrap.appendChild(el("div", "osw-preview-rprog-card", "Question"));

    stage.appendChild(wrap);
  };

  // ── Sidebar previews (Background / Action Buttons / Deck Icons) ───────────
  //
  // The three Qt painters this replaces (_draw_sidebar_preview_mockup,
  // _draw_sidebar_preview_actions, _draw_sidebar_preview_deck_rows in
  // settings/_page_sidebar.py) all drew the same thing first: the main-menu
  // backdrop with the sidebar frame floating on it. That shared part is
  // designerSidebarFrame below; each painter then fills the frame with whatever
  // its own card is about.

  // The buttons the sidebar itself lays out. The "More" menu's own entries
  // (get_shared / create_deck / import_file) are deliberately not here: they
  // are drawn inside More, not on the sidebar.
  const SIDEBAR_ACTION_ICON_KEYS = [
    "add", "browse", "stats", "sync", "settings", "gamification", "more"
  ];

  const SIDEBAR_READY_ITEMS = [
    { key: "inbox", label: "Inbox" },
    { key: "warm_up", label: "Warm up" },
    { key: "today", label: "Today" },
    { key: "cool_down", label: "Cool-Down" }
  ];

  /* A masked <span> for one icon value ("system:add-card.svg", a user filename,
     or "emoji:🔥"), tinted `color` — the same resolution renderIcon's chip does,
     so a preview glyph is the glyph the deck browser will draw. */
  function designerIconGlyph(value, color, size) {
    const span = el("span", "osw-sbprev-glyph");
    span.style.width = size + "px";
    span.style.height = size + "px";
    const raw = String(value || "");
    if (raw.indexOf("emoji:") === 0) {
      span.classList.add("is-emoji");
      span.style.fontSize = size + "px";
      span.textContent = raw.slice(6);
      return span;
    }
    const url = resolveIconAssetUrl(raw);
    if (!url) { span.style.opacity = "0"; return span; }
    span.style.background = color;
    span.style.webkitMaskImage = "url('" + url + "')";
    span.style.maskImage = "url('" + url + "')";
    return span;
  }

  function designerNum(value, fallback) {
    const n = Number(value);
    return isNaN(n) ? fallback : n;
  }

  /* Everything the sidebar frame is drawn from, with "Sync with Widget Color
     and Effect" resolved: when it is on, the fill and the effect come from the
     shared widget styling instead of the sidebar's own keys — which is exactly
     what the legacy save path persisted into the sidebar keys on the way out
     (settings/_page_sidebar.py:1705-1718). */
  function designerSidebarSpec(vals, isDark) {
    const type = vals["modern_menu_sidebar_bg_type"] || "color";
    const bgMode = vals["modern_menu_sidebar_bg_mode"] || "custom";
    const matchesWidgets = bgMode === "custom";
    const sync = matchesWidgets || !!vals["modern_menu_sidebar_sync_box_effect"];
    let color;
    let blur;
    let opacity;
    let radius;
    let stroke;
    if (sync) {
      color = designerPairValue(vals, "widget_box_color_light", "widget_box_color_dark",
                                "onigiri_canvas_inset_color_theme_mode", isDark);
      blur = designerNum(vals["onigiri_canvas_inset_effect_blur"], 0);
      opacity = designerNum(vals["onigiri_canvas_inset_effect_opacity"], 100);
      radius = designerNum(vals["onigiri_canvas_inset_border_radius"], 20);
      stroke = designerNum(vals["onigiri_canvas_inset_border_width"], 1);
    } else {
      color = designerPairValue(vals, "modern_menu_sidebar_bg_color_light",
                                "modern_menu_sidebar_bg_color_dark",
                                "modern_menu_sidebar_bg_color_theme_mode", isDark);
      blur = designerNum(vals["modern_menu_sidebar_bg_blur"], 0);
      opacity = designerNum(vals["modern_menu_sidebar_bg_opacity"], 100);
      radius = designerNum(vals["modern_menu_sidebar_radius"], 15);
      stroke = designerNum(vals["modern_menu_sidebar_stroke"], 1);
    }
    // The border can be customized while fill/effects remain widget-synced.
    if (!matchesWidgets && vals["modern_menu_sidebar_border_custom"]) {
      radius = designerNum(vals["modern_menu_sidebar_radius"], 15);
      stroke = designerNum(vals["modern_menu_sidebar_stroke"], 1);
    }
    if (!color) color = isDark ? "#2C2C2C" : "#F3F3F3";
    if (!matchesWidgets && type === "accent") color = CTX.accent || color;

    let image = "";
    if (type === "image_color") {
      image = designerPairValue(vals, "modern_menu_sidebar_bg_image_light",
                                "modern_menu_sidebar_bg_image_dark",
                                "modern_menu_sidebar_bg_image_theme_mode", isDark,
                                "modern_menu_sidebar_bg_image");
    } else if (type === "slideshow") {
      const list = Array.isArray(vals["modern_menu_sidebar_slideshow_images"])
        ? vals["modern_menu_sidebar_slideshow_images"] : [];
      image = list[0] || "";
    }

    if (matchesWidgets) image = "";

    // Custom: the main background shows through the frame and only
    // an overlay sits on top of it — either a translucent white/black wash with
    // a backdrop blur (glassmorphism) or a flat tint at the chosen intensity.
    // Mirrors patcher.py:3017-3050, which is the only reader of these keys.
    let backdropBlur = matchesWidgets ? blur * 0.2 : 0;
    if (bgMode === "main") {
      image = "";
      const effect = vals["onigiri_sidebar_main_bg_effect_mode"] || "opaque";
      if (effect === "glassmorphism") {
        const intensity = designerNum(vals["onigiri_sidebar_main_bg_effect_intensity"], 50);
        backdropBlur = (intensity / 100) * 15;
        color = "rgba(" + (isDark ? "0, 0, 0, " : "255, 255, 255, ") +
                ((intensity / 100) * 0.3).toFixed(3) + ")";
      } else {
        const intensity = designerNum(vals["onigiri_sidebar_opaque_tint_intensity"], 30);
        const tint = designerPairValue(vals, "onigiri_sidebar_opaque_tint_color_light",
                                       "onigiri_sidebar_opaque_tint_color_dark",
                                       "onigiri_sidebar_opaque_tint_color_theme_mode", isDark)
                     || (isDark ? "#1D1D1D" : "#FFFFFF");
        color = rgba(tint, intensity / 100);
      }
    }

    return {
      type: type,
      bgMode: bgMode,
      color: color,
      image: image,
      blur: blur,
      opacity: opacity,
      backdropBlur: backdropBlur,
      radius: radius,
      stroke: stroke,
      margin: designerNum(vals["modern_menu_sidebar_margin"], 10),
      position: vals["modern_menu_sidebar_position"] || "left",
      borderColor: designerPairValue(vals, "widget_border_color_light", "widget_border_color_dark",
                                     "onigiri_canvas_inset_color_theme_mode", isDark)
                   || (isDark ? "#424242" : "#e0e0e0"),
      isDark: isDark,
      fg: designerFontRole(vals, "main", isDark).color,
      iconColor: designerPairValue(vals, "sb_icon_color_light", "sb_icon_color_dark",
                                   "onigiri_sidebar_deck_colors_theme_mode", isDark)
                 || (isDark ? "#E0E0E0" : "#333333")
    };
  }

  /* The backdrop plus the sidebar frame, positioned/rounded/stroked from the
     live values. Returns the frame's content box for the caller to fill. */
  function designerSidebarFrame(stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    stage.style.minHeight = "";
    designerPaintBackdrop(stage, vals, isDark);

    const spec = designerSidebarSpec(vals, isDark);
    const frame = el("div", "osw-sbprev-frame");
    frame.style.borderRadius = spec.radius + "px";
    frame.style.border = spec.stroke + "px solid " + spec.borderColor;
    frame.style.setProperty("--osw-sbprev-inner-radius", Math.max(0, spec.radius - spec.stroke) + "px");
    // Lay out at a useful sidebar width, then scale every dimension together:
    // fonts, icons, profile, padding, radius and stroke. Very wide sidebars
    // cannot be reduced literally inside this half-dialog stage — a 1,200 px
    // sidebar made 13 px labels render at only a few pixels tall. The preview
    // therefore keeps the configured width up to a representative wide
    // sidebar and treats anything larger as the same readable detail view.
    // An unpinned sidebar always returns to its standard width. Check the
    // toggle here as well as resetting the stored value in the schema so the
    // preview changes on the same click, before its autosave response returns.
    const sidebarWidthPinned = !!vals["modern_menu_sidebar_width_pinned"];
    const configuredWidth = sidebarWidthPinned
      ? Math.max(320, designerNum(
        vals["modern_menu_sidebar_width"],
        designerNum((CTX.sidebarBg || {}).width, 345)
      ))
      : 345;
    const nativeWidth = Math.min(configuredWidth, 520);
    frame.style.width = nativeWidth + "px";
    frame.dataset.configuredWidth = String(configuredWidth);
    frame.style.transformOrigin = "top left";
    function fitSidebar() {
      const availableWidth = stage.clientWidth;
      const availableHeight = stage.clientHeight;
      if (!availableWidth || !availableHeight) return;
      // Left/right previews use nearly the whole canvas. Center leaves a little
      // more backdrop on both sides so its position is still unmistakable. The
      // whole preview stays deliberately modest: it is a composition cue, not
      // a life-size replica of the sidebar.
      const isCentered = spec.position === "center";
      const share = isCentered ? 0.84 : 0.92;
      const scale = Math.min(
        isCentered ? 0.9 : 1.08,
        availableWidth * share / (nativeWidth + 2 * spec.margin)
      );
      const margin = spec.margin * scale;
      // Centered is the dashboard composition: the sidebar sits at the top,
      // leaving room below for the dashboard widgets represented in the
      // preview by the compact tile grid added after this frame is created.
      // Its full native content needs a generous, stable height; squeezing it
      // to a percentage of the stage hides the lower deck rows.
      const nativeHeight = isCentered
        ? 430
        : Math.max(0, availableHeight / scale - 2 * spec.margin);
      frame.style.top = (isCentered ? 14 : margin) + "px";
      frame.style.height = nativeHeight + "px";
      frame.style.left = (spec.position === "center"
        ? (availableWidth - nativeWidth * scale) / 2
        : spec.position === "right"
          ? availableWidth - nativeWidth * scale - margin : margin) + "px";
      frame.style.transform = "scale(" + scale + ")";
      frame.dataset.previewScale = String(scale);
      frame.dataset.nativeHeight = String(nativeHeight);
      if (frame.__fitWidgets) frame.__fitWidgets();
    }
    if (stage.__sidebarPreviewResizeObserver) stage.__sidebarPreviewResizeObserver.disconnect();
    if (typeof ResizeObserver !== "undefined") {
      stage.__sidebarPreviewResizeObserver = new ResizeObserver(fitSidebar);
      stage.__sidebarPreviewResizeObserver.observe(stage);
    }
    fitSidebar();

    const fill = el("div", "osw-sbprev-fill");
    fill.style.background = spec.bgMode === "custom"
      ? rgba(spec.color, Math.max(0, Math.min(100, spec.opacity)) / 100) : spec.color;
    const fillBlur = spec.bgMode === "custom" ? spec.blur * 0.2 : spec.backdropBlur;
    if (fillBlur) {
      fill.style.backdropFilter = "blur(" + fillBlur.toFixed(1) + "px)";
      fill.style.webkitBackdropFilter = fill.style.backdropFilter;
    }
    frame.appendChild(fill);

    const url = spec.image ? imageUrl("sidebar_bg", spec.image) : "";
    if (url) {
      const img = el("div", "osw-sbprev-fill osw-sbprev-image");
      img.style.backgroundImage = "url(\"" + url.replace(/"/g, "") + "\")";
      img.style.filter = spec.blur > 0 ? "blur(" + spec.blur.toFixed(1) + "px)" : "";
      img.style.opacity = String(Math.max(0, Math.min(100, spec.opacity)) / 100);
      frame.appendChild(img);
    }

    const content = el("div", "osw-sbprev-content");
    frame.appendChild(content);
    stage.appendChild(frame);
    return { frame: frame, content: content, spec: spec };
  }

  /* Centered sidebar mode is a dashboard rather than a full-height rail. Give
     its settings preview a quiet row of widget tiles so the composition reads
     at a glance without pretending to render the user's actual dashboard. */
  function designerCenteredWidgetPlaceholders(stage, built) {
    if (built.spec.position !== "center") return;
    const grid = el("div", "osw-sbprev-widget-placeholders");
    function fitWidgets() {
      const scale = Number(built.frame.dataset.previewScale) || 1;
      const nativeHeight = Number(built.frame.dataset.nativeHeight) || 0;
      grid.style.top = (14 + nativeHeight * scale + 18) + "px";
      grid.style.width = Math.min(
        stage.clientWidth * 0.76,
        Number(built.frame.style.width.replace("px", "")) * scale
      ) + "px";
      grid.style.left = "50%";
      grid.style.transform = "translateX(-50%)";
    }
    built.frame.__fitWidgets = fitWidgets;
    fitWidgets();
    for (let index = 0; index < 4; index += 1) {
      const tile = el("span", "osw-sbprev-widget-placeholder");
      tile.style.background = rgba(built.spec.fg, built.spec.isDark ? 0.13 : 0.09);
      tile.style.borderColor = rgba(built.spec.fg, built.spec.isDark ? 0.19 : 0.14);
      grid.appendChild(tile);
    }
    stage.appendChild(grid);
  }

  /* The profile, painted by the Profile page's own renderer (paintProfileItem)
     rather than by a lookalike here. Whatever type is selected — Bar, Ring,
     Minimal — with its real picture, background, colours, font and level chip,
     because "the profile" is one thing and two previews of it that can disagree
     are worse than one. */
  function designerSidebarProfile(host, vals, spec) {
    const slot = el("div", "osw-sbprev-profile");
    // paintProfileItem() owns its target's className, so it gets a child of its
    // own rather than the slot itself.
    const item = el("div", null);
    slot.appendChild(item);
    paintProfileItem(item, spec.isDark);
    const smallRole = designerFontRole(vals, "sidebar_small", spec.isDark, "main");
    item.querySelectorAll(".osw-preview-sub-text, .rl-chip-level").forEach(function (node) {
      node.style.fontFamily = smallRole.family;
      node.style.fontSize = smallRole.size + "px";
      if (smallRole.customColor) node.style.color = smallRole.customColor;
    });
    host.appendChild(slot);
  }

  /* The deck list's own header row: the "DECKS" caption and the search / list /
     home controls above the tree (the real one is `#deck-list-header`). It is
     part of the sidebar, so a preview without it is short by one row. */
  function designerDeckHeader(host, vals, spec, isDark) {
    const head = el("div", "osw-sbprev-deckhead");
    const title = el("span", "osw-sbprev-deckhead-title", str("decks", "Decks"));
    const titleRole = designerFontRole(vals, "deck_title", isDark, "subtle");
    title.style.color = spec.iconColor;
    if (titleRole.customColor) title.style.color = titleRole.customColor;
    title.style.fontFamily = titleRole.family;
    title.style.fontSize = titleRole.size + "px";
    head.appendChild(title);
    const tools = el("span", "osw-sbprev-deckhead-tools");
    function appendTool(fieldId, label, size) {
      const button = el("button", "osw-sbprev-deckhead-button");
      button.type = "button";
      button.title = label;
      button.setAttribute("aria-label", label);
      button.appendChild(designerIconGlyph(iconValue(fieldId), spec.iconColor, size || 13));
      tools.appendChild(button);
      return button;
    }
    // Home is the escape hatch for Hidden Action Buttons; search and sort are
    // always present in the real deck header.
    appendTool("modern_menu_icon_header_search", str("search", "Search"));
    appendTool("modern_menu_icon_header_sort", str("sort", "Sort"));
    if ((vals["modern_menu_ready_layout_mode"] || "list") === "hidden") {
      appendTool(
        "modern_menu_icon_ready_section",
        vals["modern_menu_ready_title"] || str("ready_to_go", "Ready to go")
      );
    }
    if ((vals["sidebarActionsMode"] || "list") === "archived") {
      appendTool("modern_menu_icon_header_home", str("home", "Home"));
    }
    head.appendChild(tools);
    host.appendChild(head);
  }

  /* Which action buttons are on screen and in what order. Unknown entries (the
     "profile" pill, sidebar-API buttons from other add-ons) are skipped here —
     they are still carried in the stored layout, they are just not action
     buttons this preview draws. */
  function designerActionOrder(vals) {
    const layout = vals["sidebarButtonLayout"] || {};
    const visible = Array.isArray(layout.visible) ? layout.visible : [];
    return visible.filter(function (id) { return SIDEBAR_ACTION_ICON_KEYS.indexOf(id) !== -1; });
  }

  /* The action strip, drawn the way the real sidebar draws it (and the way the
     Qt preview did — _draw_sidebar_preview_actions, settings/_page_sidebar.py:867):
     List mode is plain icon+label rows with no chrome, except "Add", which
     becomes a full-width dashed call-to-action bar while that option is on.
     Collapsed mode is one justified row of icon-only tinted pills. */
  function sidebarIconTint(vals, key, isDark) {
    const light = vals[key + "_light"] == null ? vals[key] : vals[key + "_light"];
    return (isDark && vals[key + "_dark"] != null ? vals[key + "_dark"] : light) || "";
  }

  function designerSidebarActions(host, vals, spec, mode) {
    if (mode === "archived") return;
    const size = designerNum(vals["modern_menu_icon_size_action_button"], 14);
    const order = designerActionOrder(vals);
    const textRole = designerFontRole(vals, "action_buttons", spec.isDark, "main");
    if (!order.length) return;

    const strip = el("div", "osw-sbprev-actions" + (mode === "collapsed" ? " is-collapsed" : ""));
    order.forEach(function (key) {
      const label = (fieldById["modern_menu_icon_" + key] || {}).label || key;
      const item = el("div", "osw-sbprev-action");
      const tint = sidebarIconTint(vals, "modern_menu_icon_color_" + key, spec.isDark) || spec.iconColor;
      if (mode === "collapsed") {
        item.style.background = rgba(spec.fg, 0.1);
        item.title = label;
        item.appendChild(designerIconGlyph(iconValue("modern_menu_icon_" + key), tint, size));
        strip.appendChild(item);
        return;
      }
      if (key === "add" && vals["sidebarAddDashed"]) {
        item.classList.add("is-dashed");
        item.style.borderColor = rgba(spec.fg, 0.47);
      }
      item.appendChild(designerIconGlyph(iconValue("modern_menu_icon_" + key), tint, size));
      const text = el("span", "osw-sbprev-action-label", label);
      text.style.color = textRole.customColor || spec.fg;
      text.style.fontFamily = textRole.family;
      text.style.fontSize = textRole.size + "px";
      item.appendChild(text);
      strip.appendChild(item);
    });
    host.appendChild(strip);
  }

  /* Ready to Go uses the real sidebar's vertical button geometry and reads
     the same icon, tint, spacing, radius and surface fields as ready_to_go.py. */
  function designerSidebarReady(host, vals, spec, isDark) {
    const layoutMode = vals["modern_menu_ready_layout_mode"] || "list";
    if (layoutMode === "hidden") return;
    const collapsed = layoutMode === "collapsed";
    const section = el("div", "osw-sbprev-ready" + (collapsed ? " is-collapsed" : ""));
    const textColor = vals["modern_menu_ready_text_color"] ||
      (isDark ? vals["theme_subtle_dark"] : vals["theme_subtle_light"]) ||
      (isDark ? "#9e9e9e" : "#757575");
    const borderColor = vals["modern_menu_ready_border_color"] ||
      (isDark ? vals["theme_border_dark"] : vals["theme_border_light"]) ||
      (isDark ? "#424242" : "#e0e0e0");
    const buttonBackground = vals["modern_menu_ready_button_background"] || "transparent";
    const iconSize = Math.max(8, Math.min(40,
      designerNum(vals["modern_menu_ready_icon_size"], 16)));
    const gap = Math.max(0, Math.min(24,
      designerNum(vals["modern_menu_ready_gap"], 6)));
    const radius = Math.max(0, Math.min(30,
      designerNum(vals["modern_menu_ready_radius"], 9)));
    const showBorder = vals["modern_menu_ready_show_border"] !== false;

    if (vals["modern_menu_ready_show_title"] !== false) {
      const title = el("div", "osw-sbprev-ready-title",
        vals["modern_menu_ready_title"] || "Ready to go");
      title.style.color = textColor;
      title.style.fontFamily = designerFontRole(vals, "main", isDark).family;
      section.appendChild(title);
    }

    const actions = el("div", "osw-sbprev-ready-actions" + (collapsed ? " is-collapsed" : ""));
    actions.style.gap = (collapsed ? 5 : gap) + "px";
    const textRole = designerFontRole(vals, "action_buttons", isDark, "main");
    SIDEBAR_READY_ITEMS.forEach(function (item) {
      const button = el("div", "osw-sbprev-ready-action");
      if (collapsed) button.title = item.label;
      button.style.borderColor = collapsed ? "transparent" : borderColor;
      button.style.borderWidth = collapsed ? "1px" : (showBorder ? "1px" : "0");
      button.style.borderRadius = (collapsed ? 9 : radius) + "px";
      button.style.background = collapsed ? rgba(spec.fg, 0.1) : buttonBackground;
      const tint = sidebarIconTint(vals, "modern_menu_icon_color_ready_" + item.key, isDark) || textColor;
      button.appendChild(designerIconGlyph(
        iconValue("modern_menu_icon_ready_" + item.key), tint, iconSize
      ));
      const label = el("span", "osw-sbprev-ready-label", item.label);
      label.style.color = textColor;
      label.style.fontFamily = textRole.family;
      label.style.fontSize = textRole.size + "px";
      button.appendChild(label);
      actions.appendChild(button);
    });
    section.appendChild(actions);
    host.appendChild(section);
  }

  function designerSidebarSectionOrder(vals) {
    const known = ["profile", "actions", "ready_to_go", "decks"];
    const raw = vals["modern_menu_sidebar_section_layout"] || {};
    const saved = Array.isArray(raw) ? raw :
      (Array.isArray(raw.visible) ? raw.visible : []);
    const order = saved.filter(function (id, index) {
      return known.indexOf(id) !== -1 && saved.indexOf(id) === index;
    });
    // Layouts saved before Profile became its own section should keep Profile
    // immediately above Actions instead of unexpectedly moving it to the end.
    if (order.indexOf("profile") === -1) {
      const actionsIndex = order.indexOf("actions");
      order.splice(actionsIndex === -1 ? 0 : actionsIndex, 0, "profile");
    }
    known.forEach(function (id) {
      if (order.indexOf(id) === -1) order.push(id);
    });
    return order;
  }

  const SIDEBAR_PREVIEW_DECKS = [
    { key: "folder", label: "Japanese", level: 0, counts: [12, 3, 40], collapse: "collapse_open" },
    { key: "subdeck", label: "Vocab", level: 1, counts: [5, 0, 12] },
    { key: "subdeck", label: "Kanji", level: 1, counts: [0, 0, 0] },
    { key: "deck", label: "Physics", level: 0, counts: [8, 1, 22], collapse: "collapse_closed" },
    { key: "filtered_deck", label: "Leeches", level: 0, counts: [0, 0, 6] }
  ];

  const SIDEBAR_COUNT_COLORS = ["#1e8cff", "#19c96b", "#ff5757"];

  function designerIndentStep(vals) {
    const mode = vals["deck_indentation_mode"] || "default";
    if (mode === "smaller") return 10;
    if (mode === "bigger") return 40;
    if (mode === "custom") return designerNum(vals["deck_indentation_custom_px"], 20);
    return 20;
  }

  /* Keep the preview's badge font at the exact live value. The live size is
     relative to the main sidebar font, except for the explicit custom-pixel
     option (patcher.py's generated tr.deck rule). */
  function designerBadgeFontSize(vals, mainFontSize) {
    const key = vals["modern_menu_count_badge_size"] || "small";
    if (key === "custom") {
      return designerNum(vals["modern_menu_count_badge_size_custom_px"], 16);
    }
    const em = ({ small: 0.75, medium: 0.98, big: 1.2 }[key] || 0.75);
    return em * mainFontSize;
  }

  function designerSidebarCountColors(vals, role, isDark) {
    const mode = isDark ? "dark" : "light";
    const defaults = {
      new: { bg: ["#a3c5e8", "#68a0d9"], fg: "#13375b" },
      learn: { bg: ["#e8a3a3", "#d96868"], fg: "#731717" },
      review: { bg: ["#a3e8b8", "#68d98a"], fg: "#1b7a38" }
    }[role];
    const paletteBg = vals["sb_count_" + role + "_bg_" + mode] || defaults.bg[isDark ? 1 : 0];
    const paletteFg = vals["sb_count_" + role + "_fg_" + mode] || defaults.fg;
    const overviewBg = vals["ovstyle_color_" + role + "_bubble_" + mode];
    const overviewFg = vals["ovstyle_color_" + role + "_text_" + mode];
    return { bg: overviewBg || paletteBg, fg: overviewFg || paletteFg };
  }

  /* Whether a deck row draws its glyph at all: each row type has its own "hide"
     switch, and "hide default icons" hides every one of them that is still the
     bundled default (settings/_infra.py _deck_icon_preview_visible). */
  function designerDeckIconVisible(vals, key) {
    const hideKey = {
      folder: "modern_menu_hide_folder_icon",
      subdeck: "modern_menu_hide_subdeck_icon",
      deck: "modern_menu_hide_deck_icon",
      filtered_deck: "modern_menu_hide_filtered_deck_icon"
    }[key];
    if (hideKey && vals[hideKey]) return false;
    if (vals["modern_menu_hide_default_icons"]) {
      const value = String(iconValue("modern_menu_icon_" + key) || "");
      if (!value || value.indexOf("system:") === 0) return false;
    }
    return true;
  }

  // Which sample deck row (SIDEBAR_PREVIEW_DECKS index) shows which marker,
  // for the Markers page's stage — skips row 0 ("Japanese", the open folder)
  // so the marker dots sit on plain deck rows the way they do in the real list.
  const SIDEBAR_MARKER_ROWS = [1, 2, 3, 4];

  function designerMarkerDot(vals, marker) {
    const color = vals[marker.color_field] || "#888888";
    const icon = String(vals[marker.icon_field] || "default");
    const dot = el("span", "osw-marker-dot");
    if (icon.indexOf("emoji:") === 0) {
      dot.classList.add("is-emoji");
      dot.style.color = color;
      dot.textContent = icon.slice(6);
      return dot;
    }
    const url = icon && icon !== "default" ? resolveIconAssetUrl(icon) : "";
    dot.style.background = color;
    if (url) {
      dot.classList.add("is-icon");
      dot.style.webkitMaskImage = "url('" + url + "')";
      dot.style.maskImage = "url('" + url + "')";
    }
    return dot;
  }

  function designerDeckRows(host, vals, spec, isDark, markerList) {
    const listBg = designerPairValue(vals, "sb_deck_list_bg_light", "sb_deck_list_bg_dark",
                                     "onigiri_sidebar_deck_colors_theme_mode", isDark);
    const highlightBg = designerPairValue(vals, "sb_highlight_bg_light", "sb_highlight_bg_dark",
                                          "onigiri_sidebar_deck_colors_theme_mode", isDark)
                        || (isDark ? "#3c3c3c" : "#eeeeee");
    const highlightFg = designerPairValue(vals, "sb_highlight_fg_light", "sb_highlight_fg_dark",
                                          "onigiri_sidebar_deck_colors_theme_mode", isDark);
    const filteredColor = designerPairValue(vals, "sb_icon_color_filtered_light",
                                            "sb_icon_color_filtered_dark",
                                            "onigiri_sidebar_deck_colors_theme_mode", isDark)
                          || "#0077C8";
    const iconSize = designerNum(vals["modern_menu_icon_size_deck_folder"], 20);
    const collapseSize = designerNum(vals["modern_menu_icon_size_collapse"], 12);
    const step = designerIndentStep(vals);
    const mainRole = designerFontRole(vals, "main", isDark);
    const badgeFont = designerBadgeFontSize(vals, mainRole.size);
    const deckNameRole = designerFontRole(vals, "deck_names", isDark, "main");
    const hideZero = !!vals["hideDeckCounts"];
    const hideAll = !!vals["hideAllDeckCounts"];

    const list = el("div", "osw-sbprev-decks");
    if (listBg) list.style.background = listBg;
    designerDeckHeader(list, vals, spec, isDark);

    SIDEBAR_PREVIEW_DECKS.forEach(function (deck, index) {
      const row = el("div", "osw-sbprev-deck");
      // One highlighted row, so the highlight colours are visible without the
      // user having to hover the (non-interactive) mockup.
      const active = index === 1;
      if (active) {
        row.style.background = highlightBg;
        row.style.borderRadius = "8px";
      }
      row.style.paddingLeft = (step * deck.level) + "px";

      // A glyph's own tint (set in its picker) wins; otherwise the palette —
      // filtered decks have their own palette colour. Mirrors the CSS cascade
      // patcher.generate_icon_css emits.
      function glyphColor(key) {
        return sidebarIconTint(vals, "modern_menu_icon_color_" + key, isDark) ||
          (key === "filtered_deck" ? filteredColor : spec.iconColor);
      }

      const collapse = el("span", "osw-sbprev-collapse");
      if (deck.collapse) {
        collapse.appendChild(designerIconGlyph(
          iconValue("modern_menu_icon_" + deck.collapse), glyphColor(deck.collapse), collapseSize
        ));
      }
      row.appendChild(collapse);

      if (designerDeckIconVisible(vals, deck.key)) {
        row.appendChild(designerIconGlyph(
          iconValue("modern_menu_icon_" + deck.key), glyphColor(deck.key), iconSize
        ));
      }

      const name = el("span", "osw-sbprev-deck-name", deck.label);
      name.style.color = deckNameRole.customColor || ((active && highlightFg) ? highlightFg : spec.fg);
      name.style.fontFamily = deckNameRole.family;
      name.style.fontSize = deckNameRole.size + "px";
      row.appendChild(name);

      const markerRow = markerList && SIDEBAR_MARKER_ROWS.indexOf(index);
      if (markerList && markerRow >= 0 && markerList[markerRow]) {
        row.appendChild(designerMarkerDot(vals, markerList[markerRow]));
      }

      if (!hideAll) {
        const counts = el("span", "osw-sbprev-counts");
        const countRoles = ["new", "learn", "review"];
        deck.counts.forEach(function (count, slot) {
          if (count === 0 && hideZero) return;
          const role = countRoles[slot];
          const colors = designerSidebarCountColors(vals, role, isDark);
          const badge = el("span", "osw-sbprev-badge " + role + "-count-bubble", String(count));
          if (count === 0) badge.classList.add("zero");
          badge.style.fontSize = badgeFont + "px";
          badge.style.fontFamily = mainRole.family;
          badge.style.setProperty("--overview-" + role + "-bubble-bg", colors.bg);
          badge.style.setProperty("--overview-" + role + "-count-fg", colors.fg);
          badge.style.setProperty("--" + role + "-count-bubble-bg", colors.bg);
          badge.style.setProperty("--" + role + "-count-bubble-fg", colors.fg);
          counts.appendChild(badge);
        });
        row.appendChild(counts);
      }

      list.appendChild(row);
    });
    host.appendChild(list);
  }

  /* Build the same four reorderable blocks as the real Classic sidebar. The
     whole native-width frame is scaled by designerSidebarFrame, so proportions
     remain identical instead of being independently miniaturized. */
  function paintSidebarStack(stage, vals, isDark, markerList) {
    const built = designerSidebarFrame(stage, vals, isDark);
    designerSidebarSectionOrder(vals).forEach(function (sectionId) {
      const section = el("div", "osw-sbprev-section osw-sbprev-section-" + sectionId);
      if (sectionId === "profile") {
        if (!vals["modern_menu_hide_profile_bar"]) {
          designerSidebarProfile(section, vals, built.spec);
        }
      } else if (sectionId === "actions") {
        designerSidebarActions(
          section, vals, built.spec, vals["sidebarActionsMode"] || "list"
        );
      } else if (sectionId === "ready_to_go") {
        designerSidebarReady(section, vals, built.spec, isDark);
      } else if (sectionId === "decks") {
        designerDeckRows(section, vals, built.spec, isDark, markerList);
      }
      if (section.childNodes.length) built.content.appendChild(section);
    });
    designerCenteredWidgetPlaceholders(stage, built);
    return built;
  }

  /* Shima's Sidebar tab previews the actual composition: the shared main-menu
     backdrop with one compact island centered on it. The island keeps the
     Sidebar surface controls, but no profile, action strip, Ready to Go block,
     or other sidebar module. Hidden actions remain available from Home. */
  function paintShimaDeckIsland(stage, vals, isDark) {
    stage.innerHTML = "";
    stage.style.padding = "0";
    designerPaintBackdrop(stage, vals, isDark);

    const spec = designerSidebarSpec(vals, isDark);
    const island = el("div", "osw-sbprev-frame is-shima");
    island.style.borderRadius = spec.radius + "px";
    island.style.border = spec.stroke + "px solid " + spec.borderColor;
    island.style.setProperty("--osw-sbprev-inner-radius", Math.max(0, spec.radius - spec.stroke) + "px");

    const fill = el("div", "osw-sbprev-fill");
    fill.style.background = spec.color;
    if (spec.bgMode === "custom") {
      fill.style.opacity = String(Math.max(0, Math.min(100, spec.opacity)) / 100);
    }
    if (spec.backdropBlur) {
      fill.style.backdropFilter = "blur(" + spec.backdropBlur.toFixed(1) + "px)";
      fill.style.webkitBackdropFilter = fill.style.backdropFilter;
    }
    island.appendChild(fill);

    const url = spec.image ? imageUrl("sidebar_bg", spec.image) : "";
    if (url) {
      const img = el("div", "osw-sbprev-fill osw-sbprev-image");
      img.style.backgroundImage = "url(\"" + url.replace(/\"/g, "") + "\")";
      img.style.filter = spec.blur > 0 ? "blur(" + spec.blur.toFixed(1) + "px)" : "";
      img.style.opacity = String(Math.max(0, Math.min(100, spec.opacity)) / 100);
      island.appendChild(img);
    }

    const content = el("div", "osw-sbprev-content");
    const decks = el("div", "osw-sbprev-section osw-sbprev-section-decks");
    designerDeckRows(decks, vals, spec, isDark);
    content.appendChild(decks);
    island.appendChild(content);
    stage.appendChild(island);
  }

  function paintThemeSidebar(stage, vals, isDark) {
    if (vals.onigiri_ui_theme === "shima") {
      paintShimaDeckIsland(stage, vals, isDark);
      return;
    }
    paintSidebarStack(stage, vals, isDark);
  }

  PREVIEW_PAINTERS.sidebar_background = paintThemeSidebar;
  PREVIEW_PAINTERS.sidebar_actions = paintThemeSidebar;
  PREVIEW_PAINTERS.sidebar_ready = paintThemeSidebar;

  // One sidebar, one preview: all three cards show the whole thing, so switching
  // tabs never changes what is on the stage — only which controls sit beside it.
  PREVIEW_PAINTERS.deck_list = function (stage, vals, isDark) {
    paintThemeSidebar(stage, vals, isDark);
  };

  // ── Phase 6: Organize (widget grid editor) ────────────────────────────────
  //
  // Ported from settings/_widget_grid_core.py (generic canvas engine) +
  // _widget_grid_v2.py (Main-menu catalogue/glue). Persists via debounced
  // auto-patch on every atomic action rather than legacy's batch-at-Save —
  // see the plan's Architecture §5: this system has no dialog-level Save step
  // for anything else to hang batching off of.

  function organizeClamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function organizeClampSpan(raw, spec, isRow) {
    const minSpan = (spec && spec.minSpan) || [1, 1];
    const maxSpan = (spec && spec.maxSpan) || [4, 4];
    const defaultSpan = (spec && spec.defaultSpan) || (spec && spec.kind === "onigiri" ? [1, 1] : [2, 1]);
    const mn = isRow ? minSpan[0] : minSpan[1];
    const mx = isRow ? maxSpan[0] : maxSpan[1];
    let v = Number(raw);
    if (isNaN(v)) v = isRow ? defaultSpan[0] : defaultSpan[1];
    if (isRow && spec && spec.fixedRows) v = spec.fixedRows;
    return organizeClamp(v, mn, mx);
  }

  // excludeWid is either a single wid (string) or a {wid: true, ...} map, so a
  // multi-tile drag can exclude the whole dragged group in one pass.
  function organizeCellsFree(tiles, row, col, rowSpan, colSpan, cols, excludeWid) {
    if (row < 0 || col < 0 || col + colSpan > cols) return false;
    const excludeMap = excludeWid && typeof excludeWid === "object" ? excludeWid : null;
    for (let i = 0; i < tiles.length; i += 1) {
      const t = tiles[i];
      if (excludeMap ? excludeMap[t.wid] : t.wid === excludeWid) continue;
      if (row < t.row + t.rowSpan && row + rowSpan > t.row && col < t.col + t.colSpan && col + colSpan > t.col) return false;
    }
    return true;
  }

  function organizeFindFreeSlot(tiles, rowSpan, colSpan, cols, excludeWid) {
    for (let r = 0; r < 200; r += 1) {
      for (let c = 0; c <= cols - colSpan; c += 1) {
        if (organizeCellsFree(tiles, r, c, rowSpan, colSpan, cols, excludeWid)) return { row: r, col: c };
      }
    }
    return { row: 0, col: 0 };
  }

  const ORGANIZE_DEFAULT_LAYOUT = ["stats_title", "studied", "time", "pace", "retention", "heatmap"];

  function organizeTileInnerRadius(width, height, radius, border) {
    // CSS scales uniform corner radii down to half the shortest tile side.
    return Math.max(0, Math.min(radius, width / 2, height / 2) - border);
  }

  function organizeRemoveIconOffset(radius) {
    const outer = Math.min(16, Math.max(0, radius - 4));
    const inner = Math.min(6, outer, 18 - outer);
    const bottomLeft = Math.min(6, outer);
    // Find the centroid of the button's visible area: each rounded corner
    // removes a square minus a quarter-circle. Equal top-left/bottom-right
    // corners cancel, so the remaining correction is diagonal.
    const cutout = 1 - Math.PI / 4;
    const cutoutCenter = (5 / 6 - Math.PI / 4) / cutout;
    const area = 18 * 18 - cutout *
      (2 * inner * inner + outer * outer + bottomLeft * bottomLeft);
    return cutout * (outer * outer * (9 - cutoutCenter * outer) -
      bottomLeft * bottomLeft * (9 - cutoutCenter * bottomLeft)) / area;
  }

  function renderWidgetGrid(section) {
    const F_ONI = "onigiriWidgetLayout";
    const F_EXT = "externalWidgetLayout";
    const F_ROWS = "unifiedGridRows";

    function syncTileRemoveRadius(tile) {
      if (!tile.isConnected || !tile.offsetWidth || !tile.offsetHeight) return;
      const style = window.getComputedStyle(tile);
      const radius = organizeTileInnerRadius(
        tile.offsetWidth, tile.offsetHeight,
        parseFloat(style.borderTopRightRadius) || 0,
        parseFloat(style.borderTopWidth) || 0
      );
      tile.style.setProperty("--osw-organize-tile-inner-radius", radius + "px");
      tile.style.setProperty("--osw-remove-icon-offset", organizeRemoveIconOffset(radius) + "px");
    }
    const tileRadiusObserver = window.ResizeObserver
      ? new ResizeObserver(function (entries) {
        entries.forEach(function (entry) { syncTileRemoveRadius(entry.target); });
      }) : null;
    widgetGridTileRadiusObserver = tileRadiusObserver;

    const catalogue = CTX.organizeCatalogue || { onigiri: [], external: [] };
    const specsByWid = {};
    catalogue.onigiri.forEach(function (o) { specsByWid[o.wid] = Object.assign({ kind: "onigiri" }, o); });
    catalogue.external.forEach(function (o) { specsByWid[o.wid] = Object.assign({}, o); });

    // Deck Stats is intentionally repeatable. Its copies retain the base
    // widget's sizing rules but use a distinct ID, so the dashboard can store
    // each copy's selected deck and chart view independently.
    function isDeckStatsInstanceWid(wid) {
      return /^deck_stats(?:_[1-9]\d*)?$/.test(String(wid || ""));
    }
    function isRepeatableSpec(spec) {
      // Keep the ID check as the compatibility path for an already-running
      // Anki process: its Python context may predate `multiInstance`, while
      // this freshly loaded settings.js already knows Deck Stats is repeatable.
      return !!spec && (spec.multiInstance || spec.wid === "deck_stats");
    }
    function specForWid(wid) {
      if (specsByWid[wid]) return specsByWid[wid];
      if (isDeckStatsInstanceWid(wid) && specsByWid.deck_stats) {
        return Object.assign({}, specsByWid.deck_stats, { wid: wid });
      }
      return null;
    }
    function nextDeckStatsInstanceWid() {
      const used = {};
      state.tiles.forEach(function (tile) { used[tile.wid] = true; });
      if (!used.deck_stats) return "deck_stats";
      for (let n = 2; n < 1000; n += 1) {
        const wid = "deck_stats_" + n;
        if (!used[wid]) return wid;
      }
      return "deck_stats_" + Date.now();
    }

    const state = { cols: 4, minRows: 6, alignment: "center", gridWidth: 250, widgetHeight: 150, tiles: [] };

    function loadFromValues() {
      const oni = values[F_ONI] || {};
      const ext = values[F_EXT] || {};
      state.cols = organizeClamp(Number(oni.column_count) || 4, 1, 60);
      state.gridWidth = organizeClamp(Number(oni.grid_width) || 250, 200, 340);
      state.alignment = oni.grid_alignment || "center";
      state.widgetHeight = organizeClamp(Number(oni.widget_height) || 150, 120, 320);
      state.minRows = organizeClamp(Number(values[F_ROWS]) || 6, 1, 60);
      state.tiles = [];
      const oniGrid = oni.grid || {};
      Object.keys(oniGrid).forEach(function (wid) {
        const spec = specForWid(wid);
        if (!spec) return;
        const cfg = oniGrid[wid] || {};
        const pos = Number(cfg.pos) || 0;
        state.tiles.push({
          wid: wid, row: Math.floor(pos / state.cols), col: pos % state.cols,
          rowSpan: organizeClampSpan(cfg.row, spec, true), colSpan: organizeClampSpan(cfg.col, spec, false),
          displayName: wid === "stats_title" ? spec.name : (cfg.display_name || spec.name),
          orientation: cfg.orientation || "horizontal",
          design: cfg.design === "circles" ? "circles" : "squares"
        });
      });
      // Tolerates the legacy flat form (no {grid,archive} wrapper).
      const extGrid = (ext && ext.grid) ? ext.grid : (ext && !ext.archive ? ext : {});
      Object.keys(extGrid || {}).forEach(function (wid) {
        const spec = specForWid(wid);
        if (!spec) return;
        const cfg = extGrid[wid] || {};
        const pos = Number(cfg.grid_position) || 0;
        state.tiles.push({
          wid: wid, row: Math.floor(pos / state.cols), col: pos % state.cols,
          rowSpan: organizeClampSpan(cfg.row_span, spec, true), colSpan: organizeClampSpan(cfg.column_span, spec, false),
          displayName: cfg.display_name || spec.name
        });
      });
    }

    function commitLayout() {
      const effectiveRows = state.tiles.reduce(function (m, t) { return Math.max(m, t.row + t.rowSpan); }, state.minRows);
      const oniGrid = {};
      const extGrid = {};
      state.tiles.forEach(function (t) {
        const spec = specForWid(t.wid);
        if (!spec) return;
        const pos = t.row * state.cols + t.col;
        if (spec.kind === "onigiri") {
          const entry = { pos: pos, row: t.rowSpan, col: t.colSpan, display_name: t.displayName };
          if (t.wid === "restaurant_level") entry.orientation = t.orientation || "horizontal";
          if (t.wid === "ready_to_go") entry.design = t.design || "squares";
          oniGrid[t.wid] = entry;
        } else {
          extGrid[t.wid] = { grid_position: pos, row_span: Math.max(2, t.rowSpan), column_span: t.colSpan, display_name: t.displayName };
        }
      });
      const oniArchive = {};
      catalogue.onigiri.forEach(function (o) { if (!oniGrid[o.wid]) oniArchive[o.wid] = { display_name: o.name }; });
      const extArchive = {};
      catalogue.external.forEach(function (o) { if (!extGrid[o.wid]) extArchive[o.wid] = { display_name: o.name }; });

      setValue(F_ONI, {
        grid: oniGrid, archive: oniArchive, column_count: state.cols,
        grid_width: state.gridWidth, grid_alignment: state.alignment, widget_height: state.widgetHeight
      }, { debounce: true });
      setValue(F_EXT, { grid: extGrid, archive: extArchive }, { debounce: true });
      setValue(F_ROWS, effectiveRows, { debounce: true });
    }

    loadFromValues();

    // Multi-select: Shift+Click toggles a tile in/out without starting a
    // drag; dragging any tile that's still selected then carries the whole
    // set together, keeping every tile's offset from the one under the
    // pointer. Keyed by wid so it survives a renderCanvas() rebuild.
    let selectedWids = new Set();

    function clearSelection() {
      if (!selectedWids.size) return;
      selectedWids.clear();
      renderCanvas();
    }

    function toggleSelection(wid) {
      if (selectedWids.has(wid)) selectedWids.delete(wid); else selectedWids.add(wid);
      renderCanvas();
    }

    const wrap = el("div", "osw-organize-wrap");

    // ── live Main Menu preview ────────────────────────────────────────────
    // The editor still owns the layout; this skin only changes how its canvas
    // is painted. That keeps placement, multi-select and resize interactions
    // faithful while making the thing being arranged look like the menu it
    // will become.
    const WIDGET_DYNAMIC_KEY = "onigiri_canvas_inset_color_theme_mode";
    let previewMode = CTX.dark ? "dark" : "light";
    let canvas = null;
    let displayedMenuBackground = null;

    function widgetPreviewDynamicOn() {
      return values[WIDGET_DYNAMIC_KEY] === "separate";
    }

    function widgetPreviewIsDark() {
      return widgetPreviewDynamicOn() && previewMode === "dark";
    }

    function widgetPreviewValue(fieldId, fallback) {
      const value = values[fieldId];
      return value === undefined || value === null || value === "" ? fallback : value;
    }

    function paintWidgetGridPreview() {
      // Paint during construction too: the initial canvas is still detached
      // when renderCanvas runs, and must already have its background on mount.
      if (!canvas) return false;
      syncPreviewControls();
      const isDark = widgetPreviewIsDark();
      const boxColor = designerPairValue(
        values, "widget_box_color_light", "widget_box_color_dark",
        WIDGET_DYNAMIC_KEY, isDark
      ) || (isDark ? "#2c2c2c" : "#ffffff");
      const borderColor = designerPairValue(
        values, "widget_border_color_light", "widget_border_color_dark",
        WIDGET_DYNAMIC_KEY, isDark
      ) || (isDark ? "#424242" : "#e0e0e0");
      const glass = designerGlassCardStyle(
        values, isDark, "onigiri_canvas_inset_effect_opacity",
        "onigiri_canvas_inset_effect_blur", "onigiri_canvas_inset_border_radius",
        "onigiri_canvas_inset_border_width", boxColor, borderColor
      );
      const textRole = designerFontRole(values, "widget_small", isDark, "main");
      const previewText = textRole.color || (isDark ? "#f4f4f5" : "#202124");

      canvas.classList.toggle("is-dark", isDark);
      canvas.style.setProperty("--osw-organize-preview-card-bg", glass.background);
      canvas.style.setProperty("--osw-organize-preview-card-border", glass.border);
      canvas.style.setProperty("--osw-organize-preview-card-radius", glass.borderRadius);
      canvas.querySelectorAll(".osw-organize-tile").forEach(syncTileRemoveRadius);
      canvas.style.setProperty("--osw-organize-preview-card-blur", glass.backdropFilter || "none");
      canvas.style.setProperty("--osw-organize-preview-text-font", textRole.family || "inherit");
      canvas.style.setProperty("--osw-organize-preview-text", previewText);

      const titleTile = canvas.querySelector('[data-wid="stats_title"]');
      if (titleTile) {
        const enabled = !!values.modern_menu_title_background_enabled;
        titleTile.classList.add("is-menu-title-tile");
        titleTile.classList.toggle("has-title-background", enabled);
        titleTile.style.borderRadius = glass.borderRadius;
        titleTile.style.border = enabled ? glass.border : "0 solid transparent";
        syncTileRemoveRadius(titleTile);
        titleTile.setAttribute("aria-label", str("menu_title", "Menu Title"));
        let background = titleTile.querySelector(".osw-organize-title-background");
        if (!background) {
          background = el("div", "osw-organize-title-background");
          titleTile.insertBefore(background, titleTile.firstChild);
        }
        background.hidden = !enabled;
        const kind = values.modern_menu_title_background_type || "color";
        const blur = organizeClamp(Number(values.modern_menu_title_background_blur) || 0, 0, 40);
        const opacity = values.modern_menu_title_background_opacity;
        const tintOpacity = organizeClamp(opacity == null ? 100 : Number(opacity), 0, 100);
        // Keep backdrop blur visible through a translucent tint, rather than
        // fading an opaque fill together with the already-covered backdrop.
        background.style.opacity = kind === "color" ? 1 : tintOpacity / 100;
        background.style.backgroundColor = kind === "color"
          ? "color-mix(in srgb, " + (values.modern_menu_title_background_color || "#FFFFFF") + " " + tintOpacity + "%, transparent)"
          : "transparent";
        const url = kind === "image" ? imageUrl("main_bg", values.modern_menu_title_background_image) : "";
        background.style.backgroundImage = url ? 'url("' + url + '")' : "none";
        background.style.filter = kind === "image" ? "blur(" + blur + "px)" : "none";
        background.style.backdropFilter = kind === "color" ? "blur(" + blur + "px)" : "none";
        background.style.webkitBackdropFilter = background.style.backdropFilter;
        if (values.modern_menu_title_sync_widgets) {
          background.style.opacity = 1;
          background.style.backgroundColor = glass.background;
          background.style.backgroundImage = "none";
          background.style.filter = "none";
          background.style.backdropFilter = glass.backdropFilter || "none";
          background.style.webkitBackdropFilter = background.style.backdropFilter;
        }
        const phrase = titleTile.querySelector(".osw-organize-tile-name");
        const text = values.modern_menu_statsTitle;
        phrase.textContent = text == null ? ((fieldById.modern_menu_statsTitle || {}).default || "") : String(text);
        phrase.hidden = !phrase.textContent.trim();
        const alignment = values.modern_menu_title_alignment || "left";
        phrase.style.textAlign = ["left", "center", "right"].indexOf(alignment) >= 0 ? alignment : "left";
        const titleFont = designerFontRole(values, "dashboard_title", isDark, "subtle");
        phrase.style.fontFamily = titleFont.family || "inherit";
        phrase.style.color = titleFont.color || previewText;
        phrase.style.fontSize = Math.max(8, Math.min(72, Number(values.onigiri_font_size_dashboard_title) || 20)) * 0.6 + "px";
      }

      const backdrop = canvas.querySelector(".osw-organize-preview-backdrop");
      if (!backdrop) return true;
      // Resolve the background for the theme selected in the grid, so the
      // theme button changes both the widgets and their surrounding canvas.
      const backgroundIsDark = isDark;
      const color = values[backgroundIsDark ? MAIN_BG_KEYS.colorDark : MAIN_BG_KEYS.colorLight]
        || (backgroundIsDark ? "#2c2c2c" : "#eeeeee");
      const colorLayer = backdrop.querySelector(".osw-organize-preview-color");
      const imageLayer = backdrop.querySelector(".osw-organize-preview-image");
      if (colorLayer) colorLayer.style.background = color;

      const backgroundMode = values[MAIN_BG_KEYS.mode] || "color";
      let imageName = "";
      if (backgroundMode === "slideshow") {
        const images = Array.isArray(values[MAIN_BG_KEYS.slideshowImages])
          ? values[MAIN_BG_KEYS.slideshowImages] : [];
        imageName = images[0] || "";
      } else if (backgroundMode !== "color") {
        // Match config.themed_asset: themed slot then shared slot in Dynamic
        // Mode; shared, current theme, then opposite theme in single mode.
        const rawMode = values[MAIN_BG_KEYS.imageThemeMode] !== undefined
          ? values[MAIN_BG_KEYS.imageThemeMode] : values.modern_menu_background_image_mode;
        const imageDynamic = rawMode === undefined || (
          typeof rawMode === "string"
            ? ["single", "shared", "linked", "false", "off", "0"].indexOf(rawMode.toLowerCase()) === -1
            : !!rawMode
        );
        const shared = values[MAIN_BG_KEYS.imageBase] || "";
        const current = values[backgroundIsDark ? MAIN_BG_KEYS.imageDark : MAIN_BG_KEYS.imageLight] || "";
        const other = values[backgroundIsDark ? MAIN_BG_KEYS.imageLight : MAIN_BG_KEYS.imageDark] || "";
        imageName = imageDynamic ? (current || shared) : (shared || current || other);
      }
      const image = imageName && imageUrl(MAIN_BG_KEYS.imageFolder, imageName);
      if (imageLayer) {
        imageLayer.style.backgroundImage = image ? 'url("' + image.replace(/"/g, "") + '")' : "none";
        imageLayer.style.opacity = String(Math.max(0, Math.min(100,
          Number(widgetPreviewValue(MAIN_BG_KEYS.opacity, 100)))) / 100);
        const blur = Math.max(0, Number(widgetPreviewValue(MAIN_BG_KEYS.blur, 0)));
        const blurPx = blur * 0.2;
        imageLayer.style.filter = blurPx ? "blur(" + blurPx.toFixed(1) + "px)" : "none";
        imageLayer.style.transform = "scale(" + (1 + blurPx / 50) + ")";
      }
      // Use the real menu's rendered colours/images only when its theme
      // matches the selected grid theme. Slideshow frames are shared between
      // themes, so keep their image/fade synchronized in either grid mode.
      const nextLayer = backdrop.querySelector(".osw-organize-preview-next-image");
      if (nextLayer) nextLayer.style.backgroundImage = "none";
      if (displayedMenuBackground) {
        const menuIsDark = typeof displayedMenuBackground.dark === "boolean"
          ? displayedMenuBackground.dark : !!CTX.dark;
        const matchesTheme = menuIsDark === backgroundIsDark;
        if (matchesTheme && colorLayer) colorLayer.style.background = displayedMenuBackground.color;
        function copyLayer(node, layer) {
          if (!node || !layer) return;
          node.style.backgroundImage = layer.image || "none";
          node.style.backgroundPosition = layer.position || "center";
          node.style.backgroundSize = layer.size || "cover";
          node.style.opacity = layer.opacity;
          node.style.filter = layer.filter || "none";
          node.style.transform = "scale(" + (Number(layer.scale) || 1) + ")";
        }
        if (matchesTheme || backgroundMode === "slideshow") {
          copyLayer(imageLayer, displayedMenuBackground.base);
          copyLayer(nextLayer, displayedMenuBackground.next);
        }
      }
      return true;
    }

    const previewCard = el("div", "osw-organize-preview-card");
    const previewHead = el("div", "osw-designer-preview-head osw-organize-preview-head");
    previewHead.appendChild(el("div", "osw-designer-preview-title",
      str("widget_grid", "Widget grid")));
    const previewControls = el("div", "osw-preview-head-controls");
    const dynamicCtl = el("div", "osw-preview-ctl");
    dynamicCtl.appendChild(el("span", "osw-preview-ctl-label", str("dynamic_mode", "Dynamic mode")));
    const dynamicBtn = el("button", "osw-sq-switch-btn");
    dynamicBtn.type = "button";
    dynamicBtn.setAttribute("aria-label", str("dynamic_mode", "Dynamic mode"));
    const dynamicTrack = el("div", "osw-sq-switch" + (widgetPreviewDynamicOn() ? " is-on" : ""));
    dynamicBtn.appendChild(dynamicTrack);
    dynamicBtn.addEventListener("click", function () {
      bridge("osw:haptic:1");
      const next = !widgetPreviewDynamicOn();
      setValue(WIDGET_DYNAMIC_KEY, next ? "separate" : "single");
      if (!next) previewMode = "light";
      dynamicTrack.classList.toggle("is-on", next);
      dynamicBtn.setAttribute("aria-pressed", next ? "true" : "false");
      refreshPairFields();
      paintWidgetGridPreview();
      syncPreviewControls();
    });
    dynamicCtl.appendChild(dynamicBtn);
    previewControls.appendChild(dynamicCtl);

    const previewThemeBtn = el("button", "osw-profile-preview-toggle-btn osw-designer-preview-toggle-btn");
    previewThemeBtn.type = "button";
    function syncPreviewControls() {
      const isDark = widgetPreviewIsDark();
      previewThemeBtn.innerHTML = isDark ? OSW_SUN_ICON : OSW_MOON_ICON;
      previewThemeBtn.title = isDark ? str("light_mode", "Light") : str("dark_mode", "Dark");
      previewThemeBtn.disabled = !widgetPreviewDynamicOn();
      dynamicTrack.classList.toggle("is-on", widgetPreviewDynamicOn());
      dynamicBtn.setAttribute("aria-pressed", widgetPreviewDynamicOn() ? "true" : "false");
    }
    previewThemeBtn.addEventListener("click", function () {
      if (!widgetPreviewDynamicOn()) return;
      previewMode = previewMode === "dark" ? "light" : "dark";
      syncPreviewControls();
      paintWidgetGridPreview();
    });

    const resetLabel = str("reset", "Reset");
    const previewResetBtn = el("button", "osw-btn osw-designer-reset");
    previewResetBtn.type = "button";
    previewResetBtn.title = str("reset_widget_appearance", "Reset widget appearance");
    previewResetBtn.appendChild(el("span", "osw-designer-reset-label", resetLabel));
    const resetIcon = el("span", "osw-designer-reset-icon");
    resetIcon.innerHTML = OSW_RESET_ICON;
    previewResetBtn.appendChild(resetIcon);
    installResetHold(previewResetBtn, function () {
      [
        "onigiri_canvas_inset_effect_blur", "onigiri_canvas_inset_effect_opacity",
        "onigiri_canvas_inset_border_radius", "onigiri_canvas_inset_border_width",
        "widget_box_color_light", "widget_box_color_dark",
        "widget_border_color_light", "widget_border_color_dark", WIDGET_DYNAMIC_KEY
      ].forEach(function (fieldId) {
        const field = fieldById[fieldId];
        if (field && field.default !== undefined) {
          setValue(fieldId, field.default, { silent: true, keepDom: true });
        }
      });
      previewMode = "light";
      refreshSettingsPreviews();
      syncPreviewControls();
    }, { title: str("reset_widget_appearance", "Reset widget appearance") });
    const utility = el("div", "osw-preview-utility-ctl");
    utility.appendChild(previewThemeBtn);
    utility.appendChild(previewResetBtn);
    const infoBtn = el("button", "osw-organize-font-info osw-organize-grid-info");
    infoBtn.type = "button";
    infoBtn.innerHTML = ICON_INFO;
    infoBtn.title = str("organize_grid_help_title", "Arrange your widgets");
    infoBtn.setAttribute("aria-label", infoBtn.title);
    infoBtn.setAttribute("aria-haspopup", "dialog");
    infoBtn.addEventListener("click", openWidgetGridHelp);
    utility.appendChild(infoBtn);
    previewControls.appendChild(utility);
    previewHead.appendChild(previewControls);
    previewCard.appendChild(previewHead);
    syncPreviewControls();

    function openWidgetGridHelp() {
      bridge("osw:haptic:1");
      const overlay = el("div", "osw-gal osw-organize-help");
      const card = el("div", "osw-gal-card osw-organize-help-card");
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-modal", "true");
      card.setAttribute("aria-labelledby", "oswWidgetGridHelpTitle");
      card.setAttribute("aria-describedby", "oswWidgetGridHelpBody");
      const head = el("div", "osw-gal-head");
      const title = el("div", "osw-gal-title", infoBtn.title);
      title.id = "oswWidgetGridHelpTitle";
      head.appendChild(title);
      const closeBtn = el("button", "osw-gal-close");
      closeBtn.type = "button";
      closeBtn.setAttribute("aria-label", str("close", "Close"));
      closeBtn.innerHTML = ICON_CLOSE;
      closeBtn.addEventListener("click", close);
      head.appendChild(closeBtn);
      card.appendChild(head);
      const body = el("div", "osw-organize-help-body");
      body.id = "oswWidgetGridHelpBody";
      body.appendChild(el("p", "", str("organize_grid_drag_help",
        "Drag and drop widgets in the grid to arrange your Main Menu.")));
      body.appendChild(el("p", "", str("organize_grid_multiselect_help",
        "Shift+Click widgets to select several, then drag one to move them together.")));
      card.appendChild(body);
      overlay.appendChild(card);
      overlay.addEventListener("click", function (event) {
        if (event.target === overlay) close();
      });
      function close() {
        document.removeEventListener("keydown", onKey, true);
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        if (infoBtn.isConnected) infoBtn.focus();
      }
      function onKey(event) {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopImmediatePropagation();
          close();
        } else if (event.key === "Tab") {
          // The close button is this informational dialog's only control.
          event.preventDefault();
          closeBtn.focus();
        }
      }
      document.body.appendChild(overlay);
      document.addEventListener("keydown", onKey, true);
      closeBtn.focus();
    }

    // ── global controls ──
    // Two clusters on one bar: the grid's own numbers/alignment on the left,
    // the two actions on the right — instead of one wrapping run of chips.
    // Row 1 is the grid's numbers, row 2 pairs alignment with the actions —
    // four short chips then one wide control, instead of a run that wraps
    // wherever the labels happen to run out of room.
    const controls = el("div", "osw-organize-controls");
    const controlGroup = el("div", "osw-organize-group");
    const controlBottom = el("div", "osw-organize-row");
    const controlActions = el("div", "osw-organize-actions");
    function numberControl(labelText, value, min, max, onChange, suffix) {
      const row = el("div", "osw-organize-ctl");
      row.appendChild(el("span", "osw-organize-ctl-label", labelText));
      const box = el("div", "osw-organize-ctl-box");
      const input = document.createElement("input");
      input.type = "number";
      input.className = "osw-organize-ctl-input";
      input.min = min; input.max = max; input.value = value;
      input.addEventListener("change", function () {
        const v = organizeClamp(parseInt(input.value, 10) || min, min, max);
        input.value = v;
        onChange(v);
      });
      box.appendChild(input);
      // The unit belongs to the value, not to the label — keeps the chip short
      // enough for the whole bar to stay on one line.
      if (suffix) box.appendChild(el("span", "osw-organize-ctl-suffix", suffix));
      row.appendChild(box);
      return row;
    }
    controlGroup.appendChild(numberControl(str("columns", "Columns"), state.cols, 1, 60, function (v) {
      state.cols = v;
      state.tiles.forEach(function (t) {
        if (t.col + t.colSpan > state.cols) t.col = Math.max(0, state.cols - t.colSpan);
      });
      resolveAllOverlaps();
      renderCanvas();
      commitLayout();
    }));
    controlGroup.appendChild(numberControl(str("rows", "Rows"), state.minRows, 1, 60, function (v) {
      state.minRows = v;
      renderCanvas();
      commitLayout();
    }));
    const alignRow = el("div", "osw-organize-ctl");
    alignRow.setAttribute("data-simple-organize-advanced", "true");
    alignRow.appendChild(el("span", "osw-organize-ctl-label", str("grid_alignment", "Grid Alignment")));
    const alignSeg = el("div", "osw-segmented-control osw-organize-seg");
    [["left", str("align_left", "Left")], ["center", str("align_center", "Center")], ["right", str("align_right", "Right")]].forEach(function (opt) {
      const btn = el("div", "osw-segment-btn" + (state.alignment === opt[0] ? " is-active" : ""), opt[1]);
      btn.addEventListener("click", function () {
        state.alignment = opt[0];
        Array.prototype.forEach.call(alignSeg.querySelectorAll(".osw-segment-btn"), function (b) { b.classList.remove("is-active"); });
        btn.classList.add("is-active");
        commitLayout();
      });
      alignSeg.appendChild(btn);
    });
    alignRow.appendChild(alignSeg);
    controlBottom.appendChild(alignRow);
    const widgetHeightControl = numberControl(str("widget_height", "Widget Height"), state.widgetHeight, 120, 320, function (v) {
      state.widgetHeight = v; commitLayout();
    }, "px");
    widgetHeightControl.setAttribute("data-simple-organize-advanced", "true");
    controlGroup.appendChild(widgetHeightControl);
    const gridWidthControl = numberControl(str("grid_width", "Grid Width"), state.gridWidth, 200, 340, function (v) {
      state.gridWidth = v; commitLayout();
    }, "px");
    gridWidthControl.setAttribute("data-simple-organize-advanced", "true");
    controlGroup.appendChild(gridWidthControl);

    // Hold-to-reset — reuses the exact hold-fill mechanic already built for
    // Profile's reset button (.osw-profile-reset-btn / is-holding / is-ready).
    const resetBtn = el("button", "osw-profile-reset-btn osw-organize-reset-btn");
    resetBtn.type = "button";
    resetBtn.appendChild(el("span", "osw-profile-reset-btn-text", str("restore_default", "Hold to Reset")));
    installResetHold(resetBtn, resetGrid, {
      title: str("hold_to_reset_main_menu", "Hold for 3 seconds to reset Main Menu customizations")
    });
    controlActions.appendChild(resetBtn);

    // Widget Fonts uses the same small, focused popover as the former
    // organizer control: titles and widget text can follow the shared font
    // settings or be detached without opening a separate page.
    if ((SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && (section.fontRoles || []).length) {
      controlActions.appendChild(compactFontMenuButton(section));
    }

    const addBtn = el("button", "osw-action-btn osw-organize-add-btn");
    addBtn.type = "button";
    const addIcon = el("span", "osw-action-btn-icon");
    addIcon.innerHTML = ICON_PLUS;
    addBtn.appendChild(addIcon);
    addBtn.appendChild(el("span", "osw-action-btn-label", str("add_widget", "Add Widget")));
    addBtn.addEventListener("click", openWidgetGallery);
    controlActions.appendChild(addBtn);

    controlBottom.appendChild(controlActions);
    controls.appendChild(controlGroup);
    controls.appendChild(controlBottom);
    wrap.appendChild(controls);

    // Widget placement belongs with the grid it changes.  The presets patch
    // the legacy per-edge values through the schema cascade; Custom is the
    // only mode that needs to show those precise controls.
    const layoutControls = renderWidgetLayoutControls(section);
    if (layoutControls) {
      layoutControls.setAttribute("data-simple-organize-advanced", "true");
      wrap.appendChild(layoutControls);
    }

    // Shared widget appearance belongs beside the grid it styles. Mount the
    // compact two-row panel after the toolbar and before the selection hint,
    // while its fields continue using the ordinary autosave renderers.
    const compactFieldIds = section.compactFields || [];
    if (compactFieldIds.length) {
      const compactSet = {};
      compactFieldIds.forEach(function (fieldId) { compactSet[fieldId] = true; });
      wrap.appendChild(renderCompactWidgetEffect({
        fields: (section.fields || []).filter(function (field) {
          return !!compactSet[field.id];
        })
      }));
    }

    const hint = el("div", "osw-organize-hint");
    wrap.appendChild(hint);

    function renderHint() {
      hint.innerHTML = "";
      hint.hidden = selectedWids.size <= 1;
      if (selectedWids.size > 1) {
        hint.classList.add("has-selection");
        hint.appendChild(el("span", "osw-organize-hint-text", selectedWids.size + " " +
          str("organize_widgets_selected", "widgets selected — drag any one to move them together")));
        const clearBtn = el("button", "osw-organize-hint-clear", str("organize_clear_selection", "Clear"));
        clearBtn.type = "button";
        clearBtn.addEventListener("click", clearSelection);
        hint.appendChild(clearBtn);
      } else {
        hint.classList.remove("has-selection");
      }
    }

    canvas = el("div", "osw-organize-canvas osw-organize-live-preview");
    canvas.addEventListener("pointerdown", function (event) {
      if (event.target === canvas || event.target.classList.contains("osw-organize-slot") ||
          event.target.closest(".osw-organize-preview-backdrop")) clearSelection();
    });
    previewCard.appendChild(canvas);
    wrap.appendChild(previewCard);

    function resolveAllOverlaps() {
      const placed = [];
      state.tiles.forEach(function (t) {
        if (organizeCellsFree(placed, t.row, t.col, t.rowSpan, t.colSpan, state.cols, t.wid)) {
          placed.push(t);
          return;
        }
        const slot = organizeFindFreeSlot(placed, t.rowSpan, t.colSpan, state.cols, t.wid);
        t.row = slot.row; t.col = slot.col;
        placed.push(t);
      });
    }

    function effectiveRows() {
      return state.tiles.reduce(function (m, t) { return Math.max(m, t.row + t.rowSpan); }, state.minRows);
    }

    function renderCanvas() {
      if (tileRadiusObserver) tileRadiusObserver.disconnect();
      canvas.innerHTML = "";
      const rows = effectiveRows();
      const rowHeightPx = Math.round(organizeClamp(state.widgetHeight * 0.42, 52, 96));
      canvas.style.gridTemplateColumns = "repeat(" + state.cols + ", 1fr)";
      canvas.style.gridTemplateRows = "repeat(" + rows + ", " + rowHeightPx + "px)";

      // Two separate layers reproduce the Main Background's composition:
      // the selected colour stays behind the image, and the image alone takes
      // the configured blur/opacity. They are deliberately stage-local so
      // dragging a widget never paints a second background over the controls.
      const backdrop = el("div", "osw-organize-preview-backdrop");
      backdrop.appendChild(el("div", "osw-organize-preview-color"));
      backdrop.appendChild(el("div", "osw-organize-preview-image"));
      backdrop.appendChild(el("div", "osw-organize-preview-image osw-organize-preview-next-image"));
      canvas.appendChild(backdrop);

      // Render grid slot placeholders for every cell in cols x rows
      for (let r = 0; r < rows; r += 1) {
        for (let c = 0; c < state.cols; c += 1) {
          // A transparent title still has one full widget footprint. Cell
          // guides inside it would make that footprint look like empty slots.
          const insideTitle = state.tiles.some(function (tile) {
            return tile.wid === "stats_title" && r >= tile.row && r < tile.row + tile.rowSpan &&
              c >= tile.col && c < tile.col + tile.colSpan;
          });
          if (insideTitle) continue;
          const slot = el("div", "osw-organize-slot");
          slot.style.gridColumn = (c + 1);
          slot.style.gridRow = (r + 1);
          canvas.appendChild(slot);
        }
      }

      state.tiles.forEach(function (t) {
        const spec = specForWid(t.wid);
        if (!spec) return;
        const tile = el("div", "osw-organize-tile" +
          (spec.kind !== "onigiri" ? " is-external" : "") +
          (selectedWids.has(t.wid) ? " is-selected" : ""));
        tile.setAttribute("data-wid", t.wid);
        tile.style.gridColumn = (t.col + 1) + " / span " + t.colSpan;
        tile.style.gridRow = (t.row + 1) + " / span " + t.rowSpan;
        tile.appendChild(el("span", "osw-organize-tile-name", t.displayName || spec.name));
        const removeBtn = el("button", "osw-organize-tile-remove");
        removeBtn.type = "button";
        removeBtn.innerHTML = ICON_CLOSE;
        removeBtn.addEventListener("click", function (event) {
          event.stopPropagation();
          state.tiles = state.tiles.filter(function (x) { return x !== t; });
          selectedWids.delete(t.wid);
          renderCanvas();
          commitLayout();
        });
        tile.appendChild(removeBtn);

        const minSpan = (spec && spec.minSpan) || [1, 1];
        const maxSpan = (spec && spec.maxSpan) || [4, 4];
        const canGrowEast = t.colSpan < Math.min(maxSpan[1], state.cols) &&
          organizeCellsFree(state.tiles, t.row, t.col, t.rowSpan, t.colSpan + 1, state.cols, t.wid);
        const canGrowSouth = !spec.fixedRows && t.rowSpan < maxSpan[0] &&
          organizeCellsFree(state.tiles, t.row, t.col, t.rowSpan + 1, t.colSpan, state.cols, t.wid);
        const canResizeEast = t.colSpan > minSpan[1] || canGrowEast;
        const canResizeSouth = !spec.fixedRows && (t.rowSpan > minSpan[0] || canGrowSouth);

        function addResizeHandle(kind) {
          const handle = el("button", "osw-organize-resize-handle is-" + kind);
          handle.type = "button";
          handle.title = str("drag_to_resize", "Drag to resize");
          tile.appendChild(handle);
          wireTileResize(handle, tile, t, spec, kind);
        }
        if (canResizeEast) addResizeHandle("east");
        if (canResizeSouth) addResizeHandle("south");
        if (canResizeEast && canResizeSouth) addResizeHandle("corner");

        wireTileDrag(tile, t);
        tile.addEventListener("contextmenu", function (event) {
          event.preventDefault();
          openTileMenu(t, spec, event.clientX, event.clientY);
        });

        canvas.appendChild(tile);
        if (tileRadiusObserver) tileRadiusObserver.observe(tile);
      });
      renderHint();
      paintWidgetGridPreview();
    }

    function wireTileResize(handle, tileEl, t, spec, kind) {
      let active = false;
      let startX = 0, startY = 0, cellW = 1, cellH = 1;
      let nextRows = t.rowSpan, nextCols = t.colSpan;
      const minSpan = (spec && spec.minSpan) || [1, 1];
      const maxSpan = (spec && spec.maxSpan) || [4, 4];

      handle.addEventListener("pointerdown", function (event) {
        event.preventDefault();
        event.stopPropagation();
        startX = event.clientX;
        startY = event.clientY;
        nextRows = t.rowSpan;
        nextCols = t.colSpan;
        const canvasRect = canvas.getBoundingClientRect();
        const style = window.getComputedStyle(canvas);
        const gapX = parseFloat(style.columnGap) || 0;
        const gapY = parseFloat(style.rowGap) || 0;
        const usableWidth = canvasRect.width - (parseFloat(style.paddingLeft) || 0) -
          (parseFloat(style.paddingRight) || 0) - gapX * (state.cols - 1);
        cellW = Math.max(1, usableWidth / state.cols + gapX);
        const rows = effectiveRows();
        const usableHeight = canvasRect.height - (parseFloat(style.paddingTop) || 0) -
          (parseFloat(style.paddingBottom) || 0) - gapY * Math.max(0, rows - 1);
        cellH = Math.max(1, usableHeight / rows + gapY);
        active = true;
        tileEl.classList.add("is-resizing");
        handle.setPointerCapture(event.pointerId);
      });

      handle.addEventListener("pointermove", function (event) {
        if (!active) return;
        let candidateRows = t.rowSpan;
        let candidateCols = t.colSpan;
        if (kind === "east" || kind === "corner") {
          candidateCols = organizeClamp(
            t.colSpan + Math.round((event.clientX - startX) / cellW),
            minSpan[1],
            Math.min(maxSpan[1], state.cols - t.col)
          );
        }
        if ((kind === "south" || kind === "corner") && !spec.fixedRows) {
          candidateRows = organizeClamp(
            t.rowSpan + Math.round((event.clientY - startY) / cellH),
            minSpan[0],
            maxSpan[0]
          );
        }
        if (!organizeCellsFree(
          state.tiles, t.row, t.col, candidateRows, candidateCols, state.cols, t.wid
        )) return;
        nextRows = candidateRows;
        nextCols = candidateCols;
        tileEl.style.gridColumn = (t.col + 1) + " / span " + nextCols;
        tileEl.style.gridRow = (t.row + 1) + " / span " + nextRows;
      });

      function finishResize() {
        if (!active) return;
        active = false;
        tileEl.classList.remove("is-resizing");
        if (nextRows !== t.rowSpan || nextCols !== t.colSpan) {
          t.rowSpan = nextRows;
          t.colSpan = nextCols;
          renderCanvas();
          commitLayout();
        } else {
          tileEl.style.gridColumn = (t.col + 1) + " / span " + t.colSpan;
          tileEl.style.gridRow = (t.row + 1) + " / span " + t.rowSpan;
        }
      }

      handle.addEventListener("pointerup", finishResize);
      handle.addEventListener("pointercancel", finishResize);
      handle.addEventListener("lostpointercapture", finishResize);
    }

    // A tile drags alone unless it's part of an active multi-selection with
    // more than one member, in which case every selected tile moves together,
    // each keeping its original offset from the one under the pointer. Either
    // way, a drop commits only if every cell every group tile would land on
    // is free (checked against tiles outside the group) — landing on an
    // occupied cell snaps the whole group back instead of displacing anyone.
    function wireTileDrag(tileEl, t) {
      let dragging = false;
      let moved = false;
      let modifierClick = false;
      let startX = 0, startY = 0, cellW = 0, cellH = 0;
      let canvasRect = null, tileStartRect = null, padLeft = 0, padRight = 0, padTop = 0, padBottom = 0;
      let groupTiles = [], deltaRow = 0, deltaCol = 0, dropValid = true, previews = [];

      function clearPreviews() {
        previews.forEach(function (p) { if (p.parentNode) p.parentNode.removeChild(p); });
        previews = [];
      }

      function updatePreviews() {
        clearPreviews();
        groupTiles.forEach(function (gt) {
          const p = el("div", "osw-organize-drop-preview" + (dropValid ? "" : " is-invalid"));
          p.style.gridColumn = (gt.col + deltaCol + 1) + " / span " + gt.colSpan;
          p.style.gridRow = (gt.row + deltaRow + 1) + " / span " + gt.rowSpan;
          canvas.appendChild(p);
          previews.push(p);
        });
      }

      tileEl.addEventListener("pointerdown", function (event) {
        if (event.target !== tileEl && event.target.closest(".osw-organize-tile-remove, .osw-organize-resize-handle")) return;
        event.preventDefault();

        // Shift+Click only ever toggles this tile's selection — it never
        // starts a drag, so building a selection is unambiguous even on a
        // trackpad that reads a small wiggle as movement. (Ctrl+Click isn't
        // used for this: macOS treats it as a right-click, which would fire
        // this tile's own context menu at the same time.)
        modifierClick = event.shiftKey;
        if (modifierClick) { dragging = false; return; }

        // Pressing a tile outside the current selection abandons it, same as
        // a plain click on empty canvas — only a still-selected tile carries
        // its group along.
        if (!selectedWids.has(t.wid)) clearSelection();

        startX = event.clientX; startY = event.clientY;
        moved = false;
        dropValid = true;
        deltaRow = 0; deltaCol = 0;
        groupTiles = (selectedWids.has(t.wid) && selectedWids.size > 1)
          ? state.tiles.filter(function (x) { return selectedWids.has(x.wid); })
          : [t];

        const rect = canvas.getBoundingClientRect();
        const canvasStyle = window.getComputedStyle(canvas);
        canvasRect = rect;
        tileStartRect = tileEl.getBoundingClientRect();
        padLeft = parseFloat(canvasStyle.paddingLeft) || 0;
        padRight = parseFloat(canvasStyle.paddingRight) || 0;
        padTop = parseFloat(canvasStyle.paddingTop) || 0;
        padBottom = parseFloat(canvasStyle.paddingBottom) || 0;
        const gap = parseFloat(canvasStyle.columnGap) || 0;
        const padX = padLeft + padRight;
        cellW = Math.max(1, (rect.width - padX - gap * (state.cols - 1)) / state.cols + gap);
        cellH = Math.max(1, tileEl.getBoundingClientRect().height / t.rowSpan + (parseFloat(canvasStyle.rowGap) || 0));
        dragging = true;
        tileEl.setPointerCapture(event.pointerId);
      });

      tileEl.addEventListener("pointermove", function (event) {
        if (!dragging) return;
        const dx = event.clientX - startX;
        const dy = event.clientY - startY;
        if (!moved && Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        moved = true;

        groupTiles.forEach(function (gt) {
          const node = canvas.querySelector('[data-wid="' + gt.wid + '"]');
          if (node) node.classList.add("is-dragging");
        });

        // Keep the carried tile inside the canvas' actual content box. The
        // target cell is clamped as well, so a release outside the grid can
        // never create a new row or place a widget beyond its edges.
        const minDx = canvasRect.left + padLeft - tileStartRect.left;
        const maxDx = canvasRect.right - padRight - tileStartRect.right;
        const minDy = canvasRect.top + padTop - tileStartRect.top;
        const maxDy = canvasRect.bottom - padBottom - tileStartRect.bottom;
        const dragDx = organizeClamp(dx, minDx, Math.max(minDx, maxDx));
        const dragDy = organizeClamp(dy, minDy, Math.max(minDy, maxDy));

        const rawDCol = Math.round(dragDx / cellW);
        const rawDRow = Math.round(dragDy / cellH);
        const maxEffRow = effectiveRows();

        // A group moves as one rigid shape: the offset it's allowed to take
        // is the intersection of what every one of its tiles can tolerate,
        // so no member is ever clamped separately from the rest.
        let minDCol = -Infinity, maxDCol = Infinity, minDRow = -Infinity, maxDRow = Infinity;
        groupTiles.forEach(function (gt) {
          minDCol = Math.max(minDCol, -gt.col);
          maxDCol = Math.min(maxDCol, state.cols - gt.colSpan - gt.col);
          minDRow = Math.max(minDRow, -gt.row);
          maxDRow = Math.min(maxDRow, maxEffRow - gt.rowSpan - gt.row);
        });
        deltaCol = organizeClamp(rawDCol, minDCol, maxDCol);
        deltaRow = organizeClamp(rawDRow, minDRow, maxDRow);

        const groupWids = {};
        groupTiles.forEach(function (gt) { groupWids[gt.wid] = true; });
        // Only cells free of every non-group tile count as a legal drop —
        // dragging never displaces a widget that's in the way.
        dropValid = groupTiles.every(function (gt) {
          return organizeCellsFree(state.tiles, gt.row + deltaRow, gt.col + deltaCol, gt.rowSpan, gt.colSpan, state.cols, groupWids);
        });

        // The carried tiles follow the pointer 1:1 (smooth); only the drop
        // preview snaps to the grid cells the release would actually commit.
        groupTiles.forEach(function (gt) {
          const node = canvas.querySelector('[data-wid="' + gt.wid + '"]');
          if (node) node.style.transform = "translate3d(" + dragDx + "px, " + dragDy + "px, 0)";
        });
        updatePreviews();
      });

      function endDrag() {
        if (!dragging) return;
        dragging = false;
        groupTiles.forEach(function (gt) {
          const node = canvas.querySelector('[data-wid="' + gt.wid + '"]');
          if (node) { node.classList.remove("is-dragging"); node.style.transform = ""; }
        });
        clearPreviews();
        if (moved && dropValid && (deltaRow !== 0 || deltaCol !== 0)) {
          groupTiles.forEach(function (gt) { gt.row += deltaRow; gt.col += deltaCol; });
          renderCanvas();
          commitLayout();
        } else if (moved) {
          // Invalid target (or no net movement) — snap back to place.
          renderCanvas();
        }
      }

      tileEl.addEventListener("pointerup", function () {
        if (modifierClick) { toggleSelection(t.wid); modifierClick = false; return; }
        endDrag();
      });
      tileEl.addEventListener("pointercancel", endDrag);
      tileEl.addEventListener("lostpointercapture", endDrag);
    }

    function resetGrid() {
      const layoutDefaults = (fieldById[F_ONI] || {}).default || {};
      state.cols = organizeClamp(Number(layoutDefaults.column_count) || 4, 1, 60);
      state.minRows = organizeClamp(Number((fieldById[F_ROWS] || {}).default) || 6, 1, 60);
      state.gridWidth = organizeClamp(Number(layoutDefaults.grid_width) || 250, 200, 340);
      state.alignment = layoutDefaults.grid_alignment || "center";
      state.widgetHeight = organizeClamp(Number(layoutDefaults.widget_height) || 150, 120, 320);
      state.tiles = [];
      selectedWids.clear();
      let i = 0;
      ORGANIZE_DEFAULT_LAYOUT.forEach(function (wid) {
        const spec = specsByWid[wid];
        if (!spec) return;
        const rowSpan = organizeClampSpan(spec.defaultSpan[0], spec, true);
        const colSpan = organizeClampSpan(spec.defaultSpan[1], spec, false);
        const slot = organizeFindFreeSlot(state.tiles, rowSpan, colSpan, state.cols);
        state.tiles.push({ wid: wid, row: slot.row, col: slot.col, rowSpan: rowSpan, colSpan: colSpan, displayName: spec.name });
        i += 1;
      });
      renderCanvas();
      commitLayout();
      const inputs = controls.querySelectorAll(".osw-organize-ctl-input");
      if (inputs[0]) inputs[0].value = state.cols;
      if (inputs[1]) inputs[1].value = state.minRows;
      if (inputs[2]) inputs[2].value = state.widgetHeight;
      if (inputs[3]) inputs[3].value = state.gridWidth;
      Array.prototype.forEach.call(alignSeg.querySelectorAll(".osw-segment-btn"), function (button) {
        button.classList.toggle("is-active", button.textContent.toLowerCase() === state.alignment);
      });
    }

    // ── context menu: resize (+/- span), rename, remove ──
    let openMenuEl = null;
    let tileMenuOutsideHandler = null;
    function closeTileMenu() {
      if (tileMenuOutsideHandler) {
        document.removeEventListener("pointerdown", tileMenuOutsideHandler, true);
        tileMenuOutsideHandler = null;
      }
      if (openMenuEl && openMenuEl.parentNode) openMenuEl.parentNode.removeChild(openMenuEl);
      openMenuEl = null;
      if (activeTileMenuClose === closeTileMenu) activeTileMenuClose = null;
    }
    function openTileMenu(t, spec, x, y) {
      if (activeTileMenuClose) activeTileMenuClose();
      closeTileMenu();
      const menu = el("div", "osw-organize-menu");
      menu.style.left = x + "px";
      menu.style.top = y + "px";

      function spanRow(labelText, current, min, max, onMinus, onPlus) {
        const row = el("div", "osw-organize-menu-row");
        row.appendChild(el("span", "osw-organize-menu-label", labelText));

        const stepper = el("div", "osw-organize-menu-stepper");

        const minus = el("button", "osw-organize-menu-step-btn");
        minus.type = "button";
        minus.innerHTML = ICON_MINUS;
        minus.setAttribute("aria-label", "Decrease " + labelText);
        minus.firstElementChild.setAttribute("aria-hidden", "true");
        minus.firstElementChild.setAttribute("focusable", "false");
        minus.disabled = current <= min;
        minus.addEventListener("click", onMinus);

        const valSpan = el("span", "osw-organize-menu-val", current);

        const plus = el("button", "osw-organize-menu-step-btn");
        plus.type = "button";
        plus.innerHTML = ICON_PLUS;
        plus.setAttribute("aria-label", "Increase " + labelText);
        plus.firstElementChild.setAttribute("aria-hidden", "true");
        plus.firstElementChild.setAttribute("focusable", "false");
        plus.disabled = current >= max;
        plus.addEventListener("click", onPlus);

        stepper.appendChild(minus);
        stepper.appendChild(valSpan);
        stepper.appendChild(plus);

        row.appendChild(stepper);
        return row;
      }

      const minSpan = (spec && spec.minSpan) || [1, 1];
      const maxSpan = (spec && spec.maxSpan) || [4, 4];
      if (maxSpan[1] > minSpan[1]) {
        menu.appendChild(spanRow(str("columns", "Columns"), t.colSpan, minSpan[1], Math.min(maxSpan[1], state.cols), function () {
          resizeTile(t, spec, t.rowSpan, t.colSpan - 1);
        }, function () {
          resizeTile(t, spec, t.rowSpan, t.colSpan + 1);
        }));
      }
      if ((!spec || !spec.fixedRows) && maxSpan[0] > minSpan[0]) {
        menu.appendChild(spanRow(str("rows", "Rows"), t.rowSpan, minSpan[0], maxSpan[0], function () {
          resizeTile(t, spec, t.rowSpan - 1, t.colSpan);
        }, function () {
          resizeTile(t, spec, t.rowSpan + 1, t.colSpan);
        }));
      }

      if (t.wid === "ready_to_go") {
        const designRow = el("div", "osw-organize-menu-row");
        designRow.appendChild(el("span", "osw-organize-menu-label", str("design", "Design")));
        const designSeg = el("div", "osw-segmented-control");
        [["squares", "Squares"], ["circles", "Circles"]].forEach(function (opt) {
          const btn = el("button", "osw-segment-btn" + ((t.design || "squares") === opt[0] ? " is-active" : ""), opt[1]);
          btn.type = "button";
          btn.setAttribute("aria-pressed", String((t.design || "squares") === opt[0]));
          btn.addEventListener("click", function () {
            t.design = opt[0];
            Array.prototype.forEach.call(designSeg.children, function (b) {
              const active = b === btn;
              b.classList.toggle("is-active", active);
              b.setAttribute("aria-pressed", String(active));
            });
            renderCanvas();
            commitLayout();
          });
          designSeg.appendChild(btn);
        });
        designRow.appendChild(designSeg);
        menu.appendChild(designRow);
      }

      if (t.wid === "restaurant_level") {
        const orientRow = el("div", "osw-organize-menu-row");
        orientRow.appendChild(el("span", "osw-organize-menu-label", str("widget_menu_orientation", "Orientation")));
        const orientSeg = el("div", "osw-segmented-control");
        const currentOrient = t.orientation || "horizontal";
        [
          ["horizontal", str("orientation_side_by_side", "Horizontal")],
          ["vertical", str("orientation_image_top", "Vertical")]
        ].forEach(function (opt) {
          const btn = el("div", "osw-segment-btn" + (currentOrient === opt[0] ? " is-active" : ""), opt[1]);
          btn.addEventListener("click", function () {
            t.orientation = opt[0];
            Array.prototype.forEach.call(orientSeg.querySelectorAll(".osw-segment-btn"), function (b) { b.classList.remove("is-active"); });
            btn.classList.add("is-active");
            renderCanvas();
            commitLayout();
          });
          orientSeg.appendChild(btn);
        });
        orientRow.appendChild(orientSeg);
        menu.appendChild(orientRow);
      }

      if (t.wid === "stats_title") {
        menu.classList.add("is-menu-title");
        // The grid tile is the Main Menu heading, so its context popup edits
        // the heading itself rather than the organizer-only display name.
        const menuTitleFields = SETTINGS_MODE_PARITY || settingsComplexity === "advanced"
          ? [
            "modern_menu_statsTitle",
            "onigiri_font_dashboard_title",
            "onigiri_font_size_dashboard_title",
            "modern_menu_title_alignment",
            "modern_menu_title_background_enabled",
            "modern_menu_title_sync_widgets",
            "modern_menu_title_background_type",
            "modern_menu_title_background_color",
            "modern_menu_title_background_image",
            "modern_menu_title_background_opacity",
            "modern_menu_title_background_blur"
          ]
          : ["modern_menu_statsTitle"];
        menuTitleFields.forEach(function (fieldId) {
          const field = fieldById[fieldId];
          const renderer = field && FIELD_RENDERERS[field.type];
          if (!renderer) return;
          const node = renderer(field);
          node.classList.add("osw-organize-menu-field");
          node.setAttribute("data-field-host", field.id);
          menu.appendChild(node);
        });
        menu.__section = { fields: menuTitleFields.map(function (id) { return fieldById[id]; }).filter(Boolean) };
        menu.__fieldsHost = menu;
        applyPlainVisibility(menu);
        conditionalBlocks.push(menu);
        menu.__afterVisibility = function () {
          if (!menu.isConnected) return;
          const height = menu.getBoundingClientRect().height;
          menu.style.top = Math.max(12, Math.min(y, window.innerHeight - height - 12)) + "px";
        };
      } else {
        const renameRow = el("div", "osw-organize-menu-row");
        const renameInput = document.createElement("input");
        renameInput.type = "text";
        renameInput.className = "osw-organize-menu-input";
        renameInput.value = t.displayName || spec.name;
        renameInput.addEventListener("change", function () {
          const text = renameInput.value.trim();
          if (text) { t.displayName = text; renderCanvas(); commitLayout(); }
        });
        renameRow.appendChild(renameInput);
        menu.appendChild(renameRow);
      }

      const removeRow = el("div", "osw-organize-menu-row");
      const removeBtn = el("button", "osw-organize-menu-remove", str("remove", "Remove"));
      removeBtn.type = "button";
      removeBtn.addEventListener("click", function () {
        state.tiles = state.tiles.filter(function (x) { return x !== t; });
        selectedWids.delete(t.wid);
        closeTileMenu();
        renderCanvas();
        commitLayout();
      });
      removeRow.appendChild(removeBtn);
      menu.appendChild(removeRow);

      document.body.appendChild(menu);
      openMenuEl = menu;
      activeTileMenuClose = closeTileMenu;
      const menuRect = menu.getBoundingClientRect();
      if (x + menuRect.width > window.innerWidth - 12) {
        menu.style.left = Math.max(12, window.innerWidth - menuRect.width - 12) + "px";
      }
      if (y + menuRect.height > window.innerHeight - 12) {
        menu.style.top = Math.max(12, window.innerHeight - menuRect.height - 12) + "px";
      }
      setTimeout(function () {
        if (openMenuEl !== menu) return;
        tileMenuOutsideHandler = onOutside;
        document.addEventListener("pointerdown", onOutside, true);
      }, 0);
      if (menu.__afterVisibility) menu.__afterVisibility();
      // Gallery interactions should not dismiss the underlying editor.
      function onOutside(event) {
        if (settingsPicker || gallery) return;
        if (!menu.contains(event.target)) closeTileMenu();
      }
    }

    function resizeTile(t, spec, rowSpan, colSpan) {
      rowSpan = organizeClampSpan(rowSpan, spec, true);
      colSpan = organizeClampSpan(colSpan, spec, false);
      if (t.col + colSpan > state.cols) t.col = Math.max(0, state.cols - colSpan);
      t.rowSpan = rowSpan; t.colSpan = colSpan;
      resolveAllOverlaps();
      closeTileMenu();
      renderCanvas();
      commitLayout();
    }

    // ── gallery: add a widget not currently on the grid ──
    function openWidgetGallery() {
      const placed = {};
      state.tiles.forEach(function (t) { placed[t.wid] = true; });
      const oniAvail = catalogue.onigiri.filter(function (o) {
        return isRepeatableSpec(o) || !placed[o.wid];
      });

      const extSeen = {};
      const extAvail = [];
      catalogue.external.forEach(function (o) {
        if (placed[o.wid]) return;
        const mainName = (o.name || o.wid).split(" - ")[0].trim().toLowerCase();
        if (extSeen[mainName] || extSeen[o.wid]) return;
        extSeen[mainName] = true;
        extSeen[o.wid] = true;
        extAvail.push(o);
      });

      if (!oniAvail.length && !extAvail.length) {
        toast(str("gallery_all_added", "All widgets are already on the grid"));
        return;
      }
      const root = el("div", "osw-gal");
      const card = el("div", "osw-gal-card osw-organize-gallery-card");
      root.appendChild(card);
      const head = el("div", "osw-gal-head");
      head.appendChild(el("div", "osw-gal-title", str("add_widget", "Add Widget")));
      const closeBtn = el("button", "osw-gal-close");
      closeBtn.type = "button";
      closeBtn.innerHTML = ICON_CLOSE;
      closeBtn.addEventListener("click", function () { if (root.parentNode) root.parentNode.removeChild(root); });
      head.appendChild(closeBtn);
      card.appendChild(head);

      const body = el("div", "osw-organize-gallery-body");
      card.appendChild(body);

      function section_(title, list, isExternal) {
        if (!list.length) return;
        const sec = el("div", "osw-organize-gallery-section");
        const secHead = el("div", "osw-organize-gallery-section-head");
        secHead.appendChild(el("span", "osw-organize-gallery-section-title", title));
        secHead.appendChild(el("span", "osw-organize-gallery-section-count", list.length + " " + str("available", "available")));
        sec.appendChild(secHead);

      const BENTO_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M0 10.435c0-.256.051-.512.153-.758c.233-.56.854-1.046 2.095-2.018l6.206-4.856c1.241-.972 1.862-1.458 2.577-1.64c.63-.16 1.308-.16 1.938 0c.715.183 1.336.668 2.577 1.64l6.206 4.856c1.241.972 1.862 1.458 2.095 2.018c.102.246.153.502.153.758v3.13c0 .256-.051.512-.153.758c-.233.56-.854 1.046-2.095 2.017l-6.206 4.857c-1.241.972-1.862 1.457-2.577 1.64c-.63.16-1.308.16-1.938 0c-.715-.183-1.336-.668-2.577-1.64L2.248 16.34C1.007 15.37.386 14.883.153 14.323A2 2 0 0 1 0 13.565zm9.34-3.238l.887.694c.62.485.93.728 1.289.82c.315.08.653.08.968 0c.358-.092.668-.335 1.29-.82l.886-.694c.62-.486.93-.729 1.047-1.009a.98.98 0 0 0 0-.758c-.116-.28-.427-.523-1.047-1.008l-.887-.694c-.62-.486-.93-.729-1.289-.82a2 2 0 0 0-.968 0c-.358.091-.668.334-1.29.82l-.886.694c-.62.485-.93.728-1.047 1.008a.98.98 0 0 0 0 .758c.116.28.427.523 1.047 1.009m5.91 4.625l.887.694c.62.486.931.729 1.29.82c.314.08.653.08.968 0c.358-.091.668-.334 1.288-.82l.887-.694c.62-.485.931-.728 1.047-1.008a.98.98 0 0 0 0-.758c-.116-.28-.426-.523-1.047-1.009l-.887-.694c-.62-.485-.93-.728-1.288-.82a2 2 0 0 0-.969 0c-.358.092-.668.335-1.289.82l-.886.694c-.621.486-.931.729-1.047 1.009a.98.98 0 0 0 0 .758c.116.28.426.523 1.047 1.008Zm-11.82 0l6.797 5.32c.62.486.93.728 1.289.82c.315.08.653.08.968 0c.358-.092.668-.334 1.29-.82l.886-.694c.62-.486.93-.729 1.047-1.009a.97.97 0 0 0 0-.758c-.116-.28-.427-.523-1.047-1.008l-6.797-5.32c-.62-.485-.931-.728-1.29-.82a2 2 0 0 0-.968 0c-.358.092-.668.335-1.288.82l-.887.694c-.62.486-.931.729-1.047 1.009a.98.98 0 0 0 0 .758c.116.28.426.523 1.047 1.008"/></svg>';

        const grid = el("div", "osw-organize-gallery-grid");
        list.forEach(function (o) {
          const spec = specForWid(o.wid) || o;
          const tile = el("button", "osw-organize-gallery-item");
          tile.type = "button";

          let rawName = spec.name || o.wid;
          let mainTitle = rawName;
          let subText = "";
          if (rawName.indexOf(" - ") !== -1) {
            const parts = rawName.split(" - ");
            mainTitle = parts[0].trim();
            subText = parts.slice(1).join(" - ").trim();
          } else if (!isExternal) {
            const defaultSpan = spec.defaultSpan || [1, 1];
            const multiplicity = isRepeatableSpec(spec)
              ? str("multiple_instances_allowed", "Multiple instances allowed") + " • "
              : "";
            subText = multiplicity + "Onigiri Widget • " + defaultSpan[1] + "×" + defaultSpan[0];
          }

          const content = el("div", "osw-organize-gallery-item-content");
          const headEl = el("div", "osw-organize-gallery-item-head");
          const bentoNames = ["global", "sticky", "power", "hours", "berry", "league"];
          const isBento = spec.kind === "bento" || bentoNames.some(function (b) {
            return mainTitle.toLowerCase().indexOf(b) !== -1 || (spec.wid || "").toLowerCase().indexOf(b) !== -1;
          });

          if (isBento) {
            const iconSpan = el("span", "osw-organize-gallery-item-icon");
            iconSpan.innerHTML = BENTO_SVG;
            headEl.appendChild(iconSpan);
          }
          headEl.appendChild(el("span", "osw-organize-gallery-item-title", mainTitle));
          content.appendChild(headEl);

          if (subText) {
            content.appendChild(el("div", "osw-organize-gallery-item-desc", subText));
          }

          const action = el("div", "osw-organize-gallery-item-add", "+ Add");

          tile.appendChild(content);
          tile.appendChild(action);

          tile.addEventListener("click", function () {
            const rowSpan = organizeClampSpan(spec.defaultSpan ? spec.defaultSpan[0] : 1, spec, true);
            const colSpan = organizeClampSpan(spec.defaultSpan ? spec.defaultSpan[1] : 1, spec, false);
            const slot = organizeFindFreeSlot(state.tiles, rowSpan, colSpan, state.cols);
            const repeatable = isRepeatableSpec(spec);
            const wid = repeatable ? nextDeckStatsInstanceWid() : spec.wid;
            const displayName = repeatable && wid !== "deck_stats"
              ? spec.name + " " + wid.slice("deck_stats_".length)
              : spec.name;
            state.tiles.push({ wid: wid, row: slot.row, col: slot.col, rowSpan: rowSpan, colSpan: colSpan, displayName: displayName });
            if (root.parentNode) root.parentNode.removeChild(root);
            renderCanvas();
            commitLayout();
          });
          grid.appendChild(tile);
        });
        sec.appendChild(grid);
        body.appendChild(sec);
      }
      section_(str("gallery_onigiri", "Onigiri Widgets"), oniAvail, false);
      section_(str("gallery_external", "External Add-ons"), extAvail, true);

      root.addEventListener("mousedown", function (event) { if (event.target === root && root.parentNode) root.parentNode.removeChild(root); });
      document.body.appendChild(root);
    }

    activeWidgetGridPreviews.push(function () {
      if (!canvas.isConnected) {
        if (tileRadiusObserver) tileRadiusObserver.disconnect();
        return false;
      }
      return paintWidgetGridPreview();
    });
    activeWidgetGridBackgroundReceiver = function (background) {
      if (!canvas.isConnected) return;
      displayedMenuBackground = background;
      paintWidgetGridPreview();
    };
    // Start after the grid has been mounted. Stop when switching away so a
    // background-only read never runs for another Settings section.
    requestAnimationFrame(function () {
      if (!canvas.isConnected) return;
      canvas.querySelectorAll(".osw-organize-tile").forEach(syncTileRemoveRadius);
      function syncBackground() {
        if (!canvas.isConnected) {
          if (tileRadiusObserver) tileRadiusObserver.disconnect();
          stopWidgetGridBackgroundSync();
          return;
        }
        bridge("osw:grid_background:");
      }
      syncBackground();
      widgetGridBackgroundTimer = setInterval(syncBackground, 500);
    });
    // Older integrations could register a Bento widget at cell zero, which
    // collides with the title widget in a unified grid. Config normalisation
    // repairs that for the main menu; resolve here as well so opening Organize
    // is safe even when this dialog received a stale in-memory layout.
    resolveAllOverlaps();
    renderCanvas();
    return wrap;
  }

  /* The sidebar's action-button layout, edited as one list: drag a row to
     reorder it, click its eye to archive it. Replaces the legacy 3-zone
     drag/drop editor plus its right-click menu (settings/_layout_sidebar.py,
     _infra.py:830-1000) — one list with two states says the same thing, and the
     archived half is where "Hidden" already lived.

     The stored value carries ids this dialog knows nothing about: the "profile"
     pill, and buttons other add-ons registered through the sidebar API. Those
     are read, kept in their original order, and written straight back — an
     editor that silently dropped them would uninstall another add-on's button.

     Dragging is pointer events, NOT HTML5 drag-and-drop: `dragstart` never
     fires inside Anki's webview, so the native version looked exactly like a
     broken list. The dragged row moves in the DOM as the pointer passes each
     neighbour (so the list shows the result, not a floating ghost), and the
     settled DOM order is what gets committed on release. */
  function renderButtonOrder(field) {
    const host = el("div", "osw-btnorder");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "button_order");

    const known = {};
    const allowArchive = field.allowArchive !== false;
    const hasMoreBucket = field.moreBucket === true;
    (field.options || []).forEach(function (option) { known[option.value] = option; });

    function layout() {
      const raw = values[field.id] || {};
      const visible = Array.isArray(raw.visible) ? raw.visible.slice() : [];
      const more = hasMoreBucket && Array.isArray(raw.more) ? raw.more.slice() : [];
      const archived = Array.isArray(raw.archived) ? raw.archived.slice() : [];
      if (!allowArchive) {
        // Insert newly introduced sections according to the schema's order.
        // In particular, this migrates the old combined Profile & Actions row
        // into two adjacent, independently draggable rows.
        const optionIds = (field.options || []).map(function (option) {
          return option.value;
        });
        optionIds.forEach(function (id, index) {
          if (visible.indexOf(id) !== -1) return;
          const nextExisting = optionIds.slice(index + 1).find(function (nextId) {
            return visible.indexOf(nextId) !== -1;
          });
          const insertAt = nextExisting === undefined
            ? visible.length : visible.indexOf(nextExisting);
          visible.splice(insertAt, 0, id);
        });
      }
      return {
        visible: visible,
        more: more,
        archived: allowArchive ? archived : []
      };
    }

    /* Writes back a new arrangement of the ids this editor manages, with every
       foreign id restored to the bucket and relative position it came from. */
    function commit(nextVisible, nextMore, nextArchived) {
      const before = layout();
      function merge(nextKnown, previous) {
        const out = [];
        previous.forEach(function (id) { if (!known[id]) out.push(id); });
        return out.concat(nextKnown);
      }
      setValue(field.id, {
        visible: merge(nextVisible, before.visible),
        ...(hasMoreBucket ? { more: merge(nextMore, before.more) } : {}),
        archived: allowArchive ? merge(nextArchived, before.archived) : []
      }, { keepDom: true });
      paint();
      updateDesignerPreviews();
    }

    function managed(list) {
      return list.filter(function (id) { return !!known[id]; });
    }

    function makeRow(id, bucket) {
      const archived = bucket === "archived";
      const option = known[id];
      const row = el("div", "osw-btnorder-row" + (archived ? " is-archived" : ""));
      row.setAttribute("data-id", id);

      const handle = el("span", "osw-btnorder-handle");
      handle.innerHTML = OSW_DRAG_HANDLE;
      row.appendChild(handle);

      const glyph = el("span", "osw-btnorder-icon");
      glyph.innerHTML = option.icon || "";
      row.appendChild(glyph);
      row.appendChild(el("span", "osw-btnorder-label", option.label || id));

      if (allowArchive) {
        const toggle = el("button", "osw-btnorder-eye");
        toggle.type = "button";
        toggle.title = archived
          ? str("button_order_show", "Show this button")
          : str("button_order_hide", "Move to archived");
        toggle.innerHTML = archived ? OSW_EYE_OFF : OSW_EYE;
        toggle.addEventListener("click", function (event) {
          event.stopPropagation();
          bridge("osw:haptic:1");
          const now = layout();
          const visible = managed(now.visible).filter(function (x) { return x !== id; });
          const more = managed(now.more).filter(function (x) { return x !== id; });
          const archivedIds = managed(now.archived).filter(function (x) { return x !== id; });
          if (archived) visible.push(id); else archivedIds.push(id);
          commit(visible, more, archivedIds);
        });
        row.appendChild(toggle);
      }

      row.addEventListener("pointerdown", function (event) {
        // The eye is a button of its own; pressing it must not start a drag.
        if (event.target.closest(".osw-btnorder-eye")) return;
        if (event.button !== undefined && event.button !== 0) return;
        // In WebKit's webview a pointer drag on label text otherwise begins a
        // native selection before our pointer-move handler can rearrange it.
        event.preventDefault();
        beginDrag(row, event);
      });
      return row;
    }

    /* Pointer drag. A lifted row follows the pointer freely while a placeholder
       marks its eventual position. Nothing is written until pointer release. */
    function beginDrag(row, event) {
      const startX = event.clientX;
      const startY = event.clientY;
      const startRect = row.getBoundingClientRect();
      const grabX = startX - startRect.left;
      const grabY = startY - startRect.top;
      const placeholder = el("div", "osw-btnorder-placeholder");
      placeholder.style.height = startRect.height + "px";
      let moved = false;
      let lifted = false;

      function canEnter(list) {
        return !!list && !(row.getAttribute("data-id") === "more" &&
          list.getAttribute("data-bucket") === "more");
      }

      function lift() {
        if (lifted) return;
        lifted = true;
        row.parentNode.insertBefore(placeholder, row);
        document.body.appendChild(row);
        row.classList.add("is-dragging");
        host.classList.add("has-active-drag");
        if (row.getAttribute("data-id") === "more") {
          host.classList.add("is-dragging-more");
        }
        row.style.position = "fixed";
        row.style.left = startRect.left + "px";
        row.style.top = startRect.top + "px";
        row.style.width = startRect.width + "px";
        row.style.zIndex = "10000";
        row.style.pointerEvents = "none";
        row.style.margin = "0";
      }

      function place(clientX, clientY) {
        row.style.left = (clientX - grabX) + "px";
        row.style.top = (clientY - grabY) + "px";
        const under = document.elementFromPoint(clientX, clientY);
        if (!under) return;
        const overRow = under.closest(".osw-btnorder-row");
        if (overRow && overRow !== row && host.contains(overRow)) {
          const targetList = overRow.closest(".osw-btnorder-list");
          if (!canEnter(targetList)) return;
          const rect = overRow.getBoundingClientRect();
          const after = clientY > rect.top + rect.height / 2;
          overRow.parentNode.insertBefore(
            placeholder,
            after ? overRow.nextSibling : overRow
          );
          return;
        }
        // Empty space in a bucket (including an empty bucket, which is the only
        // way the last button out of one can be put back).
        const overList = under.closest(".osw-btnorder-list");
        if (overList && host.contains(overList) && canEnter(overList) &&
            placeholder.parentNode !== overList) {
          overList.appendChild(placeholder);
        }
      }

      function onMove(moveEvent) {
        // Distance, not vertical distance: dragging straight sideways into the
        // other bucket is a real gesture and moves the pointer barely at all
        // on the axis the rows are stacked on.
        if (!moved &&
            Math.abs(moveEvent.clientY - startY) < 3 &&
            Math.abs(moveEvent.clientX - startX) < 3) return;
        moved = true;
        moveEvent.preventDefault();
        lift();
        place(moveEvent.clientX, moveEvent.clientY);
      }

      function onUp() {
        window.removeEventListener("pointermove", onMove, true);
        window.removeEventListener("pointerup", onUp, true);
        window.removeEventListener("pointercancel", onUp, true);
        if (!moved) return;
        if (placeholder.parentNode) {
          placeholder.parentNode.replaceChild(row, placeholder);
        }
        row.classList.remove("is-dragging");
        host.classList.remove("has-active-drag", "is-dragging-more");
        row.style.position = "";
        row.style.left = "";
        row.style.top = "";
        row.style.width = "";
        row.style.zIndex = "";
        row.style.pointerEvents = "";
        row.style.margin = "";
        commitFromDom();
      }

      // On window rather than on the row, and without setPointerCapture: the
      // row is re-parented mid-drag, and a capture on a moving element is one
      // more thing that can silently drop the gesture.
      window.addEventListener("pointermove", onMove, true);
      window.addEventListener("pointerup", onUp, true);
      window.addEventListener("pointercancel", onUp, true);
    }

    /* The lists as they now stand on screen. Reading the DOM rather than
       tracking indices keeps the committed order and the visible order the same
       thing by construction. */
    function commitFromDom() {
      const lists = host.querySelectorAll(".osw-btnorder-list");
      function idsOf(list) {
        return list
          ? Array.prototype.map.call(list.querySelectorAll(".osw-btnorder-row"),
              function (node) { return node.getAttribute("data-id"); })
          : [];
      }
      const visible = idsOf(lists[0]);
      const more = hasMoreBucket ? idsOf(lists[1]) : [];
      const archived = idsOf(lists[hasMoreBucket ? 2 : 1]);
      commit(visible, more, archived);
    }

    function makeBucket(title, ids, bucketName, emptyText) {
      const archived = bucketName === "archived";
      const bucket = el("div", "osw-btnorder-bucket" + (archived ? " is-archived" : ""));
      bucket.appendChild(el("div", "osw-btnorder-bucket-title", title));
      const list = el("div", "osw-btnorder-list");
      list.setAttribute("data-bucket", bucketName);
      ids.forEach(function (id) { list.appendChild(makeRow(id, bucketName)); });
      // An empty bucket still has to be a drop target — otherwise the last
      // button out of it could never be put back. The placeholder is not a row,
      // so it never takes part in the ordering.
      if (!ids.length) list.appendChild(el("div", "osw-btnorder-empty", emptyText));
      bucket.appendChild(list);
      return bucket;
    }

    function paint() {
      host.innerHTML = "";
      host.appendChild(makeFieldHead(field, null));
      const now = layout();
      const visible = managed(now.visible);
      const more = managed(now.more);
      const archived = managed(now.archived);
      // Anything the schema knows about that the stored layout mentions nowhere
      // (a button added by a later Onigiri version) is shown as archived rather
      // than vanishing from the editor.
      (field.options || []).forEach(function (option) {
        if (visible.indexOf(option.value) === -1 &&
            more.indexOf(option.value) === -1 &&
            archived.indexOf(option.value) === -1) {
          (allowArchive ? archived : visible).push(option.value);
        }
      });
      const body = el("div", "osw-btnorder-buckets");
      body.appendChild(makeBucket(
        hasMoreBucket
          ? str("button_order_outside_more", "Outside More")
          : (allowArchive ? str("button_order_visible", "On the sidebar") : str("top_to_bottom", "Top to bottom")),
        visible, "visible",
        str("button_order_none_visible", "No buttons — drag one back here.")
      ));
      if (hasMoreBucket) {
        body.appendChild(makeBucket(
          str("more", "More"), more, "more",
          str("button_order_none_more", "Nothing under More.")
        ));
      }
      if (allowArchive) {
        body.appendChild(makeBucket(
          str("button_order_archived", "Archived"), archived, "archived",
          str("button_order_none_archived", "Nothing archived.")
        ));
      }
      host.appendChild(body);
    }

    field.__syncButtonOrder = paint;
    host.__syncButtonOrder = paint;
    paint();
    return host;
  }

  /* ── Games pages ───────────────────────────────────────────────────────────
   *
   * Everything below belongs to the pages that replaced the standalone
   * "Gamification Settings" window. They need three things the rest of the
   * dialog does not: colours stored in Qt's #AARRGGBB order, live state that
   * comes from a game manager rather than the config (the Onigimon roster, the
   * island balance, the installed Bento add-ons), and previews of widgets that
   * live outside the deck browser's own CSS.
   */

  const gamesCtx = CTX.games || {};

  /* State that costs a game-module import on the Python side, fetched the first
     time a Games page is opened rather than on every settings open. Everything
     that consumes it paints an empty shape first and repaints on arrival, so a
     slow Ankimon probe never blocks the page appearing. */
  let gamesContextPending = false;

  function ensureGamesContext() {
    if (gamesCtx.loaded || gamesContextPending) return;
    gamesContextPending = true;
    call("osw:games_context:").then(function (res) {
      gamesContextPending = false;
      if (!res || !res.games) return;
      Object.keys(res.games).forEach(function (key) { gamesCtx[key] = res.games[key]; });
      refreshGamesLive();
    });
  }

  /* Every control fed by that context. Called once it lands, and again after
     any action that changes it. */
  function refreshGamesLive() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-note-live"), function (node) {
      if (node.__syncNote) node.__syncNote();
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-companions"), function (node) {
      if (node.__syncCompanions) node.__syncCompanions();
    });
    refreshHexagonCards();
    Array.prototype.forEach.call(document.querySelectorAll(".osw-bento"), function (node) {
      if (node.__syncBento) node.__syncBento();
    });
    updateDesignerPreviews();
  }

  /* Qt writes a translucent colour as #AARRGGBB; CSS puts the alpha LAST, so
     handing one straight to the browser silently reads the alpha byte as blue.
     The chip's background is the one setting stored that way. */
  function qtColorToCss(value) {
    const text = String(value || "").trim();
    if (text.length !== 9 || text[0] !== "#") return text;
    const a = parseInt(text.slice(1, 3), 16);
    const r = parseInt(text.slice(3, 5), 16);
    const g = parseInt(text.slice(5, 7), 16);
    const b = parseInt(text.slice(7, 9), 16);
    if ([a, r, g, b].some(isNaN)) return text;
    return "rgba(" + r + "," + g + "," + b + "," + (a / 255).toFixed(3) + ")";
  }

  /* The opaque #RRGGBB inside a colour that may carry Qt alpha — what the
     colour picker should open on, and what a contrast check should judge. */
  function qtColorRgb(value) {
    const text = String(value || "").trim();
    if (text.length === 9 && text[0] === "#") return "#" + text.slice(3);
    return text;
  }

  /* An opaque #RRGGBB for anything this file may be showing — a plain hex, a
     Qt #AARRGGBB, or the rgba() a converted one becomes. Used wherever a value
     leaves for the native colour picker, which has no alpha channel. */
  function cssColorToHex(value) {
    const text = String(value || "").trim();
    if (/^#[0-9a-f]{6}$/i.test(text)) return text;
    if (text.length === 9 && text[0] === "#") return qtColorRgb(text);
    const match = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(text);
    if (match) return rgbToHex(+match[1], +match[2], +match[3]);
    return text;
  }

  function qtColorAlpha(value) {
    const text = String(value || "").trim();
    if (text.length !== 9 || text[0] !== "#") return 100;
    const a = parseInt(text.slice(1, 3), 16);
    return isNaN(a) ? 100 : Math.round((a / 255) * 100);
  }

  function qtColorWithAlpha(rgb, percent) {
    const hex = qtColorRgb(rgb);
    if (!/^#[0-9a-f]{6}$/i.test(hex)) return hex;
    const clamped = Math.max(0, Math.min(100, Math.round(percent)));
    if (clamped >= 100) return hex;
    const a = Math.round((clamped / 100) * 255);
    return "#" + (a < 16 ? "0" : "") + a.toString(16) + hex.slice(1);
  }

  // Which theme the Level Chip card is previewing. The chip's colours are
  // per-theme when Dynamic is on, so the opacity slider and the inherited
  // swatches follow the stage rather than Anki's current mode.
  let chipPreviewDark = !!CTX.dark;

  function chipFallbackDark(target) {
    if (target && target.role === "dark") return true;
    if (target && target.role === "light") return false;
    return chipPreviewDark;
  }

  /* The chip colour key the opacity slider is currently editing: the shared one
     while Dynamic is off, otherwise the one for the theme on the stage. */
  function chipAlphaKey(field) {
    const target = fieldById[field.alphaOf];
    if (!target) return null;
    if (!pairAvailable(target) || pairLinked(target)) return target.singleField || target.id;
    return chipPreviewDark ? target.darkField : target.lightField;
  }

  function chipAlphaPercent(field) {
    const key = chipAlphaKey(field);
    if (!key) return 100;
    const raw = values[key];
    if (!raw) {
      // Nothing chosen yet: the slider shows the inherited colour's own alpha,
      // so moving it starts from what is on screen rather than from 100%.
      const target = fieldById[field.alphaOf];
      const defaults = (CTX.chipDefaults || {})[chipPreviewDark ? "dark" : "light"] || {};
      const inherited = target && target.chipRole ? defaults[target.chipRole] : "";
      const match = /rgba\([^,]+,[^,]+,[^,]+,\s*([0-9.]+)\)/.exec(String(inherited || ""));
      return match ? Math.round(parseFloat(match[1]) * 100) : 100;
    }
    return qtColorAlpha(raw);
  }

  function setChipAlpha(field, percent) {
    const key = chipAlphaKey(field);
    if (!key) return;
    values[field.id] = percent;
    const target = fieldById[field.alphaOf];
    const defaults = (CTX.chipDefaults || {})[chipPreviewDark ? "dark" : "light"] || {};
    // Starting from the inherited colour means the first drag makes the chip
    // its own colour at that opacity instead of jumping to black.
    let base = qtColorRgb(values[key] || "");
    if (!/^#[0-9a-f]{6}$/i.test(base)) {
      const inherited = target && target.chipRole ? defaults[target.chipRole] : "";
      const rgbMatch = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(String(inherited || ""));
      base = rgbMatch
        ? rgbToHex(+rgbMatch[1], +rgbMatch[2], +rgbMatch[3])
        : (chipPreviewDark ? "#000000" : "#ffffff");
    }
    setValue(key, qtColorWithAlpha(base, percent), { keepDom: true, debounce: true });
  }

  /* Keeps a chosen colour's opacity when the native picker hands back an opaque
     hex — the picker has no alpha channel, and losing it would silently make a
     translucent chip solid. */
  function chipPreserveAlpha(id, value) {
    const slider = gamesAlphaSliderFor(id);
    if (!slider) return value;
    return qtColorWithAlpha(value, values[slider.id]);
  }

  function gamesAlphaSliderFor(colorKey) {
    let found = null;
    Object.keys(fieldById).forEach(function (fid) {
      const field = fieldById[fid];
      if (!field.alphaOf) return;
      if (chipAlphaKey(field) === colorKey) found = field;
    });
    return found;
  }

  // ── notification position ─────────────────────────────────────────────────

  const NOTIF_POSITIONS = [
    ["top-left", "↖"], ["top-center", "↑"], ["top-right", "↗"],
    ["bottom-left", "↙"], ["bottom-center", "↓"], ["bottom-right", "↘"],
  ];

  /* The six reviewer anchors, as a 3x2 pad beside a miniature of the reviewer
     with the notification drawn where it will actually appear — the picture is
     the label, exactly as in the classic dialog. */
  function renderNotifPosition(field) {
    const host = el("div", "osw-notifpos");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "notif_position");
    if (field.label) host.appendChild(el("div", "osw-row-label", field.label));

    const body = el("div", "osw-notifpos-body");
    const pad = el("div", "osw-notifpos-pad");

    // No miniature screen of its own anymore: this control sits under a stage
    // that already shows the real toast at the picked corner, and two previews
    // of one setting disagreeing is worse than one.
    const buttons = {};
    function paint() {
      const value = values[field.id] || "top-center";
      Object.keys(buttons).forEach(function (id) {
        buttons[id].classList.toggle("is-active", id === value);
      });
    }

    NOTIF_POSITIONS.forEach(function (entry) {
      const button = el("button", "osw-notifpos-btn", entry[1]);
      button.type = "button";
      button.title = entry[0];
      buttons[entry[0]] = button;
      button.addEventListener("click", function () {
        bridge("osw:haptic:1");
        setValue(field.id, entry[0], { keepDom: true });
        paint();
      });
      pad.appendChild(button);
    });

    body.appendChild(pad);
    host.appendChild(body);
    host.__syncNotifPos = paint;
    paint();
    return host;
  }

  // ── picture-card choice (difficulty pickers) ──────────────────────────────

  /* One card per option: artwork, name, and what choosing it does. The Nook's
     three ranks and Onigimon's three starters were both this control in the
     classic dialog, and the picture is the fastest thing to recognise. */
  function renderGameChoice(field) {
    const host = el("div", "osw-gamechoice");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "game_choice");
    if (field.label) host.appendChild(el("div", "osw-row-label", field.label));

    const list = el("div", "osw-gamechoice-list");
    (field.options || []).forEach(function (option) {
      const card = el("button", "osw-gamechoice-card");
      card.type = "button";
      card.setAttribute("data-value", option.value);

      const badge = el("span", "osw-gamechoice-badge");
      if (option.accent) {
        badge.style.backgroundColor = rgba(option.accent, 0.12);
        badge.style.borderColor = rgba(option.accent, 0.26);
      }
      if (option.image) {
        const img = document.createElement("img");
        img.src = option.image;
        img.alt = "";
        badge.appendChild(img);
      } else if (option.icon) {
        badge.innerHTML = option.icon;
        if (option.accent) badge.style.color = option.accent;
      }
      card.appendChild(badge);

      const text = el("span", "osw-gamechoice-text");
      text.appendChild(el("span", "osw-gamechoice-title", option.label));
      if (option.desc) text.appendChild(el("span", "osw-gamechoice-desc", option.desc));
      card.appendChild(text);
      const check = el("span", "osw-gamechoice-check");
      if (option.accent) {
        card.style.setProperty("--osw-gamechoice-accent", option.accent);
        card.style.backgroundColor = rgba(option.accent, 0.08);
        check.style.borderColor = option.accent;
      }
      card.appendChild(check);

      card.addEventListener("click", function () {
        bridge("osw:haptic:1");
        setValue(field.id, option.value, { keepDom: true });
        paint();
      });
      list.appendChild(card);
    });

    function paint() {
      const value = values[field.id];
      Array.prototype.forEach.call(list.querySelectorAll(".osw-gamechoice-card"), function (card) {
        const active = card.getAttribute("data-value") === String(value);
        card.classList.toggle("is-selected", active);
        const option = (field.options || []).filter(function (o) {
          return String(o.value) === card.getAttribute("data-value");
        })[0];
        const accent = option && option.accent;
        card.style.borderColor = active && accent ? accent : (accent ? rgba(accent, 0.26) : "");
        card.style.backgroundColor = accent ? rgba(accent, active ? 0.16 : 0.08) : "";
        const dot = card.querySelector(".osw-gamechoice-check");
        if (dot) {
          dot.style.borderColor = accent || "";
          dot.style.background = active && accent
            ? "radial-gradient(circle, " + accent + " 0 45%, transparent 46%)"
            : "transparent";
        }
      });
    }

    host.appendChild(list);
    host.__syncGameChoice = paint;
    paint();
    return host;
  }

  // ── message list ──────────────────────────────────────────────────────────

  const ICON_ARROW_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  const ICON_ARROW_DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>';
  const ICON_TRASH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"' +
    ' stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"/></svg>';

  /* One message per row, reorderable and removable. The setting is a list, and
     editing it as a textarea made a message with a line break in it impossible
     to express — the classic dialog learned that and shipped this same editor. */
  function renderMessageList(field) {
    const host = el("div", "osw-msglist");
    host.setAttribute("data-field", field.id);
    host.setAttribute("data-field-type", "message_list");
    if (field.label) host.appendChild(el("div", "osw-row-label", field.label));
    if (field.desc) host.appendChild(el("div", "osw-row-desc", field.desc));

    const rows = el("div", "osw-msglist-rows");
    host.appendChild(rows);

    function current() {
      const value = values[field.id];
      return Array.isArray(value) ? value.slice() : [];
    }

    function commit(list, options) {
      // Blank rows are not messages; they exist only while the user is typing
      // one, so they are dropped on the way to storage rather than persisted.
      setValue(field.id, list.filter(function (item) {
        return String(item).trim() !== "";
      }), options || { debounce: true, keepDom: true });
    }

    function paint(focusIndex) {
      const list = current();
      rows.innerHTML = "";
      list.forEach(function (message, index) {
        const row = el("div", "osw-msglist-row");

        const input = document.createElement("input");
        input.type = "text";
        input.className = "osw-text-input osw-msglist-input";
        input.value = message;
        input.placeholder = str("message_placeholder", "Write a message…");
        input.addEventListener("input", function () {
          const next = current();
          next[index] = input.value;
          // keepDom so the row being typed in is not rebuilt under the cursor.
          values[field.id] = next;
          commit(next);
        });
        row.appendChild(input);

        const tools = el("div", "osw-msglist-tools");
        function toolButton(icon, title, disabled, onClick) {
          const button = el("button", "osw-msglist-btn");
          button.type = "button";
          button.innerHTML = icon;
          button.title = title;
          button.disabled = !!disabled;
          if (!disabled) button.addEventListener("click", onClick);
          return button;
        }
        tools.appendChild(toolButton(ICON_ARROW_UP, str("message_move_up", "Move up"), index === 0, function () {
          const next = current();
          const moved = next.splice(index, 1)[0];
          next.splice(index - 1, 0, moved);
          values[field.id] = next;
          commit(next, { keepDom: true });
          paint();
        }));
        tools.appendChild(toolButton(ICON_ARROW_DOWN, str("message_move_down", "Move down"), index === list.length - 1, function () {
          const next = current();
          const moved = next.splice(index, 1)[0];
          next.splice(index + 1, 0, moved);
          values[field.id] = next;
          commit(next, { keepDom: true });
          paint();
        }));
        tools.appendChild(toolButton(ICON_TRASH, str("message_remove", "Remove"), false, function () {
          const next = current();
          next.splice(index, 1);
          values[field.id] = next;
          commit(next, { keepDom: true });
          paint();
        }));
        row.appendChild(tools);
        rows.appendChild(row);

        if (focusIndex === index) {
          input.focus();
        }
      });
    }

    const add = el("button", "osw-msglist-add");
    add.type = "button";
    add.appendChild(el("span", "osw-msglist-add-icon", "+"));
    add.appendChild(el("span", null, str("message_add", "Add message")));
    add.addEventListener("click", function () {
      bridge("osw:haptic:1");
      const next = current();
      next.push("");
      values[field.id] = next;
      paint(next.length - 1);
    });
    host.appendChild(add);

    host.__syncMessageList = paint;
    paint();
    return host;
  }

  // ── Onigimon companions ───────────────────────────────────────────────────

  /* The roster comes from Ankimon, not from the config, so this section is a
     live list: it paints what Python last reported and can ask for it again. */
  function renderOnigimonCompanions(section) {
    const host = el("div", "osw-companions");
    const status = el("div", "osw-companions-status");
    host.appendChild(status);

    const nicknameField = (section.fields || []).filter(function (f) {
      return f.type === "text";
    })[0];
    const menuPokemonField = (section.fields || []).filter(function (f) {
      return f.id === "g_onigimon_menu_pokemon";
    })[0];
    if (nicknameField) host.appendChild(renderText(nicknameField));

    const grid = el("div", "osw-companions-grid");
    host.appendChild(grid);

    const actions = el("div", "osw-companions-actions");
    const refresh = el("button", "osw-btn", str("onigimon_refresh_button", "Refresh"));
    refresh.type = "button";
    refresh.addEventListener("click", function () {
      bridge("osw:haptic:1");
      status.textContent = str("onigimon_status_loading", "Loading…");
      call("osw:games_companions:1").then(function (res) {
        if (res && res.companions) gamesCtx.companions = res.companions;
        if (res && res.preview) gamesCtx.companionPreview = res.preview;
        paint();
        updateDesignerPreviews();
      });
    });
    actions.appendChild(refresh);
    host.appendChild(actions);

    const note = el("div", "osw-row-desc", str("onigimon_starter_note", ""));
    host.appendChild(note);

    if (menuPokemonField) {
      host.appendChild(el(
        "div",
        "osw-companions-menu-hint",
        str("onigimon_menu_team_hint", "Use the pin on each Pokémon to show it in the Pokémon Team widget on the Main Menu.")
      ));
    }

    function paint() {
      const data = gamesCtx.companions || { companions: [], message: "", active: "" };
      status.textContent = data.message || "";
      grid.innerHTML = "";
      const menuPokemonIds = Array.isArray(values.g_onigimon_menu_pokemon)
        ? values.g_onigimon_menu_pokemon.map(String)
        : [];
      (data.companions || []).forEach(function (pokemon) {
        // A tile contains its own pin button, so it must not itself be a
        // button (nested interactive controls are invalid HTML and QtWebEngine
        // handles their clicks inconsistently).
        const tile = el("div", "osw-companion-tile");
        tile.tabIndex = 0;
        tile.setAttribute("role", "button");
        tile.title = pokemon.name + " · " + str("onigimon_level_short", "Lv") + " " + pokemon.level;
        tile.classList.toggle("is-active", String(pokemon.id) === String(values.g_onigimon_companion || data.active));
        tile.classList.toggle("is-on-menu", menuPokemonIds.indexOf(String(pokemon.id)) !== -1);
        if (pokemon.sprite) {
          const img = document.createElement("img");
          img.src = pokemon.sprite;
          img.alt = "";
          tile.appendChild(img);
        } else {
          tile.appendChild(el("span", "osw-companion-initials", pokemon.name.slice(0, 2).toUpperCase()));
        }
        tile.addEventListener("click", function () {
          bridge("osw:haptic:1");
          // Not a plain setValue: choosing a companion makes the manager the
          // source of its nickname, which comes back with the reply.
          values.g_onigimon_companion = String(pokemon.id);
          paint();
          call("osw:games_pick_companion:" + encodeURIComponent(pokemon.id)).then(function (res) {
            if (res && res.preview) gamesCtx.companionPreview = res.preview;
            updateDesignerPreviews();
          });
        });
        tile.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            tile.click();
          }
        });
        if (menuPokemonField) {
          const pin = el("button", "osw-companion-menu-pin");
          pin.type = "button";
          pin.title = str("onigimon_menu_team_pin", "Show on Main Menu");
          pin.setAttribute("aria-label", str("onigimon_menu_team_pin", "Show on Main Menu") + ": " + pokemon.name);
          pin.setAttribute("aria-pressed", menuPokemonIds.indexOf(String(pokemon.id)) !== -1 ? "true" : "false");
          pin.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9"/><path d="M3 12h6m6 0h6"/><circle cx="12" cy="12" r="3"/></svg>';
          pin.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            bridge("osw:haptic:1");
            const id = String(pokemon.id);
            const next = menuPokemonIds.filter(function (value) { return value !== id; });
            if (menuPokemonIds.indexOf(id) === -1) next.push(id);
            setValue(menuPokemonField.id, next);
            paint();
          });
          tile.appendChild(pin);
        }
        grid.appendChild(tile);
      });
      grid.classList.toggle("is-empty", !(data.companions || []).length);
    }

    host.__syncCompanions = paint;
    paint();
    return host;
  }

  // ── Hexagon Land keys ─────────────────────────────────────────────────────

  function renderHexagonKeys(section) {
    const host = el("div", "osw-hexkeys");
    if (section.description) host.appendChild(el("div", "osw-row-desc", section.description));

    const banner = el("div", "osw-hexkeys-banner");
    const glyph = el("span", "osw-hexkeys-glyph");
    glyph.innerHTML = ISLAND_KEY_SVG;
    banner.appendChild(glyph);
    const cost = el("span", "osw-hexkeys-cost");
    banner.appendChild(cost);
    const balance = el("span", "osw-hexkeys-balance");
    banner.appendChild(balance);
    host.appendChild(banner);

    const nameField = (section.fields || []).filter(function (f) { return f.type === "text"; })[0];
    const nameRow = nameField ? renderText(nameField) : null;
    if (nameRow) host.appendChild(nameRow);

    const buy = el("button", "osw-btn osw-btn-primary osw-hexkeys-buy");
    buy.type = "button";
    buy.textContent = str("hexagon_keys_buy", "Buy Keys of the Island");
    buy.addEventListener("click", function () {
      bridge("osw:haptic:1");
      call("osw:games_action:hexagon_buy_keys").then(applyActionReply);
    });
    host.appendChild(buy);

    function paint() {
      const data = gamesCtx.hexagon || { owns_keys: false, coins: 0, cost: 0, affordable: false };
      cost.textContent = fmt(str("hexagon_keys_cost", "{cost} Hex Coins"), { cost: num(data.cost) });
      balance.textContent = data.owns_keys
        ? str("hexagon_keys_owned", "owned")
        : num(data.coins) + " / " + num(data.cost);
      buy.style.display = data.owns_keys ? "none" : "";
      buy.disabled = !data.affordable;
      // Naming the island is what the Keys unlock, so the field is inert until
      // they are owned rather than silently discarding what is typed.
      if (nameRow) {
        nameRow.classList.toggle("is-disabled", !data.owns_keys);
        const input = nameRow.querySelector("input");
        if (input) input.disabled = !data.owns_keys;
      }
    }

    host.__syncHexKeys = paint;
    paint();
    return host;
  }

  function refreshHexagonCards() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-hexkeys"), function (node) {
      if (node.__syncHexKeys) node.__syncHexKeys();
    });
  }

  const ISLAND_KEY_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/>' +
    '<circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/></svg>';

  // ── Bento games ───────────────────────────────────────────────────────────

  function renderBentoGames(_section) {
    const host = el("div", "osw-bento");
    host.__syncBento = function () { paintBentoGames(host); };
    paintBentoGames(host);
    return host;
  }

  function paintBentoGames(host) {
    host.innerHTML = "";
    (gamesCtx.bento || []).forEach(function (game) {
      const card = el("div", "osw-bento-card" + (game.detected ? " is-detected" : ""));

      const column = el("div", "osw-bento-thumb-col");
      const thumb = el("div", "osw-bento-thumb");
      if (game.accent) {
        thumb.style.backgroundColor = rgba(game.accent, 0.12);
        thumb.style.borderColor = rgba(game.accent, 0.24);
      }
      if (game.logo) {
        const img = document.createElement("img");
        img.src = game.logo;
        img.alt = "";
        thumb.appendChild(img);
      }
      column.appendChild(thumb);
      const pill = el("div", "osw-bento-pill", game.detected
        ? str("bento_detected", "Detected")
        : str("bento_not_found", "Not found"));
      if (game.detected && game.accent) {
        pill.style.backgroundColor = rgba(game.accent, 0.18);
        pill.style.borderColor = rgba(game.accent, 0.28);
      }
      column.appendChild(pill);
      card.appendChild(column);

      const body = el("div", "osw-bento-body");
      body.appendChild(el("div", "osw-bento-title", game.name));
      body.appendChild(el("div", "osw-row-desc", game.detected
        ? str("bento_detected_desc", "")
        : str("bento_missing_desc", "")));

      if (game.has_settings || game.has_open) {
        const actions = el("div", "osw-bento-actions");
        if (game.has_settings) actions.appendChild(bentoButton(str("settings", "Settings"), "bento_settings", game.id));
        if (game.has_open) actions.appendChild(bentoButton(str("open", "Open"), "bento_open", game.id));
        body.appendChild(actions);
      }
      card.appendChild(body);
      host.appendChild(card);
    });
  }

  /* Games launcher: the 2×3 grid on Gamification > Select Games. A card is a
     link to that game's own page, not a control — the on/off state it shows is
     read live from the game's own hero switch (values[card.toggle]), which is
     the same field that page edits, so the two can never disagree. */
  function renderGamesGallery(section) {
    const host = el("div", "osw-gamegrid");
    (section.cards || []).forEach(function (card) {
      const tile = el("button", "osw-gamecard" + (card.wide ? " is-wide" : ""));
      tile.type = "button";
      tile.setAttribute("data-game-card", card.id);
      if (card.accent) tile.style.setProperty("--osw-gamecard-accent", card.accent);

      const thumb = el("div", "osw-gamecard-thumb");
      if (card.accent) thumb.style.backgroundColor = rgba(card.accent, 0.14);
      if (card.image) {
        const img = document.createElement("img");
        img.src = card.image;
        img.alt = "";
        thumb.appendChild(img);
      }
      tile.appendChild(thumb);

      const body = el("div", "osw-gamecard-body");
      const head = el("div", "osw-gamecard-head");
      head.appendChild(el("div", "osw-gamecard-title", card.title));
      const state = el("span", "osw-gamecard-state");
      state.setAttribute("data-game-state", card.toggle || "");
      body.appendChild(head);
      if (card.desc) body.appendChild(el("div", "osw-gamecard-desc", card.desc));
      head.appendChild(state);
      tile.appendChild(body);

      tile.addEventListener("click", function () {
        bridge("osw:haptic:1");
        showPage(card.page);
      });
      host.appendChild(tile);
    });
    host.__syncGameCards = function () { paintGameCardStates(host); };
    paintGameCardStates(host);
    return host;
  }

  function paintGameCardStates(host) {
    Array.prototype.forEach.call(host.querySelectorAll("[data-game-state]"), function (node) {
      const toggleId = node.getAttribute("data-game-state");
      const on = !!values[toggleId];
      node.textContent = on ? str("on", "On") : str("off", "Off");
      node.classList.toggle("is-on", on);
      const tile = node.closest(".osw-gamecard");
      if (tile) tile.classList.toggle("is-on", on);
    });
  }

  function refreshGameCards() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-gamegrid"), function (node) {
      if (node.__syncGameCards) node.__syncGameCards();
    });
  }

  function bentoButton(label, action, gameId) {
    const button = el("button", "osw-btn", label);
    button.type = "button";
    button.addEventListener("click", function () {
      bridge("osw:haptic:1");
      call("osw:games_action:" + action + ":" + gameId).then(applyActionReply);
    });
    return button;
  }

  // ── preview painters ──────────────────────────────────────────────────────

  /* The level chip exactly as nook_level.get_chip_style_values() resolves it:
     the shared keys while Dynamic is off, the per-theme ones while it is on,
     each falling back to the game's own default. */
  function nookChipColors(vals, isDark) {
    const dynamic = vals.g_rl_dynamic_chip_colors === true;
    const defaults = (CTX.chipDefaults || {})[isDark ? "dark" : "light"] || {};
    function pick(role) {
      const base = "g_rl_chip_" + role;
      const raw = dynamic ? vals[base + (isDark ? "_dark" : "_light")] : vals[base];
      return raw ? qtColorToCss(raw) : qtColorToCss(defaults[
        role === "bg" ? "bg" : role === "progress" ? "progress" : "text"
      ] || "");
    }
    const bg = pick("bg");
    let text = pick("text");
    if (!text) {
      // The chip reader derives an unset text colour from the background's
      // lightness; the preview has to make the same call or it would show
      // white-on-white.
      const raw = dynamic
        ? vals["g_rl_chip_bg" + (isDark ? "_dark" : "_light")]
        : vals.g_rl_chip_bg;
      text = readableTextColor(qtColorRgb(raw || "") || (isDark ? "#000000" : "#ffffff"));
    }
    return { bg: bg, progress: pick("progress"), text: text };
  }

  /* The Profile Level page shows the same profile item as the Profile page.
     Its colour controls still come from this page, so only the chip palette is
     overridden; the markup, avatar, name, level source and selected Profile
     Type all come from the shared profile renderer. */
  PREVIEW_PAINTERS.profile_level = function (stage, vals, isDark) {
    stage.innerHTML = "";
    stage.classList.remove("osw-chipstage");

    const backdrop = el("div", "osw-profile-preview-backdrop");
    paintProfileBackdrop(backdrop, isDark);
    const profileItem = el("div", "osw-profile-preview-item");
    const chipColors = nookChipColors(vals, isDark);
    paintProfileItem(profileItem, isDark, {
      chipColors: chipColors,
      fillColor: chipColors.progress,
    });
    backdrop.appendChild(profileItem);
    stage.appendChild(backdrop);

    // The opacity slider belongs to whichever colour key this theme uses, so it
    // has to be resynced whenever the stage's theme changes.
    refreshAlphaSliders();
  };

  /* The Onigimon widget as the deck browser draws it: a coloured scene with the
     companion on it, fused to the stats panel underneath. Mirrors
     gamification/onigimon.py's `.onigimon-card` and onigiri_renderer.py's
     `.onigimon-top` / `.onigimon-bottom` rules. */
  PREVIEW_PAINTERS.onigimon_scene = function (stage, vals, isDark) {
    const color = /^#[0-9a-f]{6}$/i.test(String(vals.g_onigimon_scene_color || ""))
      ? vals.g_onigimon_scene_color
      : "#6ea96a";
    const blur = Math.max(0, Math.min(40, Number(vals.g_onigimon_scene_blur) || 0));
    const opacity = Math.max(0, Math.min(100, Number(vals.g_onigimon_scene_opacity) || 0)) / 100;
    const bottom = /^#[0-9a-f]{6}$/i.test(String(vals.g_onigimon_bottom_color || ""))
      ? vals.g_onigimon_bottom_color
      : (isDark ? "#2e2e2d" : "#efefec");
    const companion = gamesCtx.companionPreview || { name: "Onigimon", level: 1, sprite: "" };
    const columns = Math.max(1, Math.min(2, Number(onigimonPreviewColumns) || 1));
    const rows = Math.max(1, Math.min(4, Number(onigimonPreviewRows) || 2));
    const compact = rows === 1;
    const wide = columns === 2 && rows >= 2;
    const tall = rows >= 3;
    const extraTall = rows >= 4;

    stage.innerHTML = "";
    stage.classList.add("osw-onistage");
    stage.setAttribute("data-onigimon-columns", String(columns));
    stage.setAttribute("data-onigimon-rows", String(rows));
    // This stage sits on the deck browser's configured background just like
    // the live widget. It deliberately reuses the Main Background painter so
    // image/color, theme mode, blur, opacity and slideshow fallback stay in
    // lockstep with the Main Menu preview.
    designerPaintBackdrop(stage, vals, isDark);

    const card = el("div", "osw-onistage-card");
    card.classList.toggle("is-compact", compact);
    card.classList.toggle("is-wide", wide);
    card.classList.toggle("is-tall", tall);
    card.classList.toggle("is-extra-tall", extraTall);
    // Use the same grid footprint as the deck browser (230px columns, 120px
    // rows, 20px gaps), capped by the preview stage on narrow dialogs.
    card.style.width = (columns * 230 + (columns - 1) * 20) + "px";
    card.style.height = (rows * 120 + (rows - 1) * 20) + "px";

    const top = el("div", "osw-onistage-top");
    // The live widget's radial wash — lighter towards the top-left, darker at
    // the far corner — computed here because this webview has no color-mix().
    top.style.background = "radial-gradient(circle at 22% 32%, " +
      mix(color, "#ffffff", 0.92) + " 0%, " + color + " 70%, " +
      mix(color, "#000000", 0.90) + " 100%)";

    const sceneMode = vals.g_onigimon_scene_mode || "preset";
    const scenePath = sceneMode === "custom"
      ? vals.g_onigimon_scene_image
      : (vals.g_onigimon_scene_preset
        || "system_files/gamification_images/onigimon/scenarios/nature/default.png");
    const image = sceneMode === "color"
      ? ""
      : (String(scenePath || "").indexOf("system_files/") === 0
        ? (CTX.addonBase || "") + scenePath
        : imageUrl("onigimon_bg", scenePath));
    if (image) {
      const backdrop = el("div", "osw-onistage-backdrop");
      backdrop.style.backgroundImage = "url('" + image + "')";
      backdrop.style.filter = "blur(" + blur + "px)";
      backdrop.style.opacity = opacity.toFixed(2);
      top.appendChild(backdrop);
    }

    const sprite = el("div", "osw-onistage-sprite");
    const wantsAnimation = vals.g_onigimon_sprite_motion === "gif";
    let spriteUrls = wantsAnimation ? companion.animatedSprites : companion.staticSprites;
    if (!Array.isArray(spriteUrls)) spriteUrls = [];
    spriteUrls = spriteUrls.filter(function (url, index) {
      return url && spriteUrls.indexOf(url) === index;
    });
    if (!spriteUrls.length && companion.sprite) spriteUrls.push(companion.sprite);
    if (spriteUrls.length) {
      const img = document.createElement("img");
      img.src = spriteUrls[0];
      img.__fallbacks = spriteUrls.slice(1);
      img.addEventListener("error", function () {
        const next = img.__fallbacks.shift();
        if (next) img.src = next;
        else img.style.display = "none";
      });
      img.alt = "";
      sprite.appendChild(img);
    } else {
      sprite.textContent = "Onigimon";
    }
    top.appendChild(sprite);

    const info = el("div", "osw-onistage-info");
    const name = el("div", "osw-onistage-name", companion.name || "Onigimon");
    const level = el("div", "osw-onistage-level",
      str("onigimon_level", "Level") + " " + (companion.level || 1));
    info.appendChild(name);
    info.appendChild(level);
    card.appendChild(top);

    // The real 1-row widget is its compact scene: 1 column shows only the
    // companion, while 2 columns has enough room for name and level.
    if (compact) {
      name.style.color = isDark ? "#ffffff" : "#000000";
      level.style.color = isDark ? "rgba(255,255,255,0.82)" : "rgba(0,0,0,0.68)";
      top.appendChild(info);
      info.classList.toggle("is-hidden", columns === 1);
      stage.appendChild(card);
      return;
    }

    const panel = el("div", "osw-onistage-bottom");
    panel.style.background = bottom;
    const meterFg = readableTextColor(bottom);
    panel.style.color = meterFg;
    name.style.color = meterFg;
    level.style.color = rgba(meterFg, 0.68);
    panel.appendChild(info);
    const metersHost = el("div", "osw-onistage-meters");
    const needs = companion.needs || {};
    function previewNumber(value, fallback) {
      const number = Number(value);
      return isNaN(number) ? fallback : number;
    }
    [
      ["HP", previewNumber(needs.health, 100), "#08c46b", previewNumber(companion.hp, 20)],
      [str("onigimon_status_happiness", "Happiness"), previewNumber(needs.happiness, 62), "#ffbd55", previewNumber(needs.happiness, 31)],
      [str("onigimon_status_hygiene", "Hygiene"), previewNumber(needs.hygiene, 80), "#21b7d6", previewNumber(needs.hygiene, 40)],
      [str("onigimon_status_training", "Training"), previewNumber(needs.training, 45), "#c866e5", previewNumber(needs.training, 30)],
      [str("onigimon_status_hunger", "Hunger"), previewNumber(needs.hunger, 26), "#f45bb3", previewNumber(needs.hunger, 26)],
    ].forEach(function (meter) {
      const row = el("div", "osw-onistage-meter");
      const meterName = el("span", "osw-onistage-meter-name", String(meter[0]).toUpperCase());
      const meterValue = el("span", "osw-onistage-meter-value", meter[3]);
      meterName.style.color = meterFg;
      meterValue.style.color = meterFg;
      const meterTrack = el("span", "osw-onistage-meter-track");
      meterTrack.style.background = rgba(meterFg, 0.14);
      const meterFill = el("span", "osw-onistage-meter-fill");
      meterFill.style.width = meter[1] + "%";
      meterFill.style.background = meter[2];
      meterTrack.appendChild(meterFill);
      row.appendChild(meterName);
      row.appendChild(meterValue);
      row.appendChild(meterTrack);
      metersHost.appendChild(row);
    });
    panel.appendChild(metersHost);

    function appendQuickStat(host, label, value) {
      const item = el("div", "osw-onistage-quick-stat");
      item.appendChild(el("span", null, label));
      item.appendChild(el("b", null, String(previewNumber(value, 0))));
      host.appendChild(item);
    }

    if (tall) {
      const bondLevel = Math.max(1, previewNumber(companion.bondLevel, 1));
      const bondXp = Math.max(0, previewNumber(companion.bondXp, 0));
      const bondTarget = Math.max(1, bondLevel * 40);
      const growth = el("div", "osw-onistage-growth");
      const growthHead = el("div", "osw-onistage-growth-head");
      growthHead.appendChild(el("span", null, str("onigimon_bond", "Bond")));
      growthHead.appendChild(el("b", null,
        str("onigimon_level_short", "Lv") + " " + bondLevel));
      growthHead.appendChild(el("em", null, bondXp + "/" + bondTarget + " XP"));
      growth.appendChild(growthHead);
      const growthTrack = el("div", "osw-onistage-growth-track");
      growthTrack.style.background = rgba(meterFg, 0.14);
      const growthFill = el("i", null);
      growthFill.style.width = Math.max(0, Math.min(100, (bondXp / bondTarget) * 100)) + "%";
      growthTrack.appendChild(growthFill);
      growth.appendChild(growthTrack);
      panel.appendChild(growth);

      const quickStats = el("div", "osw-onistage-quick-stats");
      appendQuickStat(quickStats, str("onigimon_streak", "Streak"), companion.streak);
      appendQuickStat(quickStats, str("onigimon_items", "Items"), companion.itemCount);
      panel.appendChild(quickStats);
    }

    if (extraTall) {
      const battleStats = el("div", "osw-onistage-battle-stats");
      appendQuickStat(battleStats, str("onigimon_attack", "Attack"), companion.attack);
      appendQuickStat(battleStats, str("onigimon_defense", "Defense"), companion.defense);
      appendQuickStat(battleStats, str("onigimon_speed", "Speed"), companion.speed);
      panel.appendChild(battleStats);
    }
    card.appendChild(panel);
    stage.appendChild(card);
  };

  /* Mochi uses the same payload shape as MochiMessenger._dispatch_notification
     and the same factory as the live reviewer notification. */
  PREVIEW_PAINTERS.mochi_message = function (stage, vals, isDark) {
    const custom = vals.g_mochi_icon_choice === "custom" && vals.g_mochi_custom_icon;
    const customUrl = custom ? imageUrl("mochi_icon", vals.g_mochi_custom_icon) : "";
    const textColor = vals.g_mochi_text_color || (isDark ? "#ffffff" : "#2c2c2c");
    const fontOption = ((fieldById.g_mochi_font || {}).options || []).filter(function (option) {
      return option.value === vals.g_mochi_font;
    })[0];
    const payload = {
      id: "mochi_message",
      name: String(vals.g_mochi_title_name || "").trim()
        || str("mochi_title_placeholder", "Mochi says…"),
      description: str("mochi_font_sample", "Keep going!"),
      icon: "🍡",
      hideTitle: !!vals.g_mochi_hide_title,
      textColorLight: textColor,
      textColorDark: textColor
    };
    if (customUrl) payload.iconImage = customUrl;
    if (fontOption && fontOption.family) payload.fontFamily = fontOption.family;

    paintLiveNotification(stage, vals, isDark, payload);
  };

  const FIELD_RENDERERS = {
    toggle: renderToggle,
    notif_position: renderNotifPosition,
    game_choice: renderGameChoice,
    scenario_picker: renderScenarioPicker,
    message_list: renderMessageList,
    button_order: renderButtonOrder,
    image: renderImage,
    image_list: renderImageList,
    color_pair: renderColorPair,
    mode_card: renderModeCard,
    choice: renderChoice,
    select: renderSelect,
    number: renderNumber,
    slider: renderSlider,
    duration: renderDuration,
    text: renderText,
    color: renderColor,
    font: renderFont,
    icon: renderIcon,
    language: renderLanguage,
    action: renderAction,
    note: renderNote
  };

  // ── section renderers ──────────────────────────────────────────────────────

  /* The immersion ladder (Modes page). Focus/Flow/Zen contain one another, which
     the schema already encodes as `cascade` rules. A single slider makes that
     containment the only gesture: dragging past a tick turns on that level and
     everything below it, instead of hunting through three separate switches.

     Same anti-flicker discipline as the Languages hero: the DOM is built once
     and only classes / the slider value change, so nothing reflows on drag. */
  function renderLadder(section) {
    const fields = (section.fields || []).slice().sort(function (a, b) {
      return (a.level || 0) - (b.level || 0);
    });
    const maxLevel = fields.length;

    const host = el("div", "osw-ladder");
    host.setAttribute("data-section", section.id || "");

    const head = el("div", "osw-ladder-head");
    const headTop = el("div", "osw-ladder-head-top");
    const headText = el("div", "osw-ladder-head-text");
    headText.appendChild(el("div", "osw-ladder-eyebrow", str("immersion", "Immersion")));
    const stateLabel = el("div", "osw-ladder-state");
    const stateCaption = el("div", "osw-ladder-caption");
    headText.appendChild(stateLabel);
    headText.appendChild(stateCaption);
    headTop.appendChild(headText);

    // Only the active level's notes show here — the three modes' bullets
    // used to sit stacked in one big block below; showing just the one that
    // is actually on keeps this from turning back into a wall of text.
    const notesList = el("ul", "osw-ladder-notes");
    headTop.appendChild(notesList);
    head.appendChild(headTop);

    // Same capsule track as the Blur/Opacity sliders (osw-slider-*), so the
    // ladder reads as "a slider" rather than a bespoke control. It just steps
    // in wholes across maxLevel+1 stops (0 is off) instead of a free 0-100.
    const card = el("div", "osw-slider-card osw-ladder-slider-card");
    card.setAttribute("role", "slider");
    card.setAttribute("aria-label", str("immersion", "Immersion"));
    card.setAttribute("tabindex", "0");

    // Every element that marks a position on the track — the fill's leading
    // edge, the thumb's center, each level's tick — has to land on the exact
    // same x for a given level, or they read as misaligned. CAP_INSET (the
    // track's 14px corner radius, minus half the 5px thumb) keeps that shared
    // position clear of the rounded ends, so nothing ever pokes outside them.
    var CAP_INSET = 11.5;
    function stopExpr(pct) {
      return "max(" + CAP_INSET + "px, min(" + pct + "%, calc(100% - " + CAP_INSET + "px)))";
    }

    const track = el("div", "osw-slider-track");
    const fill = el("div", "osw-slider-fill");
    const marks = el("div", "osw-ladder-track-marks");
    fields.forEach(function (field) {
      const mark = el("span", "osw-ladder-track-mark");
      mark.style.left = stopExpr((field.level / maxLevel) * 100);
      marks.appendChild(mark);
    });
    const thumb = el("div", "osw-slider-thumb");
    track.appendChild(fill);
    track.appendChild(marks);
    track.appendChild(thumb);
    card.appendChild(track);
    head.appendChild(card);
    host.appendChild(head);

    function currentLevel() {
      let level = 0;
      fields.forEach(function (field) {
        if (values[field.id]) level = field.level;
      });
      return level;
    }

    function setLevel(level) {
      fields.forEach(function (field) {
        setValue(field.id, field.level <= level);
      });
    }

    function paint(level) {
      const pct = (level / maxLevel) * 100;
      const thumbStop = stopExpr(pct);
      // The fill always reaches CAP_INSET past the thumb's own clamped stop,
      // so the thumb reads as nested inside the filled capsule (with room to
      // its right) at every level, not sitting right on the fill/track seam.
      // At max level thumbStop is already CAP_INSET short of 100%, so this
      // lands exactly on 100% — a fully colored, edge-to-edge track.
      fill.style.width = "min(calc(" + thumbStop + " + " + CAP_INSET + "px), 100%)";
      thumb.style.left = "calc(" + thumbStop + " - 2.5px)";
    }

    function levelFromClientX(clientX) {
      const rect = track.getBoundingClientRect();
      if (rect.width <= 0) return currentLevel();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.round(ratio * maxLevel);
    }

    let isDragging = false;

    function onPointerDown(e) {
      isDragging = true;
      card.classList.add("is-dragging");
      setLevel(levelFromClientX(e.clientX));
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    }
    function onPointerMove(e) {
      if (isDragging) setLevel(levelFromClientX(e.clientX));
    }
    function onPointerUp() {
      isDragging = false;
      card.classList.remove("is-dragging");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }
    track.addEventListener("pointerdown", onPointerDown);

    card.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowUp") setLevel(Math.min(maxLevel, currentLevel() + 1));
      else if (e.key === "ArrowLeft" || e.key === "ArrowDown") setLevel(Math.max(0, currentLevel() - 1));
      else return;
      e.preventDefault();
    });

    function refresh() {
      const level = currentLevel();
      const activeField = fields.filter(function (field) { return field.level === level; })[0] || null;

      stateLabel.textContent = activeField
        ? activeField.label
        : str("immersion_off", "Off");
      stateCaption.textContent = activeField
        ? (activeField.desc || "")
        : str("immersion_off_caption", "Anki looks the way it always does.");
      host.classList.toggle("is-off", level === 0);

      notesList.innerHTML = "";
      const notes = (activeField && activeField.notes || []).filter(function (note) { return !!note; });
      notes.forEach(function (note) { notesList.appendChild(el("li", null, note)); });
      notesList.classList.toggle("is-empty", notes.length === 0);

      card.setAttribute("aria-valuemin", "0");
      card.setAttribute("aria-valuemax", String(maxLevel));
      card.setAttribute("aria-valuenow", String(level));
      card.setAttribute("aria-valuetext", activeField ? activeField.label : str("immersion_off", "Off"));
      paint(level);
    }

    host.__refreshLadder = refresh;
    refresh();
    return host;
  }

  function renderFontRole(section) {
    const roleKey = section.role_key || (section.id || "").replace("font_", "");
    const fallbackRoleKey = section.fallback_role_key || "";

    const host = el("div", "osw-font-role-section");
    host.setAttribute("data-role-key", roleKey);

    const controlsCol = el("div", "osw-font-role-controls");
    const fieldsWrap = el("div", "osw-fields");
    (section.fields || []).forEach(function (field) {
      const renderer = FIELD_RENDERERS[field.type];
      if (!renderer) return;
      const node = renderer(field);
      node.setAttribute("data-field-host", field.id);
      fieldsWrap.appendChild(node);
    });
    controlsCol.appendChild(fieldsWrap);
    host.appendChild(controlsCol);

    const previewCol = el("div", "osw-font-role-preview");
    const card = el("div", "osw-font-preview-card");
    card.setAttribute("id", "oswFontPreview_" + roleKey);

    const header = el("div", "osw-font-preview-header");
    const badge = el("span", "osw-font-preview-badge", str("font_preview", "Preview"));
    header.appendChild(badge);

    const modeSwitcher = el("div", "osw-font-preview-modes");
    let currentPreviewMode = CTX.dark ? "dark" : "light";

    const btnLight = el("button", "osw-font-preview-mode-btn" + (currentPreviewMode === "light" ? " is-active" : ""));
    btnLight.type = "button";
    btnLight.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg><span>' + str("light_mode", "Light") + '</span>';

    const btnDark = el("button", "osw-font-preview-mode-btn" + (currentPreviewMode === "dark" ? " is-active" : ""));
    btnDark.type = "button";
    btnDark.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg><span>' + str("dark_mode", "Dark") + '</span>';

    modeSwitcher.appendChild(btnLight);
    modeSwitcher.appendChild(btnDark);
    header.appendChild(modeSwitcher);
    card.appendChild(header);

    const body = el("div", "osw-font-preview-body");
    const sampleText = el("div", "osw-font-preview-text", str("font_preview_text", "The quick brown fox jumps over the lazy dog. 1234567890"));

    body.appendChild(sampleText);
    card.appendChild(body);
    previewCol.appendChild(card);
    host.appendChild(previewCol);

    function updatePreview() {
      const fontKey = values["onigiri_font_" + roleKey] || "sync";
      const colorRoleKey = fallbackRoleKey || roleKey;
      const lightColor = values["font_color_light_" + colorRoleKey] || "#1f2933";
      const darkColor = values["font_color_dark_" + colorRoleKey] || "#f4f4f5";

      const fontField = fieldById["onigiri_font_" + roleKey];
      const resolvedFontKey = fontKey === "sync" && fallbackRoleKey
        ? (values["onigiri_font_" + fallbackRoleKey] || "system")
        : fontKey;
      // In Advanced mode family sync and component size are independent. The
      // Simple UI never renders these component cards and continues to use
      // the three shared typography scales.
      const fontSize = SETTINGS_MODE_PARITY || settingsComplexity === "advanced"
        ? (values["onigiri_font_size_" + roleKey] || 14)
        : (values["onigiri_font_size_" + fallbackRoleKey] || 14);
      let family = "";
      if (fontField && fontField.options) {
        const opt = fontField.options.filter(function (o) { return o.value === resolvedFontKey; })[0];
        if (opt && opt.family) family = opt.family;
      }
      if (!family && resolvedFontKey !== "system") family = resolvedFontKey;

      const isLight = currentPreviewMode === "light";
      const color = fontFieldColor(values, "onigiri_font_" + roleKey, !isLight) || (isLight ? lightColor : darkColor);

      card.setAttribute("data-preview-mode", currentPreviewMode);

      sampleText.style.fontFamily = family ? ('"' + family + '", sans-serif') : 'inherit';
      sampleText.style.fontSize = fontSize + "px";
      sampleText.style.color = color;
    }

    btnLight.addEventListener("click", function () {
      currentPreviewMode = "light";
      btnLight.classList.add("is-active");
      btnDark.classList.remove("is-active");
      updatePreview();
    });

    btnDark.addEventListener("click", function () {
      currentPreviewMode = "dark";
      btnDark.classList.add("is-active");
      btnLight.classList.remove("is-active");
      updatePreview();
    });

    host.__updateFontPreview = updatePreview;
    updatePreview();
    return host;
  }

  function renderFontRoles(section) {
    const stack = el("div", "osw-font-roles-stack");
    (section.fontRoles || []).forEach(function (role) {
      const card = el("div", "osw-font-role-group");
      card.appendChild(el("div", "osw-section-title", role.title || ""));
      const fieldIds = role.field_ids || [];
      card.appendChild(renderFontRole({
        id: role.id,
        role_key: role.role_key,
        fallback_role_key: role.fallback_role_key,
        fields: (section.fields || []).filter(function (field) {
          return fieldIds.indexOf(field.id) !== -1;
        })
      }));
      stack.appendChild(card);
    });
    return stack;
  }

  /* Themes page: two card grids (yours, official) over a split light/dark
     swatch, plus import/export/reset. Applying a theme touches config/col.conf
     keys most of which have no WebUI field at all yet (Colors, Backgrounds,
     Sidebar are still legacy pages) — Python owns the whole theme and returns
     a complete bound-value snapshot so every Settings preview repaints from
     the same palette (see dialog.py's _cmd_theme_apply `preview`). */
  function applyThemeRefresh(refresh, preview) {
    const updates = Object.assign({}, refresh || {}, preview || {});
    const ids = Object.keys(updates).filter(function (id) { return id in values; });
    if (!ids.length) return;

    deferringPreviewRefresh = true;
    try {
      ids.forEach(function (id) {
        values[id] = updates[id];
        // A pre-theme value waiting in the debounce queue must not overwrite
        // the value Python just applied as part of the selected theme.
        delete pending[id];
        syncField(id);
      });
    } finally {
      deferringPreviewRefresh = false;
    }
    refreshSettingsPreviews();
  }

  function promptThemeName(callback) {
    const overlay = el("div", "osw-theme-prompt-overlay");
    const card = el("div", "osw-theme-prompt-card");
    card.appendChild(el("div", "osw-theme-prompt-title", str("theme_export_name_title", "Name this theme")));
    const input = document.createElement("input");
    input.type = "text";
    input.className = "osw-text-input";
    input.placeholder = str("theme_export_name_placeholder", "Theme name");
    card.appendChild(input);
    const row = el("div", "osw-theme-prompt-row");
    const cancelBtn = el("button", "osw-btn", str("cancel", "Cancel"));
    cancelBtn.type = "button";
    const okBtn = el("button", "osw-btn osw-btn-primary", str("save", "Save"));
    okBtn.type = "button";
    row.appendChild(cancelBtn);
    row.appendChild(okBtn);
    card.appendChild(row);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    input.focus();

    function close(value) {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      document.removeEventListener("keydown", onKey, true);
      callback(value);
    }
    function onKey(event) {
      if (event.key === "Escape") { event.preventDefault(); close(null); }
      else if (event.key === "Enter") { event.preventDefault(); close(input.value.trim()); }
    }
    document.addEventListener("keydown", onKey, true);
    overlay.addEventListener("mousedown", function (event) {
      if (event.target === overlay) close(null);
    });
    cancelBtn.addEventListener("click", function () { close(null); });
    okBtn.addEventListener("click", function () { close(input.value.trim()); });
  }

  /* Gallery-only colour cards. The settings pages keep their compact row
     controls, while Gallery presents the same bindings as a visual catalogue
     modelled on the Themes grid. Every value is labelled as #RRGGBB even when
     its stored form is rgba() or Qt's #AARRGGBB. */
  function renderColorGallery(section, _page) {
    const host = el("div", "osw-color-gallery");
    const grid = el("div", "osw-color-gallery-grid");
    host.appendChild(grid);

    function displayHex(value) {
      let hex = String(cssColorToHex(value) || "").trim();
      const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(hex);
      if (short) {
        hex = "#" + short[1] + short[1] + short[2] + short[2] + short[3] + short[3];
      }
      return /^#[0-9a-f]{6}$/i.test(hex) ? hex.toUpperCase() : "#000000";
    }

    function targetsFor(field) {
      if (field.type === "color_pair") return imageTargets(field);
      return [{ id: field.id, role: "single", label: "", key: "" }];
    }

    function fieldFallback(field, target) {
      if (field.type === "color_pair") return pairColorFallback(field, target);
      return iconColorFallback(field) || field.default || "#000000";
    }

    function paint() {
      grid.innerHTML = "";
      (section.fields || []).forEach(function (field) {
        if (field.type !== "color" && field.type !== "color_pair") return;

        const card = el("article", "osw-color-card");
        card.setAttribute("data-color-field", field.id);

        const targets = targetsFor(field);
        const art = el(
          "div",
          "osw-color-card-art" + (targets.length > 1 ? " is-split" : "")
        );

        targets.forEach(function (target) {
          const single = field.type === "color_pair" && !field.lightField && !field.darkField;
          const key = field.type === "color"
            ? field.id
            : (single
              ? field.id
              : (target.role === "single" ? (field.singleField || field.lightField) : target.id));
          const value = values[key] || "";
          const fallback = fieldFallback(field, target);
          const shown = value || fallback || "#000000";
          const displayed = field.chipRole ? qtColorToCss(shown) : shown;
          const hex = displayHex(displayed);

          const swatch = el(
            "button",
            "osw-color-card-swatch" + (!value && fallback ? " is-default" : "")
          );
          swatch.type = "button";
          swatch.style.background = displayed || hex;
          swatch.style.color = readableTextColor(hex);
          swatch.setAttribute("data-slot", target.role);

          if (target.role === "light" || target.role === "dark") {
            const role = el("span", "osw-color-card-role");
            const chromeIcons = CTX.chromeIcons || {};
            role.innerHTML = target.role === "light"
              ? (chromeIcons.sun || OSW_SUN_ICON)
              : (chromeIcons.moon || OSW_MOON_ICON);
            role.title = target.role === "light"
              ? str("theme_light_mode", "Light")
              : str("theme_dark_mode", "Dark");
            swatch.appendChild(role);
          }
          swatch.appendChild(el("span", "osw-color-card-hex", hex));
          swatch.setAttribute(
            "aria-label",
            (field.label || str("color", "Color")) + " " +
              (target.label ? target.label + " " : "") + hex
          );
          swatch.addEventListener("click", function () {
            bridge("osw:haptic:1");
            openColorPickerById(
              key, value || (field.chipRole ? cssColorToHex(displayed) : shown)
            );
          });
          art.appendChild(swatch);
        });

        card.appendChild(art);
        const foot = el("div", "osw-color-card-foot");
        const name = field.desc || field.label || str("color", "Color");
        foot.appendChild(el("div", "osw-color-card-name", name));
        if (field.desc && field.label && field.desc !== field.label) {
          foot.appendChild(el("div", "osw-color-card-sub", field.label));
        }
        card.appendChild(foot);
        grid.appendChild(card);
      });
    }

    host.__syncColorGallery = paint;
    paint();
    return host;
  }

  function renderThemeStyle(section) {
    const field = (section.fields || [])[0];
    const host = el("div", "osw-theme-style-grid");
    if (!field) return host;

    (field.options || []).forEach(function (option) {
      const card = el("button", "osw-theme-style-card");
      card.type = "button";
      card.setAttribute("data-theme-style", option.value);
      card.setAttribute("data-field", field.id);
      card.setAttribute("data-field-type", "choice");

      const decoration = el("span", "osw-theme-style-decoration");
      decoration.setAttribute("aria-hidden", "true");
      if (option.value === "things3") {
        decoration.textContent = "米";
      } else if (option.value === "shima") {
        decoration.classList.add("is-shima");
        decoration.innerHTML =
          '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" aria-hidden="true">' +
          '<path d="M0 0h24v24H0z" fill="none"/>' +
          '<rect width="12" height="20" x="6" y="2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" rx="2"/>' +
          '</svg>';
      } else if (option.value === "classic") {
        const iconUrl = (CTX.iconAssets || {})["system:onigiri.svg"] || "";
        decoration.classList.add("is-onigiri");
        decoration.style.setProperty(
          "--osw-theme-style-decoration-image", "url(" + iconUrl + ")"
        );
      }
      card.appendChild(decoration);

      const copy = el("span", "osw-theme-style-copy");
      const title = el("span", "osw-theme-style-title");
      title.appendChild(el("span", "osw-theme-style-name", option.label));
      if (option.value === "things3") {
        title.appendChild(el("span", "osw-theme-style-credit", "by Max"));
      }
      copy.appendChild(title);
      copy.appendChild(el("span", "osw-theme-style-desc", option.sub || ""));
      card.appendChild(copy);

      card.addEventListener("click", function () {
        bridge("osw:haptic:1");
        setValue(field.id, option.value);
      });
      host.appendChild(card);
    });

    host.__refreshThemeStyle = function () {
      Array.prototype.forEach.call(host.querySelectorAll("[data-theme-style]"), function (card) {
        const selected = card.getAttribute("data-theme-style") === String(values[field.id]);
        card.classList.toggle("is-selected", selected);
        card.setAttribute("aria-pressed", selected ? "true" : "false");
      });
    };
    host.__refreshThemeStyle();
    return host;
  }

  function refreshThemeStyleCards() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-theme-style-grid"), function (host) {
      if (host.__refreshThemeStyle) host.__refreshThemeStyle();
    });
  }

  const THINGS_PREVIEW_WIDTH = 1440;
  const THINGS_PREVIEW_HEIGHT = 900;

  function thingsPreviewJson(value) {
    return JSON.stringify(value == null ? null : value)
      .replace(/</g, "\\u003c")
      .replace(/>/g, "\\u003e")
      .replace(/&/g, "\\u0026");
  }

  function thingsPreviewCssValue(value, fallback) {
    const clean = String(value || fallback || "").replace(/[<>{};]/g, "").trim();
    return clean || fallback;
  }

  function buildThingsPreviewDocument(mode) {
    const asset = CTX.thingsPreview || {};
    const decks = Array.isArray(asset.decks) && asset.decks.length ? asset.decks : [
      { did: 1, name: "Japanese", depth: 0, new: 38, learn: 0, review: 24, done: 18 },
      { did: 2, name: "Biology", depth: 0, new: 17, learn: 0, review: 12, done: 4 },
      { did: 3, name: "Design notes", depth: 0, new: 8, learn: 0, review: 0, done: 0 },
    ];
    const standing = Object.assign({
      due: 57, new: 63, learn: 4, today: 42, total: 915, streak: 8,
      last14: [2, 5, 4, 9, 7, 12, 8, 14, 11, 18, 16, 23, 20, 28],
      states: { new: 25, learning: 4, relearning: 6, young: 54, mature: 2 },
    }, asset.standing || {});
    const configuredMainLight = String(
      values.things_main_background_light || ""
    ).toLowerCase() === "#f6f3ec" ? "" : values.things_main_background_light;
    const configuredMainDark = String(
      values.things_main_background_dark || ""
    ).toLowerCase() === "#0b0c0f" ? "" : values.things_main_background_dark;
    const palette = {
      light: {
        bg: thingsPreviewCssValue(
          configuredMainLight,
          values.theme_bg_light || "#eeeeee"
        ),
        inset: thingsPreviewCssValue(values.theme_inset_light, "#ffffff"),
        fg: thingsPreviewCssValue(values.theme_fg_light, "#212121"),
        subtle: thingsPreviewCssValue(values.theme_subtle_light, "#757575"),
        border: thingsPreviewCssValue(values.theme_border_light, "#e0e0e0"),
        accent: thingsPreviewCssValue(values.theme_accent_light, "#0077c8"),
      },
      dark: {
        bg: thingsPreviewCssValue(
          configuredMainDark,
          values.theme_bg_dark || "#171717"
        ),
        inset: thingsPreviewCssValue(values.theme_inset_dark, "#2c2c2c"),
        fg: thingsPreviewCssValue(values.theme_fg_dark, "#e0e0e0"),
        subtle: thingsPreviewCssValue(values.theme_subtle_dark, "#9e9e9e"),
        border: thingsPreviewCssValue(values.theme_border_dark, "#424242"),
        accent: thingsPreviewCssValue(values.theme_accent_dark, "#0077c8"),
      },
    };
    const variables = ["light", "dark"].map(function (key) {
      return Object.keys(palette[key]).map(function (token) {
        return "--rf-" + key + "-" + token + ":" + palette[key][token] + ";";
      }).join("");
    }).join("");
    const sidebarVariables =
      "--rf-sidebar-light-bg:" + thingsPreviewCssValue(
        values.things_sidebar_background_light, palette.light.bg
      ) + ";" +
      "--rf-sidebar-dark-bg:" + thingsPreviewCssValue(
        values.things_sidebar_background_dark, palette.dark.bg
      ) + ";";
    const currentPalette = palette[mode];
    const countColors = {};
    ["new", "learn", "review"].forEach(function (role) {
      countColors[role] = ((asset.palettes || {})[mode] || {})["--" + role + "-count-bubble-bg"] || currentPalette.accent;
    });
    const activeColors = {
      new: thingsPreviewCssValue(values.things_active_new_color, countColors.new),
      learning: thingsPreviewCssValue(values.things_active_learning_color, countColors.learn),
      relearning: thingsPreviewCssValue(values.things_active_relearning_color, countColors.learn),
      young: thingsPreviewCssValue(values.things_active_young_color, countColors.review),
      mature: thingsPreviewCssValue(values.things_active_mature_color, currentPalette.accent),
    };
    const activeVariables = Object.keys(activeColors).map(function (key) {
      return "--rf-" + mode + "-active-" + key + ":" + activeColors[key] + ";";
    }).join("");
    const heatmapColor = thingsPreviewCssValue(
      values.things_heatmap_color, currentPalette.accent
    );
    const dashboardVariables =
      "--rf-heatmap-color:" + heatmapColor + ";" +
      "--rf-weekly-reviews-color:" + thingsPreviewCssValue(
        values.things_weekly_reviews_color, currentPalette.accent
      ) + ";" +
      "--rf-progress-color:" + thingsPreviewCssValue(
        values.things_progress_color, currentPalette.accent
      ) + ";" +
      "--rf-hm-l1:color-mix(in srgb," + heatmapColor + " 22%,var(--rf-paper))!important;" +
      "--rf-hm-l2:color-mix(in srgb," + heatmapColor + " 45%,var(--rf-paper))!important;" +
      "--rf-hm-l3:color-mix(in srgb," + heatmapColor + " 72%,var(--rf-paper))!important;" +
      "--rf-hm-l4:" + heatmapColor + "!important;";
    const clampPercent = function (value, fallback) {
      const number = Number(value);
      return Math.max(0, Math.min(100, Number.isFinite(number) ? number : fallback));
    };
    const backgroundUrl = imageUrl("main_bg", values.things_background_image);
    const safeBackgroundUrl = String(backgroundUrl || "")
      .replace(/\\/g, "%5C").replace(/\"/g, "%22");
    const surfaceVariables = ["sidebar", "decks", "widgets"].map(function (surface) {
      const prefix = "things_" + (surface === "decks" ? "deck" : surface);
      const opacity = clampPercent(values[prefix + "_opacity"], 100);
      const blurIntensity = clampPercent(values[prefix + "_blur"], 0);
      const visibleOpacity = Math.min(opacity, 100 - blurIntensity * 0.3);
      const blur = blurIntensity * 0.24;
      return "--rf-" + surface + "-opacity:" + visibleOpacity + "%;" +
        "--rf-" + surface + "-blur:" + blur + "px;";
    }).join("") + (safeBackgroundUrl
      ? '--rf-background-image:url("' + safeBackgroundUrl + '");'
      : "--rf-background-image:none;");
    const showReviewChart = values.things_show_review_chart !== false;
    const showHeatmap = values.things_show_heatmap !== false;
    const previewClasses = [
      showReviewChart ? "" : "preview-hide-review",
      showHeatmap ? "" : "preview-hide-heatmap",
    ].filter(Boolean).join(" ");
    const scriptEnd = "</scr" + "ipt>";
    const safeScript = function (source) {
      return String(source || "").replace(/<\/script/gi, "<\\/script");
    };
    const seed =
      "window.__baOpts={cmdk:false,deckList:{startup:'expanded',dragMove:false}," +
        "sidebar:{hero:" + (values.things_show_due !== false) + ",heroStat:'due'," +
        "donut:" + (values.things_show_active_cards !== false) + "," +
        "tasks:" + (values.things_show_tasks !== false) + "," +
        "progress:" + (values.things_show_progress !== false) + "}};" +
      "window.__baDeckTree=" + thingsPreviewJson(decks) + ";" +
      "window.__baStandingData=" + thingsPreviewJson(standing) + ";" +
      "window.__baTasksData=" + thingsPreviewJson(asset.tasks || []) + ";" +
      "window.__baDeckIconBase=" + thingsPreviewJson(asset.deckIconBase || "") + ";";
    let analytics = asset.analyticsHtml || "";
    if (!analytics) {
      analytics = '<section class="ba-practice"><div class="ba-analytics">' +
        '<section class="ba-review-chart"><div class="ba-analytics-head"><span>Weekly reviews</span><strong>915<small> total</small></strong></div>' +
        '<svg class="ba-review-chart-svg" viewBox="0 0 640 150" preserveAspectRatio="none"><path d="M12,116 L90,104 L170,108 L250,80 L330,88 L410,58 L500,66 L628,24 L628,116 L12,116 Z" class="ba-chart-area"></path><path d="M12,116 L90,104 L170,108 L250,80 L330,88 L410,58 L500,66 L628,24" class="ba-chart-line"></path></svg></section>' +
        '<section class="ba-heatmap-card"><div class="rf-heatmap"><div class="rf-hm-head"><span class="rf-hm-title">Review activity</span><span class="rf-hm-stats"><b>42</b> today · <b>8</b> day streak</span></div></div></section>' +
      '</div></section>';
    }
    return '<!doctype html><html data-rf-theme="' + mode + '" data-rf-density="comfortable"' +
      (safeBackgroundUrl ? ' data-rf-background="image"' : '') + '>' +
      '<head><meta charset="utf-8"><style>' + String(asset.css || "") +
      ':root{' + variables + sidebarVariables + activeVariables + dashboardVariables + surfaceVariables + '}' +
      'html,body{width:' + THINGS_PREVIEW_WIDTH + 'px;min-height:' + THINGS_PREVIEW_HEIGHT + 'px;}' +
      'body{overflow:auto!important}.ba-home{min-height:' + THINGS_PREVIEW_HEIGHT + 'px}' +
      '.preview-hide-review .ba-review-chart,.preview-hide-heatmap .ba-heatmap-card{display:none!important}' +
      '.preview-hide-review .ba-analytics,.preview-hide-heatmap .ba-analytics{grid-template-columns:minmax(0,1fr)}' +
      '</style></head><body class="fancy ' + previewClasses + '">' +
      '<center class="ba-home ba-multi"><div class="ad-list ad-list--home" id="thingsPreviewDecks"></div>' +
      analytics + '</center>' +
      '<script>' + seed + scriptEnd +
      '<script>' + safeScript(asset.decklistJs) + scriptEnd +
      '<script>if(window.__adDeckList){window.__adDeckList.render(document.getElementById("thingsPreviewDecks"),window.__baDeckTree,{dragMove:false});}' + scriptEnd +
      '<script>' + safeScript(asset.sidebarJs) + scriptEnd +
      '</body></html>';
  }

  function renderThingsTheme(section) {
    const host = el("div", "osw-things3-config");
    const card = el("div", "osw-designer-preview-card osw-things3-live-card");
    const head = el("div", "osw-designer-preview-head");
    head.appendChild(el("div", "osw-designer-preview-title", str("preview", "Preview")));
    const headControls = el("div", "osw-preview-head-controls");
    const dynamicCtl = el("div", "osw-preview-ctl");
    dynamicCtl.appendChild(el("span", "osw-preview-ctl-label", str("dynamic_mode", "Dynamic mode")));
    const dynamicBtn = el("button", "osw-sq-switch-btn");
    dynamicBtn.type = "button";
    const dynamicTrack = el("div", "osw-sq-switch");
    dynamicBtn.appendChild(dynamicTrack);
    dynamicCtl.appendChild(dynamicBtn);
    headControls.appendChild(dynamicCtl);

    let previewMode = values.onigiri_theme_mode === "dark" || values.onigiri_theme_mode === "light"
      ? values.onigiri_theme_mode
      : (CTX.dark ? "dark" : "light");
    let lastThemeMode = values.onigiri_theme_mode;
    let lastEffectiveDark = !!CTX.dark;
    const modeBtn = el("button", "osw-profile-preview-toggle-btn osw-designer-preview-toggle-btn");
    modeBtn.type = "button";
    const utility = el("div", "osw-preview-utility-ctl");
    utility.appendChild(modeBtn);
    headControls.appendChild(utility);
    head.appendChild(headControls);
    card.appendChild(head);
    observeHeaderCompact(head);

    const stage = el("div", "osw-things3-live-stage");
    const iframe = el("iframe", "osw-things3-live-frame");
    iframe.title = "Kome Main Menu preview";
    stage.appendChild(iframe);
    card.appendChild(stage);
    host.appendChild(card);
    if (section.description) host.appendChild(el("div", "osw-things3-note", section.description));

    const controls = el("div", "osw-things3-controls");
    (section.fields || []).forEach(function (field) {
      const renderer = FIELD_RENDERERS[field.type];
      if (!renderer) return;
      const node = renderer(field);
      node.setAttribute("data-field-host", field.id);
      controls.appendChild(node);
    });
    host.appendChild(controls);

    let lastSignature = "";
    function syncScale() {
      const scale = stage.clientWidth / THINGS_PREVIEW_WIDTH;
      iframe.style.transform = "scale(" + scale + ")";
      stage.style.height = Math.round(THINGS_PREVIEW_HEIGHT * scale) + "px";
    }
    if (window.ResizeObserver) new ResizeObserver(syncScale).observe(stage);
    requestAnimationFrame(syncScale);

    function syncHeader() {
      const dynamic = values.onigiri_theme_mode === "system";
      dynamicTrack.classList.toggle("is-on", dynamic);
      dynamicBtn.setAttribute("aria-pressed", dynamic ? "true" : "false");
      modeBtn.innerHTML = previewMode === "dark" ? OSW_SUN_ICON : OSW_MOON_ICON;
      modeBtn.title = previewMode === "dark" ? str("light_mode", "Light") : str("dark_mode", "Dark");
    }

    function paint(force) {
      const signature = [previewMode,
        values.things_show_due, values.things_show_tasks,
        values.things_show_active_cards, values.things_show_progress,
        values.things_show_review_chart, values.things_show_heatmap,
        values.things_active_new_color, values.things_active_learning_color,
        values.things_active_relearning_color, values.things_active_young_color,
        values.things_active_mature_color,
        values.things_heatmap_color, values.things_weekly_reviews_color,
        values.things_progress_color,
        values.things_main_background_light,
        values.things_main_background_dark,
        values.things_sidebar_background_light,
        values.things_sidebar_background_dark,
        values.things_background_image,
        values.things_sidebar_opacity, values.things_sidebar_blur,
        values.things_deck_opacity, values.things_deck_blur,
        values.things_widgets_opacity, values.things_widgets_blur,
        values.theme_bg_light, values.theme_bg_dark,
        values.theme_inset_light, values.theme_inset_dark,
        values.theme_fg_light, values.theme_fg_dark,
        values.theme_subtle_light, values.theme_subtle_dark,
        values.theme_border_light, values.theme_border_dark,
        values.theme_accent_light, values.theme_accent_dark].join("|");
      syncHeader();
      if (!force && signature === lastSignature) return;
      lastSignature = signature;
      iframe.srcdoc = buildThingsPreviewDocument(previewMode);
    }

    dynamicBtn.addEventListener("click", function () {
      bridge("osw:haptic:1");
      setValue("onigiri_theme_mode", values.onigiri_theme_mode === "system" ? previewMode : "system");
    });
    modeBtn.addEventListener("click", function () {
      bridge("osw:haptic:1");
      previewMode = previewMode === "dark" ? "light" : "dark";
      if (values.onigiri_theme_mode !== "system") {
        setValue("onigiri_theme_mode", previewMode);
      } else {
        paint(true);
      }
    });

    host.__refreshThingsPreview = function () {
      if (values.onigiri_theme_mode === "light" || values.onigiri_theme_mode === "dark") {
        previewMode = values.onigiri_theme_mode;
      } else if (lastThemeMode !== values.onigiri_theme_mode || lastEffectiveDark !== !!CTX.dark) {
        // Switching back to Sync with Anki resets the preview to Anki's mode.
        // Manual preview toggles remain available while that mode is stable.
        previewMode = CTX.dark ? "dark" : "light";
      }
      lastThemeMode = values.onigiri_theme_mode;
      lastEffectiveDark = !!CTX.dark;
      paint(false);
    };
    host.__refreshThingsPreview();
    return host;
  }

  function refreshThingsPreviews() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-things3-config"), function (host) {
      if (host.__refreshThingsPreview) host.__refreshThingsPreview();
    });
  }

  function renderThemes(_section, _page) {
    const icons = CTX.chromeIcons || {};
    const host = el("div", "osw-themes");

    // Same neutral segmented-tab look as the Profile page's own action strip
    // (.osw-segment-btn on .osw-profile-segmented-tabs) rather than the
    // accent-bordered .osw-action-btn used for the gallery's Import — that
    // border reads as "this is the important action here", which is true in
    // a picker popover but wrong for three peer actions in a row.
    // Its own neutral pill per button (not one connected segmented bar) —
    // three peer actions read as three separate buttons, not tabs of a set.
    function makeActionButton(iconKey, label, handler, extraClass) {
      const btn = el("div", "osw-theme-chip-btn" + (extraClass ? " " + extraClass : ""));
      btn.setAttribute("role", "button");
      btn.setAttribute("tabindex", "0");
      if (icons[iconKey]) {
        const iconSpan = el("span", "osw-segment-btn-icon");
        iconSpan.innerHTML = icons[iconKey];
        btn.appendChild(iconSpan);
      }
      btn.appendChild(el("span", null, label));
      if (handler) btn.addEventListener("click", handler);
      return btn;
    }

    function makeSectionHead(titleText, descText, actionsNode) {
      const head = el("div", "osw-themes-section-head");
      const titles = el("div", "osw-themes-section-titles");
      titles.appendChild(el("div", "osw-themes-section-title", titleText));
      if (descText) titles.appendChild(el("div", "osw-themes-section-desc", descText));
      head.appendChild(titles);
      if (actionsNode) head.appendChild(actionsNode);
      return head;
    }

    // Three of the theme's own colors as flat stacked bands (no gradient),
    // each one dipping into the one above with a soft rounded wave instead of
    // a straight or diagonal edge. No text on top of it — the name sits
    // outside, under the art.
    // lightBg / accent / darkBg — not lightAccent + darkAccent + darkBg: a
    // theme's light and dark accents are very often the same exact hex (most
    // of the built-in themes reuse one accent for both modes), which made
    // the top two bands merge into one and read as only two colors. Bg tones
    // are always genuinely apart (a light theme's bg is pale, a dark theme's
    // is dark, categorically, not just "usually"), so anchoring on those
    // instead guarantees three visibly distinct bands every time.
    function themeColors(theme) {
      const light = theme.light || {};
      const dark = theme.dark || {};
      return {
        lightBg: light["--bg"] || "#ffffff",
        accent: light["--accent-color"] || dark["--accent-color"] || "#8a8a8a",
        darkBg: dark["--bg"] || "#1a1a1a",
        lightAccent: light["--accent-color"] || "#8a8a8a",
        darkAccent: dark["--accent-color"] || "#8a8a8a"
      };
    }

    function makeArt(colors) {
      const art = el("span", "osw-theme-art");
      [colors.lightBg, colors.accent, colors.darkBg].forEach(function (color) {
        const band = el("span", "osw-theme-band");
        band.style.background = color;
        art.appendChild(band);
      });
      return art;
    }

    function isDeleteControl(target) {
      return !!(target && target.closest && (target.closest(".osw-gal-del") || target.closest(".osw-gal-confirm")));
    }

    // Hold for 3 seconds (the card trembles the whole time) — release while
    // it's trembling fast (.is-ready) to apply, release early to cancel.
    // Same shape as the Reset hold below, just per-card and with a tremble
    // instead of a fill.
    function makeThemeTile(theme, kind, onDelete) {
      const tile = el("button", "osw-theme-tile");
      tile.type = "button";

      const colors = themeColors(theme);
      const wrap = el("span", "osw-theme-art-wrap");
      // The hover "shuffle": two more of the theme's own colors peeking out
      // from behind the swatch, not plain neutral cards — same reasoning as
      // the swatch itself. Both picks stay on the lighter/brighter side
      // (lightBg, accent) rather than darkBg: a near-black peek layer read
      // as a shadow smudge behind the card in light mode instead of a card.
      const peekA = el("span", "osw-theme-peek osw-theme-peek-a");
      peekA.style.background = colors.lightBg;
      const peekB = el("span", "osw-theme-peek osw-theme-peek-b");
      peekB.style.background = colors.accent;
      wrap.appendChild(peekA);
      wrap.appendChild(peekB);
      wrap.appendChild(makeArt(colors));

      // Nothing else on the card explains the hold gesture up front — this
      // fades in on hover (before the user has pressed anything) and fades
      // back out the moment they actually start holding, handing off to the
      // tremble + accent ring as the "keep going" feedback instead of
      // cluttering the card while they're mid-gesture.
      const holdHint = el("span", "osw-theme-hold-hint");
      holdHint.innerHTML =
        '<svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2">' +
        '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/></svg>';
      holdHint.appendChild(document.createTextNode(str("theme_hold_hint", "Hold 3s to apply")));
      wrap.appendChild(holdHint);

      // Elapsed/remaining while actually holding: a thin bar across the
      // bottom edge, filling over exactly the same 3000ms as the timer below
      // (so "how much is left" is never a guess) via a real CSS transition,
      // not a stepped JS-driven animation — smoother, and it can't drift out
      // of sync with the setTimeout that decides when release counts.
      const holdProgress = el("span", "osw-theme-hold-progress");
      const holdProgressFill = el("span", "osw-theme-hold-progress-fill");
      holdProgress.appendChild(holdProgressFill);
      wrap.appendChild(holdProgress);

      tile.appendChild(wrap);

      const foot = el("span", "osw-theme-foot");
      foot.appendChild(el("span", "osw-theme-name", theme.name));
      const sub = el("span", "osw-theme-sub");
      const dotA = el("span", "osw-theme-sub-dot");
      dotA.style.background = colors.lightAccent;
      const dotB = el("span", "osw-theme-sub-dot");
      dotB.style.background = colors.darkAccent;
      sub.appendChild(dotA);
      sub.appendChild(dotB);
      sub.appendChild(document.createTextNode(str("theme_card_sub", "Light · Dark")));
      foot.appendChild(sub);
      tile.appendChild(foot);

      let holdTimer = null;
      let isReady = false;

      function startHold(e) {
        if (e && e.button !== undefined && e.button !== 0) return;
        if (e && isDeleteControl(e.target)) return;
        if (tile.classList.contains("is-confirming") || tile.classList.contains("is-busy")) return;
        isReady = false;
        tile.classList.add("is-holding");
        // Force the reset below to actually apply before starting the fill —
        // without a reflow in between, the browser coalesces "0% then 100%"
        // into just "100%" and the bar jumps full instead of filling.
        holdProgressFill.style.transition = "none";
        holdProgressFill.style.width = "0%";
        void holdProgressFill.offsetWidth;
        holdProgressFill.style.transition = "width 3000ms linear";
        holdProgressFill.style.width = "100%";
        holdTimer = setTimeout(function () {
          isReady = true;
          tile.classList.add("is-ready");
          bridge("osw:haptic:1");
        }, 3000);
      }

      function resetProgressBar() {
        // Snap back quickly rather than reversing over the same 3s — a
        // released hold should look cancelled immediately, not like it's
        // rewinding in slow motion.
        holdProgressFill.style.transition = "width 150ms ease-out";
        holdProgressFill.style.width = "0%";
      }

      function endHold(e) {
        if (e && e.button !== undefined && e.button !== 0) return;
        tile.classList.remove("is-holding");
        tile.classList.remove("is-ready");
        if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
        if (isReady) {
          isReady = false;
          bridge("osw:haptic:2");
          tile.classList.add("is-busy");
          resetProgressBar();
          call("osw:theme_apply:" + JSON.stringify({ kind: kind, name: theme.name })).then(function (res) {
            tile.classList.remove("is-busy");
            if (!res || !res.ok) { toast((res && res.error) || str("autosave_error", "Could not save")); return; }
            if (res.palettes) {
              CTX.thingsPreview = CTX.thingsPreview || {};
              CTX.thingsPreview.palettes = res.palettes;
            }
            if (res.accent) CTX.accent = res.accent;
            applyTheme();
            applyThemeRefresh(res.refresh, res.preview);
            toast(str("theme_applied_toast", "Theme applied:") + " " + theme.name);
          });
        } else {
          resetProgressBar();
        }
      }

      function cancelHold() {
        tile.classList.remove("is-holding");
        tile.classList.remove("is-ready");
        if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
        isReady = false;
        resetProgressBar();
      }

      tile.addEventListener("mousedown", startHold);
      tile.addEventListener("mouseup", endHold);
      tile.addEventListener("mouseleave", cancelHold);
      tile.addEventListener("touchstart", function (e) { startHold(e); }, { passive: true });
      tile.addEventListener("touchend", endHold);
      tile.addEventListener("touchcancel", cancelHold);

      if (onDelete) {
        const del = el("span", "osw-gal-del");
        del.setAttribute("role", "button");
        del.innerHTML = ICON_CLOSE;
        del.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          tile.classList.add("is-confirming");
        });
        tile.appendChild(del);

        const confirm = el("span", "osw-gal-confirm");
        confirm.appendChild(el("span", "osw-gal-confirm-text", str("gallery_delete_ask", "Delete?")));
        const yes = el("span", "osw-gal-confirm-yes");
        yes.setAttribute("role", "button");
        yes.innerHTML = ICON_CHECK;
        yes.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          onDelete();
        });
        const no = el("span", "osw-gal-confirm-no");
        no.setAttribute("role", "button");
        no.innerHTML = ICON_CLOSE;
        no.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          tile.classList.remove("is-confirming");
        });
        confirm.appendChild(yes);
        confirm.appendChild(no);
        tile.appendChild(confirm);
      }

      return tile;
    }

    // ── your themes ──
    // Import / Export / Reset all live in this one action cluster now — Reset
    // used to sit alone in a header strip above the whole page, disconnected
    // from the themes it actually resets.
    const userActions = el("div", "osw-themes-actions");
    const importBtn = makeActionButton("themeImport", str("import_theme", "Import"), runImport);
    const exportBtn = makeActionButton("themeExport", str("export_theme", "Export current"), runExport);
    // Theme reset remains deliberately hold-to-confirm because it can replace
    // the entire active theme; every other reset follows the same interaction.
    const resetBtn = el("div", "osw-theme-chip-btn osw-profile-reset-btn");
    resetBtn.innerHTML = '<span class="osw-profile-reset-btn-text">' + str("reset_theme_to_default", "Reset to default") + "</span>";
    resetBtn.setAttribute("role", "button");
    resetBtn.setAttribute("tabindex", "0");
    userActions.appendChild(importBtn);
    userActions.appendChild(exportBtn);
    userActions.appendChild(resetBtn);

    const userSection = el("div", "osw-themes-section");
    userSection.appendChild(makeSectionHead(str("your_themes", "Your Themes"), str("your_themes_desc", ""), userActions));
    const userGrid = el("div", "osw-theme-grid");
    userSection.appendChild(userGrid);
    host.appendChild(userSection);

    installResetHold(resetBtn, function () {
      call("osw:theme_reset:").then(function (res) {
        if (!res || !res.ok) { toast(str("autosave_error", "Could not save")); return; }
        if (res.palettes) {
          CTX.thingsPreview = CTX.thingsPreview || {};
          CTX.thingsPreview.palettes = res.palettes;
        }
        if (res.accent) CTX.accent = res.accent;
        applyTheme();
        applyThemeRefresh(res.refresh, res.preview);
        toast(str("default_theme", "Default theme"));
      });
    }, { title: str("reset_theme_to_default", "Reset to default") });

    let userThemes = ((CTX.themeGallery || {}).user || []).slice();

    function paintUserGrid() {
      userGrid.innerHTML = "";
      if (!userThemes.length) {
        const empty = el("div", "osw-theme-empty");
        const icon = el("div", "osw-theme-empty-icon");
        icon.innerHTML = icons.themeImport || "";
        empty.appendChild(icon);
        const text = el("div", "osw-theme-empty-text");
        text.appendChild(el("div", "osw-theme-empty-title", str("no_custom_themes", "No custom themes yet")));
        text.appendChild(el("div", "osw-theme-empty-desc", str("no_custom_themes_hint", "")));
        empty.appendChild(text);
        userGrid.appendChild(empty);
        return;
      }
      userThemes.forEach(function (theme) {
        userGrid.appendChild(makeThemeTile(theme, "user", function () { runDeleteTheme(theme.name); }));
      });
    }

    function runDeleteTheme(name) {
      call("osw:theme_delete:" + JSON.stringify({ name: name })).then(function (res) {
        if (!res || !res.ok) { toast((res && res.error) || str("autosave_error", "Could not save")); return; }
        userThemes = res.user || [];
        paintUserGrid();
        toast(str("theme_deleted_toast", "Theme deleted:") + " " + name);
      });
    }

    function runImport() {
      importBtn.classList.add("is-busy");
      call("osw:theme_import:").then(function (res) {
        importBtn.classList.remove("is-busy");
        if (!res || !res.ok) { if (res && res.error) toast(res.error); return; }
        if (res.cancelled || !res.theme) return;
        userThemes = userThemes.filter(function (t) { return t.name !== res.theme.name; });
        userThemes.push(res.theme);
        userThemes.sort(function (a, b) { return a.name.localeCompare(b.name); });
        paintUserGrid();
        toast(str("theme_imported_toast", "Theme imported successfully"));
      });
    }

    function runExport() {
      promptThemeName(function (name) {
        if (!name) return;
        exportBtn.classList.add("is-busy");
        call("osw:theme_export:" + JSON.stringify({ name: name })).then(function (res) {
          exportBtn.classList.remove("is-busy");
          if (!res || !res.ok) { if (res && res.error) toast(res.error); return; }
          if (res.cancelled) return;
          toast(str("theme_exported_toast", "Theme exported:") + " " + name);
        });
      });
    }

    paintUserGrid();

    // ── official themes ──
    const officialSection = el("div", "osw-themes-section");
    officialSection.appendChild(makeSectionHead(str("official_themes", "Official Themes"), str("official_themes_desc", ""), null));
    const officialGrid = el("div", "osw-theme-grid");
    ((CTX.themeGallery || {}).official || []).forEach(function (theme) {
      officialGrid.appendChild(makeThemeTile(theme, "official", null));
    });
    officialSection.appendChild(officialGrid);
    host.appendChild(officialSection);

    return host;
  }

  /* Gallery's image browser: every picture folder on disk, with Import and
     per-file Delete. Replaces settings/_page_gallery.py's images half, which
     could only show the first 24 files of each folder and whose tiles navigated
     to the page that used them instead of doing anything here.

     It talks to the same three bridge commands the picture popover uses, so a
     delete still sweeps the settings that pointed at the file (Python answers
     with the field ids it blanked) — deleting from here and deleting from a
     picker are the same operation. */
  function renderGalleryAssets(section) {
    const host = el("div", "osw-assets");

    (section.folders || []).forEach(function (entry) {
      const folder = entry.id;
      const group = el("div", "osw-assets-group");

      const head = el("div", "osw-assets-head");
      const titles = el("div", "osw-assets-titles");
      titles.appendChild(el("div", "osw-assets-title", entry.title || folder));
      const count = el("div", "osw-assets-count");
      titles.appendChild(count);
      head.appendChild(titles);

      const importBtn = el("button", "osw-btn osw-assets-import");
      importBtn.type = "button";
      const importIcon = el("span", "osw-assets-import-icon");
      importIcon.innerHTML = ICON_PLUS;
      importBtn.appendChild(importIcon);
      importBtn.appendChild(el("span", null, str("gallery_import", "Import image")));
      head.appendChild(importBtn);
      group.appendChild(head);

      const grid = el("div", "osw-assets-grid");
      group.appendChild(grid);

      let confirming = null;

      function paint() {
        const images = galleryList(folder);
        grid.innerHTML = "";
        count.textContent = images.length === 0
          ? str("no_images_uploaded", "Nothing here yet")
          : images.length === 1
            ? str("gallery_asset_count_one", "1 file")
            : fmt(str("gallery_asset_count", "{n} files"), { n: images.length });
        images.forEach(function (image) {
          const tile = el("div", "osw-assets-tile" + (confirming === image.name ? " is-confirming" : ""));
          const thumb = el("div", "osw-assets-thumb");
          const url = image.url || imageUrl(folder, image.name);
          if (url) thumb.style.backgroundImage = "url(\"" + url.replace(/"/g, "") + "\")";
          tile.appendChild(thumb);
          tile.appendChild(el("div", "osw-assets-name", image.name));

          const del = el("button", "osw-assets-del");
          del.type = "button";
          del.setAttribute("aria-label", str("delete", "Delete"));
          del.innerHTML = ICON_CLOSE;
          del.addEventListener("click", function (event) {
            event.stopPropagation();
            bridge("osw:haptic:1");
            confirming = image.name;
            paint();
          });
          tile.appendChild(del);

          const confirm = el("div", "osw-assets-confirm");
          confirm.appendChild(el("span", "osw-assets-confirm-text", str("gallery_delete_ask", "Delete?")));
          const approve = el("span", "osw-assets-confirm-action is-delete");
          approve.setAttribute("role", "button");
          approve.setAttribute("tabindex", "0");
          approve.setAttribute("aria-label", str("gallery_delete", "Delete image"));
          approve.innerHTML = LUCIDE_CHECK;
          function approveDelete(event) {
            event.stopPropagation();
            confirming = null;
            runDelete(image.name);
          }
          approve.addEventListener("click", approveDelete);
          approve.addEventListener("keydown", function (event) {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            approveDelete(event);
          });
          const cancel = el("span", "osw-assets-confirm-action is-cancel");
          cancel.setAttribute("role", "button");
          cancel.setAttribute("tabindex", "0");
          cancel.setAttribute("aria-label", str("cancel", "Cancel"));
          cancel.innerHTML = LUCIDE_X;
          function cancelDelete(event) {
            event.stopPropagation();
            confirming = null;
            paint();
          }
          cancel.addEventListener("click", cancelDelete);
          cancel.addEventListener("keydown", function (event) {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            cancelDelete(event);
          });
          confirm.appendChild(approve);
          confirm.appendChild(cancel);
          tile.appendChild(confirm);
          grid.appendChild(tile);
        });
      }

      function runDelete(name) {
        call("osw:gallery_delete:" + JSON.stringify({ folder: folder, name: name }))
          .then(function (res) {
            if (!res || !res.ok) {
              toast((res && res.error) || str("autosave_error", "Could not save"));
              return;
            }
            setGalleryList(folder, res.images);
            // Python already blanked whatever pointed at the file; applying the
            // same locally keeps the open page from showing a picture that is
            // gone, without echoing a patch back at it.
            (res.cleared || []).forEach(function (id) { applyExternalValue(id, ""); });
            paint();
            refreshImageFields();
            updateProfilePreview();
            updateDesignerPreviews();
            toast(fmt(str("gallery_deleted", "“{name}” deleted"), { name: name }));
          });
      }

      importBtn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        importBtn.classList.add("is-busy");
        call("osw:gallery_import:" + JSON.stringify({ folder: folder }))
          .then(function (res) {
            importBtn.classList.remove("is-busy");
            if (!res || !res.ok) {
              if (res && res.error) toast(res.error);
              return;
            }
            setGalleryList(folder, res.images);
            paint();
            refreshImageFields();
          });
      });

      paint();
      // The page ships each folder's contents with it, so the grid paints from
      // real files immediately; this only catches what changed on disk since.
      call("osw:gallery_list:" + JSON.stringify({ folder: folder }))
        .then(function (res) {
          if (!res || !res.ok || !Array.isArray(res.images)) return;
          const before = galleryList(folder).map(function (i) { return i.name; }).join(" ");
          const after = res.images.map(function (i) { return i.name; }).join(" ");
          if (before === after) return;
          setGalleryList(folder, res.images);
          paint();
        });

      host.appendChild(group);
    });

    return host;
  }

  /* Markers: one card per marker instead of twelve indistinguishable rows.
     Each card leads with the thing the user actually recognises — a deck row
     with the mark on it, drawn the way the deck browser draws it
     (patcher.py:6120-6141): a coloured dot, or the chosen glyph masked in that
     same colour. The name is edited in place on that row, so what is typed is
     seen where it will appear; the colour and glyph sit under it. */
  function renderMarkers(section) {
    // A live sidebar stage above the cards, same as Background/Actions/Deck
    // Icons — the deck rows draw each marker exactly as designerDeckRows
    // does for the other three, so markers get the same "this is what it
    // actually looks like" preview instead of only their own dot swatch.
    PREVIEW_PAINTERS[section.preview_kind] = function (stage, vals, isDark) {
      return paintSidebarStack(stage, vals, isDark, section.markers);
    };

    const wrap = el("div", "osw-designer-page-wrap is-stage-side");
    const card = el("div", "osw-designer-preview-card osw-preview-kind-" + section.preview_kind);
    let previewMode = CTX.dark ? "dark" : "light";
    card.classList.toggle("is-dark", previewMode === "dark");

    const head = el("div", "osw-designer-preview-head");
    head.appendChild(el("div", "osw-designer-preview-title", section.title || str("preview", "Preview")));
    const headControls = el("div", "osw-preview-head-controls");
    const toggleBtn = el("button", "osw-profile-preview-toggle-btn osw-designer-preview-toggle-btn");
    toggleBtn.type = "button";
    function paintToggleIcon() {
      toggleBtn.innerHTML = previewMode === "dark" ? OSW_SUN_ICON : OSW_MOON_ICON;
      toggleBtn.title = previewMode === "dark" ? str("light_mode", "Light") : str("dark_mode", "Dark");
    }
    paintToggleIcon();
    toggleBtn.addEventListener("click", function () {
      previewMode = previewMode === "dark" ? "light" : "dark";
      card.classList.toggle("is-dark", previewMode === "dark");
      paintToggleIcon();
      paintDesignerPreview(card);
    });
    const utilityCtl = el("div", "osw-preview-utility-ctl");
    utilityCtl.appendChild(toggleBtn);
    headControls.appendChild(utilityCtl);
    head.appendChild(headControls);
    card.appendChild(head);
    observeHeaderCompact(head);

    const stage = el("div", "osw-designer-preview-stage");
    card.appendChild(stage);
    card.__stage = stage;
    card.__section = section;
    card.__getMode = function () { return previewMode; };
    wrap.appendChild(card);

    const host = el("div", "osw-markers");
    wrap.appendChild(host);

    (section.markers || []).forEach(function (marker) {
      const colorField = fieldById[marker.color_field];
      const iconField = fieldById[marker.icon_field];
      const nameField = fieldById[marker.name_field];
      if (!colorField || !iconField || !nameField) return;

      const card = el("div", "osw-marker-card");
      card.setAttribute("data-marker", marker.key);

      // ── preview: the deck row this marker produces ──────────────────────
      const preview = el("div", "osw-marker-preview");
      const row = el("div", "osw-marker-deck-row");
      const dot = el("span", "osw-marker-dot");
      const deckName = el("span", "osw-marker-deck-name", "Japanese");
      const counts = el("span", "osw-marker-deck-counts");
      [["12", "#1e8cff"], ["3", "#19c96b"], ["40", "#ff5757"]].forEach(function (pair) {
        const badge = el("span", "osw-marker-deck-badge", pair[0]);
        badge.style.background = pair[1];
        counts.appendChild(badge);
      });
      // Deck name, then the mark, then the counts — the mark sits immediately
      // left of the count badges, which is where the deck list puts it.
      row.appendChild(deckName);
      row.appendChild(dot);
      row.appendChild(counts);
      preview.appendChild(row);
      card.appendChild(preview);

      function paintDot() {
        const color = values[marker.color_field] || "#888888";
        const icon = String(values[marker.icon_field] || "default");
        dot.className = "osw-marker-dot";
        dot.textContent = "";
        dot.style.webkitMaskImage = "";
        dot.style.maskImage = "";
        if (icon.indexOf("emoji:") === 0) {
          dot.classList.add("is-emoji");
          dot.style.background = "transparent";
          dot.style.color = color;
          dot.textContent = icon.slice(6);
          return;
        }
        const url = icon && icon !== "default" ? resolveIconAssetUrl(icon) : "";
        dot.style.background = color;
        if (!url) return; // plain coloured dot, the default the deck list draws
        dot.classList.add("is-icon");
        dot.style.webkitMaskImage = "url('" + url + "')";
        dot.style.maskImage = "url('" + url + "')";
      }

      // ── controls ────────────────────────────────────────────────────────
      const head = el("div", "osw-marker-head");
      const nameInput = document.createElement("input");
      nameInput.className = "osw-marker-name-input";
      nameInput.type = "text";
      nameInput.value = values[marker.name_field] || "";
      nameInput.placeholder = marker.label;
      nameInput.setAttribute("aria-label", marker.label);
      nameInput.addEventListener("input", function () {
        setValue(marker.name_field, nameInput.value, { keepDom: true, debounce: true });
      });
      head.appendChild(nameInput);

      const reset = el("button", "osw-marker-reset");
      reset.type = "button";
      reset.title = str("reset_to_default", "Reset to Default");
      reset.innerHTML = ICON_UNDO;
      installResetHold(reset, function () {
        setValue(marker.color_field, colorField.default, { keepDom: true });
        setValue(marker.icon_field, iconField.default, { keepDom: true });
        setValue(marker.name_field, "", { keepDom: true });
        nameInput.value = "";
        paintDot();
      });
      head.appendChild(reset);
      card.appendChild(head);

      const controls = el("div", "osw-marker-controls");

      const colorBtn = el("button", "osw-marker-chip");
      colorBtn.type = "button";
      colorBtn.setAttribute("data-field", marker.color_field);
      colorBtn.setAttribute("data-field-type", "color");
      const swatch = el("span", "osw-marker-chip-swatch osw-chip-swatch");
      const hex = el("span", "osw-marker-chip-hex osw-chip-hex");
      colorBtn.appendChild(swatch);
      colorBtn.appendChild(hex);
      colorBtn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        openColorPickerById(marker.color_field, values[marker.color_field] || "");
      });
      controls.appendChild(colorBtn);

      const iconBtn = el("button", "osw-marker-chip osw-icon-chip");
      iconBtn.type = "button";
      iconBtn.setAttribute("data-field", marker.icon_field);
      iconBtn.setAttribute("data-field-type", "icon");
      const iconPreview = el("span", "osw-icon-chip-preview");
      const iconLabel = el("span", "osw-marker-chip-label");
      iconBtn.appendChild(iconPreview);
      iconBtn.appendChild(iconLabel);
      iconBtn.addEventListener("click", function () {
        bridge("osw:haptic:1");
        openIconPicker(iconField);
      });
      controls.appendChild(iconBtn);
      card.appendChild(controls);

      function paintChips() {
        const color = values[marker.color_field] || "";
        swatch.style.background = color || "transparent";
        hex.textContent = String(color).toUpperCase();
        const icon = String(values[marker.icon_field] || "default");
        iconPreview.innerHTML = "";
        iconPreview.classList.remove("is-emoji", "is-empty");
        iconPreview.style.webkitMaskImage = "";
        iconPreview.style.maskImage = "";
        if (icon.indexOf("emoji:") === 0) {
          iconPreview.classList.add("is-emoji");
          iconPreview.textContent = icon.slice(6);
          iconLabel.textContent = str("marker_icon_custom", "Custom");
          return;
        }
        const url = icon && icon !== "default" ? resolveIconAssetUrl(icon) : "";
        if (url) {
          iconPreview.style.webkitMaskImage = "url('" + url + "')";
          iconPreview.style.maskImage = "url('" + url + "')";
          iconLabel.textContent = iconAssetLabel(icon);
        } else {
          iconPreview.classList.add("is-empty");
          iconPreview.textContent = "●";
          iconLabel.textContent = str("marker_icon_dot", "Dot");
        }
      }

      // syncField finds these by data-field, so a value changed from the native
      // colour picker or the icon popover repaints the card and its preview.
      colorBtn.__syncMarker = function () { paintChips(); paintDot(); };
      iconBtn.__syncIconChip = function () { paintChips(); paintDot(); };
      iconBtn.__syncMarker = colorBtn.__syncMarker;

      paintChips();
      paintDot();
      host.appendChild(card);
    });

    registerDesignerPreview(card);
    paintDesignerPreview(card);

    return wrap;
  }

  /* Pomodoro's fast setup deliberately renders several bound number fields as
     one cohesive surface. The schema still owns every value and preset; this
     renderer only turns them into tap-friendly chips. */
  function renderPomodoroSetup(section) {
    const root = el("div", "osw-pomo-setup");
    if (section.description) {
      root.appendChild(el("div", "osw-pomo-setup-desc", section.description));
    }

    const presetBlock = el("div", "osw-pomo-setup-block");
    presetBlock.appendChild(el("div", "osw-pomo-setup-label", str("pomodoro_routines", "Routines")));
    const presetGrid = el("div", "osw-pomo-presets");
    (section.presets || []).forEach(function (preset) {
      const button = el("button", "osw-pomo-preset");
      button.type = "button";
      button.appendChild(el("span", "osw-pomo-preset-name", preset.label));
      button.appendChild(el("span", "osw-pomo-preset-sub", preset.sub || ""));
      button.__presetValues = preset.values || {};
      button.addEventListener("click", function () {
        bridge("osw:haptic:1");
        Object.keys(button.__presetValues).forEach(function (fieldId) {
          setValue(fieldId, button.__presetValues[fieldId]);
        });
      });
      presetGrid.appendChild(button);
    });
    presetBlock.appendChild(presetGrid);
    root.appendChild(presetBlock);

    const valuesGrid = el("div", "osw-pomo-values");
    (section.groups || []).forEach(function (group) {
      const groupNode = el("div", "osw-pomo-value-group");
      groupNode.appendChild(el("div", "osw-pomo-value-label", group.label));
      const chips = el("div", "osw-pomo-value-chips");
      const options = (group.options || []).slice();
      const current = Number(values[group.field]);
      if (Number.isFinite(current) && options.indexOf(current) === -1) {
        options.push(current);
        options.sort(function (a, b) { return Number(a) - Number(b); });
      }
      options.forEach(function (option) {
        const button = el("button", "osw-pomo-value-chip");
        button.type = "button";
        button.setAttribute("data-field-id", group.field);
        button.setAttribute("data-value", String(option));
        button.appendChild(el("strong", "", String(option)));
        if (group.unit) button.appendChild(el("span", "", group.unit));
        button.addEventListener("click", function () {
          bridge("osw:haptic:1");
          setValue(group.field, Number(option));
        });
        chips.appendChild(button);
      });
      groupNode.appendChild(chips);
      valuesGrid.appendChild(groupNode);
    });
    root.appendChild(valuesGrid);

    root.__syncPomodoroSetup = function () {
      Array.prototype.forEach.call(root.querySelectorAll(".osw-pomo-value-chip"), function (button) {
        const fieldId = button.getAttribute("data-field-id");
        const selected = String(values[fieldId]) === button.getAttribute("data-value");
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      });
      Array.prototype.forEach.call(root.querySelectorAll(".osw-pomo-preset"), function (button) {
        const patch = button.__presetValues || {};
        const selected = Object.keys(patch).every(function (fieldId) {
          return values[fieldId] === patch[fieldId];
        });
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      });
    };
    root.__syncPomodoroSetup();
    return root;
  }

  /* The widget appearance controls form one compact two-row container inside
     Organize Widgets. Reusing the normal field renderers keeps color picking
     and autosave on the same code path as every other appearance setting. */
  function renderCompactWidgetEffect(section) {
    const root = el("div", "osw-widget-effect-compact osw-designer-deck");
    const effects = el("div", "osw-widget-effect-compact-effects");
    const colors = el("div", "osw-widget-effect-compact-colors");

    (section.fields || []).forEach(function (field) {
      if (field.type !== "slider" && field.type !== "color_pair") return;
      const node = renderDeckField(field);
      if (!node) return;
      if (field.advanced) {
        node.setAttribute("data-simple-organize-advanced", "true");
      }
      if (field.type === "slider") effects.appendChild(node);
      else colors.appendChild(node);
    });

    if (effects.childNodes.length) root.appendChild(effects);
    if (colors.childNodes.length) root.appendChild(colors);
    return root;
  }

  function renderWidgetLayoutControls(section) {
    const layoutField = fieldById["modern_menu_widget_layout"];
    const gapField = fieldById["modern_menu_sidebar_widget_gap"];
    const edgeIds = [
      "modern_menu_widget_margin_top",
      "modern_menu_widget_margin_right",
      "modern_menu_widget_margin_bottom",
      "modern_menu_widget_margin_left"
    ];
    const edgeFields = edgeIds.map(function (id) { return fieldById[id]; });
    if (!layoutField || !gapField || edgeFields.some(function (field) { return !field; })) return null;

    const root = el("div", "osw-widget-layout-compact osw-designer-deck");
    const layoutNode = renderDeckField(layoutField);
    root.appendChild(layoutNode);

    const customGrid = el("div", "osw-widget-layout-custom");
    edgeFields.forEach(function (field) {
      const node = renderDeckField(field);
      if (node) customGrid.appendChild(node);
    });
    root.appendChild(customGrid);

    const gapNode = renderDeckField(gapField);
    if (gapNode) {
      gapNode.classList.add("osw-widget-layout-gap");
      root.appendChild(gapNode);
    }

    // Center stacks the widgets below the menu, so the horizontal sidebar
    // offset is inactive. Keep its stored value for a return to Left/Right.
    root.__section = { fields: [gapField] };
    root.__fieldsHost = root;
    applyPlainVisibility(root);
    conditionalBlocks.push(root);

    function syncCustomControls() {
      const isCustom = values[layoutField.id] === "custom";
      customGrid.hidden = !isCustom;
      customGrid.classList.toggle("is-hidden", !isCustom);
    }
    Array.prototype.forEach.call(layoutNode.querySelectorAll(".osw-segment-btn"), function (button) {
      button.addEventListener("click", function () {
        // renderChoice writes its value first; queueing guarantees this reads
        // the selected mode even if that implementation changes later.
        setTimeout(syncCustomControls, 0);
      });
    });
    syncCustomControls();
    return root;
  }

  const SECTION_RENDERERS = {
    ladder: renderLadder,
    color_gallery: renderColorGallery,
    gallery_assets: renderGalleryAssets,
    markers: renderMarkers,
    font_role: renderFontRole,
    font_roles: renderFontRoles,
    profile_preview: renderProfilePreview,
    designer_preview: renderDesignerPreview,
    widget_grid: renderWidgetGrid,
    theme_style: renderThemeStyle,
    things_theme: renderThingsTheme,
    themes: renderThemes,
    onigimon_companions: renderOnigimonCompanions,
    hexagon_keys: renderHexagonKeys,
    bento_games: renderBentoGames,
    games_gallery: renderGamesGallery,
    pomodoro_setup: renderPomodoroSetup
  };

  /* Plain (non-designer) sections that contain at least one conditional field.
     Rebuilt on every showPage, so a page swap cannot leave stale nodes behind. */
  let conditionalBlocks = [];

  function applyPlainVisibility(block) {
    const section = block.__section || {};
    const sectionHidden = !!section.showWhen && !showWhenMatches(section.showWhen);
    block.classList.toggle("is-hidden", sectionHidden);
    // `hidden` is the functional guarantee; the class is retained for styling
    // and inspection. Whole-section conditions must not depend on a CSS rule
    // being present, as field-level conditions historically did.
    block.hidden = sectionHidden;
    const host = block.__fieldsHost;
    if (!host) return;
    (section.fields || []).forEach(function (field) {
      if (!field.showWhen) return;
      const node = host.querySelector('[data-field-host="' + field.id + '"]');
      if (!node) return;
      node.classList.toggle("is-hidden", !showWhenMatches(field.showWhen));
    });
    if (block.__afterVisibility) block.__afterVisibility();
  }

  function refreshConditionalBlocks() {
    conditionalBlocks = conditionalBlocks.filter(function (block) {
      return block.isConnected;
    });
    conditionalBlocks.forEach(applyPlainVisibility);
  }

  /* Ladder rows mirror plain fields, so a cascade that flips three switches has
     to repaint the spine as well. Called from syncField. */
  function refreshLadders() {
    Array.prototype.forEach.call(document.querySelectorAll(".osw-ladder"), function (node) {
      if (node.__refreshLadder) node.__refreshLadder();
    });
  }

  // ── page rendering ─────────────────────────────────────────────────────────

  function pageIsAvailable(page) {
    if (!page) return false;
    if ((page.id === "prepstation" || page.id === "hashinotes") &&
        values.onigiri_ui_theme !== "classic") {
      return false;
    }
    return !page.showWhen || showWhenMatches(page.showWhen);
  }

  function refreshPageVisibility() {
    const search = document.getElementById("oswSearch");
    const needle = String((search && search.value) || "").trim().toLowerCase();
    let visible = 0;
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-item]"), function (node) {
      const id = node.getAttribute("data-nav-item");
      const available = pageIsAvailable(pageById[id]);
      const matchesSearch = !needle || (INDEX[id] || "").indexOf(needle) !== -1;
      node.classList.toggle("is-hidden", !available || !matchesSearch);
      if (available && matchesSearch) visible += 1;
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-group]"), function (group) {
      const anyVisible = group.querySelector("[data-nav-item]:not(.is-hidden)");
      group.style.display = anyVisible ? "" : "none";
    });
    const empty = document.getElementById("oswNavEmpty");
    if (empty) empty.style.display = visible ? "none" : "";

    if (currentPage && !pageIsAvailable(pageById[currentPage])) {
      const fallback = pageIsAvailable(pageById.mainmenu)
        ? pageById.mainmenu
        : PAGES.filter(pageIsAvailable)[0];
      if (fallback) showPage(fallback.id);
    }
  }

  function buildNav() {
    const nav = document.getElementById("oswNav");
    nav.innerHTML = "";
    (CTX.nav || []).forEach(function (group) {
      const section = el("div", "osw-nav-group");
      section.setAttribute("data-nav-group", group.id);
      section.appendChild(el("div", "osw-nav-title", group.title));
      group.items.forEach(function (item) {
        const button = el("button", "osw-nav-item");
        button.type = "button";
        button.setAttribute("data-nav-item", item.id);
        if (item.simpleOnly) button.setAttribute("data-simple-page", "true");
        const icon = el("span", "osw-nav-icon");
        icon.innerHTML = item.icon || "";
        button.appendChild(icon);
        button.appendChild(el("span", "osw-nav-label", item.title));
        if (item.legacy) {
          const dot = el("span", "osw-nav-legacy");
          button.appendChild(dot);
        }
        button.addEventListener("click", function () {
          // Replay even when the already-selected page is clicked: the small
          // icon response confirms the press without making navigation move.
          icon.classList.remove("is-activating");
          void icon.offsetWidth;
          icon.classList.add("is-activating");
          const search = document.getElementById("oswSearch");
          if (search && search.value) {
            search.value = "";
            applySearch("");
          }
          showPage(item.id);
        });
        section.appendChild(button);
      });
      nav.appendChild(section);
    });
    const empty = el("div", "osw-nav-empty", "—");
    empty.id = "oswNavEmpty";
    empty.style.display = "none";
    nav.appendChild(empty);
    refreshPageVisibility();
  }

  /* One section, rendered into its own card block. Shared by the plain stacked
     pages and by the tabbed ones (which render exactly one of these at a time). */
  function renderSectionBlock(section, page, withTitle) {
    const block = el("section", "osw-section");
    block.setAttribute("data-section", section.id || "");
    if (section.modeParity) block.setAttribute("data-mode-parity", "true");
    block.__section = section;
    if (withTitle && section.title) block.appendChild(el("div", "osw-section-title", section.title || ""));
    if (withTitle && section.description && !SECTION_RENDERERS[section.layout]) {
      block.appendChild(el("div", "osw-section-desc", section.description));
    }
    const sectionRenderer = SECTION_RENDERERS[section.layout];
    try {
      if (sectionRenderer) {
        block.appendChild(sectionRenderer(section, page));
        if (section.showWhen) {
          applyPlainVisibility(block);
          conditionalBlocks.push(block);
        }
      } else {
        const compactFontFieldIds = {};
        (section.fontRoles || []).forEach(function (role) {
          (role.field_ids || []).forEach(function (fieldId) {
            compactFontFieldIds[fieldId] = true;
          });
        });
        if ((SETTINGS_MODE_PARITY || settingsComplexity === "advanced") && (section.fontRoles || []).length) {
          const fontMenuRow = el("div", "osw-designer-font-menu-row");
          fontMenuRow.appendChild(compactFontMenuButton(section));
          block.appendChild(fontMenuRow);
        }
        const fields = el("div", "osw-fields");
        (section.fields || []).forEach(function (field) {
          if (compactFontFieldIds[field.id]) return;
          // A colour listed as an icon field's popover companion renders inside
          // that popover, not as a row of its own — same rule the designer deck
          // applies (deckSkipField).
          if (ICON_POPUP_SKIP[field.id]) return;
          const renderer = FIELD_RENDERERS[field.type];
          if (!renderer) return;
          const node = renderer(field);
          node.setAttribute("data-field-host", field.id);
          fields.appendChild(node);
        });
        block.appendChild(fields);
        // A row that only applies in some states collapses away in the others,
        // the same rule designer decks already follow (applyDeckVisibility).
        block.__fieldsHost = fields;
        applyPlainVisibility(block);
        conditionalBlocks.push(block);
      }
    } catch (err) {
      // One section's bug should never blank the whole page — the rest of
      // Main menu (or any other multi-section page) still needs to work.
      console.error("[Onigiri] settings_web: section '" + section.id + "' (" + section.layout + ") failed to render:", err);
      block.appendChild(el("div", "osw-note", "⚠ " + section.id + ": " + (err && err.message ? err.message : String(err))));
    }
    return block;
  }

  // Last sub-menu tab used per page, so coming back to Main menu lands where
  // the user left it instead of always on the first section.
  const activeTabByPage = {};
  let tabbedFitObserver = null;

  /* Tabbed page: sub-menu strip on top, one section mounted at a time. Only
     the visible section is in the DOM — a page with five designer previews
     paints one stage instead of five on every value change. */
  function renderTabbedPage(page, host) {
    const sections = (page.sections || []).filter(function (s) {
      return s.title && (!s.showWhen || showWhenMatches(s.showWhen)) &&
        !(s.advancedOnly && !SETTINGS_MODE_PARITY && settingsComplexity !== "advanced");
    });
    if (!sections.length) return false;

    // The strip lives on the page title's line, not above the content.
    const tabsWrap = document.getElementById("oswPageTabs");
    tabsWrap.innerHTML = "";
    // Start with labels. `fitTabs()` will switch to the compact icon rail only
    // when this particular header cannot accommodate every destination.
    tabsWrap.classList.remove("is-icons");
    const strip = el("div", "osw-subtabs-strip");

    // Main Menu and Sidebar resets live beside their tab strips because each
    // resets the complete page, not merely the currently selected section.
    if (page.id === "mainmenu" || page.id === "sidebar") {
      const isMainMenuReset = page.id === "mainmenu";
      const resetWrap = el(
        "div",
        "osw-subtabs-strip osw-page-reset-wrap"
      );
      // Use the identical tab-strip/button classes as Organize Widgets. The
      // profile reset class supplies only the shared hold-progress behavior.
      const resetBtn = el("div", "osw-segment-btn osw-subtab osw-profile-reset-btn is-active");
      resetBtn.title = isMainMenuReset
        ? str("hold_to_reset_main_menu", "Hold for 3 seconds to reset Main Menu customizations")
        : str("hold_to_reset_sidebar", "Hold for 3 seconds to reset Sidebar customizations");
      resetBtn.setAttribute("aria-label", resetBtn.title);
      resetBtn.setAttribute("role", "button");
      resetBtn.setAttribute("tabindex", "0");
      resetBtn.innerHTML = '<span class="osw-profile-reset-btn-text">' +
        (isMainMenuReset
          ? str("profile_reset_default", "Restore Default")
          : str("reset_default", "Reset Default")) + '</span>';

      function resetPageSettings() {
        // Use each schema field's declared default rather than duplicating
        // defaults here. Include compact font-role fields as well as the
        // ordinary section fields so Sidebar Fonts resets with the page.
        const resetFields = [];
        const seenFields = {};
        sections.forEach(function (section) {
          (section.fields || []).forEach(function (field) {
            if (seenFields[field.id]) return;
            seenFields[field.id] = true;
            resetFields.push(field);
          });
          (section.fontRoles || []).forEach(function (role) {
            (role.field_ids || []).forEach(function (fieldId) {
              if (seenFields[fieldId] || !fieldById[fieldId]) return;
              seenFields[fieldId] = true;
              resetFields.push(fieldById[fieldId]);
            });
          });
        });
        resetFields.forEach(function (field) {
            if (!field.bound || field.virtual || field.default === undefined) return;
            const defaultValue = field.default && typeof field.default === "object"
              ? JSON.parse(JSON.stringify(field.default))
              : field.default;
            setValue(field.id, defaultValue, { silent: true, skipCascade: true });
        });
        // The layout field's schema default carries only its base structure,
        // so build the real default widget arrangement here as well. This
        // lives outside renderWidgetGrid because the header action can be
        // used while any Main Menu tab is selected.
        if (isMainMenuReset) {
          const layoutField = fieldById.onigiriWidgetLayout || {};
          const baseLayout = layoutField.default && typeof layoutField.default === "object"
            ? JSON.parse(JSON.stringify(layoutField.default))
            : {};
          const catalogue = CTX.organizeCatalogue || { onigiri: [] };
          const specsByWid = {};
          catalogue.onigiri.forEach(function (spec) { specsByWid[spec.wid] = spec; });
          const columns = Number(baseLayout.column_count) || 4;
          const tiles = [];
          const grid = {};
          ORGANIZE_DEFAULT_LAYOUT.forEach(function (wid) {
            const spec = specsByWid[wid];
            if (!spec) return;
            const rowSpan = organizeClampSpan(spec.defaultSpan[0], spec, true);
            const colSpan = organizeClampSpan(spec.defaultSpan[1], spec, false);
            const slot = organizeFindFreeSlot(tiles, rowSpan, colSpan, columns);
            const tile = { wid: wid, row: slot.row, col: slot.col, rowSpan: rowSpan, colSpan: colSpan };
            tiles.push(tile);
            grid[wid] = {
              pos: slot.row * columns + slot.col,
              row: rowSpan,
              col: colSpan,
              display_name: spec.name,
            };
          });
          const archive = {};
          catalogue.onigiri.forEach(function (spec) {
            if (!grid[spec.wid]) archive[spec.wid] = { display_name: spec.name };
          });
          baseLayout.grid = grid;
          baseLayout.archive = archive;
          setValue("onigiriWidgetLayout", baseLayout, { silent: true, skipCascade: true });
        }
        activeTabByPage[page.id] = sections[0].id;
        mount(sections[0].id);
      }
      installResetHold(resetBtn, resetPageSettings, { title: resetBtn.title });
      resetWrap.appendChild(resetBtn);
      tabsWrap.appendChild(resetWrap);
    }
    tabsWrap.appendChild(strip);

    const body = el("div", "osw-subtab-body");
    host.appendChild(body);

    let activeId = activeTabByPage[page.id];
    if (!sections.some(function (s) { return s.id === activeId; })) activeId = sections[0].id;

    const buttons = {};

    function mount(sectionId) {
      activeId = sectionId;
      activeTabByPage[page.id] = sectionId;
      Object.keys(buttons).forEach(function (id) {
        buttons[id].classList.toggle("is-active", id === sectionId);
        buttons[id].setAttribute("aria-selected", id === sectionId ? "true" : "false");
      });
      body.innerHTML = "";
      activeDesignerPreviews = [];
      activeWidgetGridPreviews = [];
      stopWidgetGridBackgroundSync();
      const section = sections.filter(function (s) { return s.id === sectionId; })[0];
      if (section) body.appendChild(renderSectionBlock(section, page, false));
      applySettingsComplexity(false);
      const scroller = document.getElementById("oswPageScroll");
      if (scroller) scroller.scrollTop = 0;
      refreshEdgeFades();
    }

    sections.forEach(function (section) {
      const button = el("button", "osw-segment-btn osw-subtab");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.title = section.title;
      const icon = el("span", "osw-subtab-icon");
      icon.innerHTML = section.icon || "";
      button.appendChild(icon);
      button.appendChild(el("span", "osw-subtab-label", section.title));
      buttons[section.id] = button;
      button.addEventListener("click", function () {
        if (activeId === section.id) return;
        bridge("osw:haptic:1");
        mount(section.id);
      });
      strip.appendChild(button);
    });

    /* Labels first; the moment they stop fitting next to the title the whole
       strip drops to icons (measured, not a breakpoint guess — the title's
       width depends on the page name and the rail's collapsed state). */
    function fitTabs() {
      const row = tabsWrap.parentNode;
      if (!row) return;
      // Measure with labels visible. Main Menu and Sidebar share the same
      // compact threshold: all destinations keep their Lucide glyphs, while
      // the selected destination retains its label.
      tabsWrap.classList.remove("is-icons");
      if (strip.scrollWidth > tabsWrap.clientWidth + 1) {
        tabsWrap.classList.add("is-icons");
      }
      // These two five-destination pages benefit from compacting before the
      // title itself begins to crowd out. Other tabbed pages compact only when
      // their labels genuinely no longer fit.
      const designerCompact = (page.id === "mainmenu" || page.id === "sidebar") && (
        window.innerWidth <= 1100 || tabsWrap.clientWidth < 760
      );
      if (designerCompact || strip.scrollWidth > tabsWrap.clientWidth + 1) {
        tabsWrap.classList.add("is-icons");
      }
    }
    if (tabbedFitObserver) tabbedFitObserver.disconnect();
    if (window.ResizeObserver) {
      tabbedFitObserver = new ResizeObserver(fitTabs);
      tabbedFitObserver.observe(tabsWrap.parentNode || tabsWrap);
    }
    requestAnimationFrame(fitTabs);

    mount(activeId);
    return true;
  }

  /* A page can own one compact choice in the title row. It uses the same
     field/value plumbing as an ordinary segmented choice, so autosave,
     external refreshes and conditional sections all remain data-driven. */
  function renderPageHeaderChoice(page) {
    const fieldId = page.headerFieldId || "";
    const field = fieldById[fieldId];
    if (!field || field.type !== "choice") return;

    const tabsWrap = document.getElementById("oswPageTabs");
    const strip = el("div", "osw-subtabs-strip osw-page-mode-strip");
    strip.setAttribute("data-field", field.id);
    strip.setAttribute("data-field-type", "choice");
    strip.setAttribute("role", "group");
    strip.setAttribute("aria-label", field.label || page.title);

    (field.options || []).forEach(function (option) {
      const selected = option.value === values[field.id];
      const button = el("button", "osw-segment-btn osw-subtab" + (selected ? " is-active" : ""));
      button.type = "button";
      button.setAttribute("data-value", option.value);
      button.setAttribute("aria-selected", selected ? "true" : "false");
      button.appendChild(el("span", "osw-subtab-label", option.label));
      button.addEventListener("click", function () {
        bridge("osw:haptic:1");
        setValue(field.id, option.value);
      });
      strip.appendChild(button);
    });
    tabsWrap.appendChild(strip);
  }

  function applySettingsComplexity(persist) {
    document.body.setAttribute("data-settings-complexity", settingsComplexity);
    applySimpleProfileDefaults();
    applySimpleSyncDefaults();
    Object.keys(fieldById).forEach(function (id) {
      const field = fieldById[id];
      const selector = '[data-field-host="' + id + '"]';
      let nodes = document.querySelectorAll(selector);
      if (!nodes.length) nodes = document.querySelectorAll('[data-field="' + id + '"]');
      Array.prototype.forEach.call(nodes, function (node) {
        const sectionParity = node.closest('[data-mode-parity="true"]');
        if (field.advanced && !SETTINGS_MODE_PARITY && !sectionParity) node.setAttribute("data-advanced-setting", "true");
        else node.removeAttribute("data-advanced-setting");
        if (field.simpleOnly && !SETTINGS_MODE_PARITY && !sectionParity) node.setAttribute("data-simple-setting", "true");
        else node.removeAttribute("data-simple-setting");
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-complexity]"), function (button) {
      const active = button.getAttribute("data-complexity") === settingsComplexity;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    Array.prototype.forEach.call(document.querySelectorAll(".osw-section"), function (section) {
      // Count every field so a mixed section stays visible when its detailed
      // controls are hidden but ordinary Simple controls remain available.
      const hosts = section.querySelectorAll("[data-field-host], [data-field]");
      if (!hosts.length) {
        section.classList.remove("is-complexity-empty");
        return;
      }
      const visible = Array.prototype.some.call(hosts, function (host) {
        // Inputs nested inside a hidden field inherit that field's mode.
        const hiddenField = host.closest(settingsComplexity === "simple"
          ? '[data-advanced-setting="true"]'
          : '[data-simple-setting="true"]');
        return !hiddenField;
      });
      section.classList.toggle("is-complexity-empty", !visible);
    });
    refreshConditionalBlocks();
    refreshEdgeFades();
    if (persist) bridge("osw:complexity:" + settingsComplexity);
    if (
      !SETTINGS_MODE_PARITY && settingsComplexity === "advanced" &&
      pageById[currentPage] &&
      pageById[currentPage].simpleOnly
    ) {
      const fallbackPage = PAGES.filter(function (page) { return !page.simpleOnly; })[0];
      if (fallbackPage) showPage(fallbackPage.id);
    } else if (persist && pageById[currentPage]) {
      showPage(currentPage);
    }
  }

  function showPage(pageId) {
    closeCompactFontMenu();
    let page = pageById[pageId];
    if (!page) return;
    if (!pageIsAvailable(page)) {
      page = pageIsAvailable(pageById.mainmenu)
        ? pageById.mainmenu
        : PAGES.filter(pageIsAvailable)[0];
      if (!page) return;
      pageId = page.id;
    }
    if (!SETTINGS_MODE_PARITY && settingsComplexity === "advanced" && page.simpleOnly) {
      page = PAGES.filter(function (candidate) { return !candidate.simpleOnly; })[0];
      if (!page) return;
      pageId = page.id;
    }
    currentPage = pageId;
    // Live game state is fetched on demand: everything below paints an empty
    // shape now and repaints when it lands.
    if (page.group === "games") ensureGamesContext();

    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-item]"), function (node) {
      node.classList.toggle("is-active", node.getAttribute("data-nav-item") === pageId);
    });

    document.getElementById("oswPageTitle").textContent = page.title;
    // The page title is the complete header now; descriptions remain in the
    // search index but no longer occupy a second line in Settings.
    document.getElementById("oswPageDesc").textContent = "";

    const host = document.getElementById("oswPage");
    host.innerHTML = "";
    activeDesignerPreviews = [];
    activeWidgetGridPreviews = [];
    stopWidgetGridBackgroundSync();
    const headTabs = document.getElementById("oswPageTabs");
    headTabs.innerHTML = "";
    headTabs.classList.remove("is-icons");
    if (tabbedFitObserver) { tabbedFitObserver.disconnect(); tabbedFitObserver = null; }

    if (page.tabbed && renderTabbedPage(page, host)) {
      // renderTabbedPage mounted the active section itself.
    } else {
      renderPageHeaderChoice(page);
      (page.sections || []).forEach(function (section) {
        if (section.headerOnly) return;
        if (page.id === "profile" && section.layout !== "profile_preview") {
          return;
        }
        host.appendChild(renderSectionBlock(section, page, true));
      });
    }
    const pageScroller = document.getElementById("oswPageScroll");
    pageScroller.scrollTop = 0;
    measureDesc();
    applySettingsComplexity(false);
    // New content means a new scrollHeight, so the bottom fade has to be
    // recomputed even though the scroll position went back to the top.
    refreshEdgeFades();
  }

  // ── search ─────────────────────────────────────────────────────────────────

  function searchableText(parts) {
    return parts.filter(function (part) { return part != null; }).join(" ").toLowerCase();
  }

  const INDEX = {};
  const SEARCH_RECORDS = [];
  Object.keys(pageById).forEach(function (pageId) {
    const page = pageById[pageId];
    const pageParts = [page.title, page.description || "", page.id];
    (page.sections || []).forEach(function (section) {
      let sectionParts = [section.title || "", section.description || "", section.id || ""];
      (section.fields || []).forEach(function (field) {
        const fieldParts = [field.label || "", field.desc || "", field.id || ""];
        (field.notes || []).forEach(function (item) { fieldParts.push(item); });
        (field.items || []).forEach(function (item) { fieldParts.push(item); });
        (field.options || []).forEach(function (option) {
          fieldParts.push(option.label || "", option.sub || "");
        });
        SEARCH_RECORDS.push({
          pageId: pageId,
          sectionId: section.id || "",
          fieldId: field.id,
          pageTitle: page.title,
          simpleOnly: !!page.simpleOnly,
          sectionTitle: section.title || "",
          title: field.label || section.title || page.title,
          desc: field.desc || section.description || "",
          advanced: !!field.advanced,
          text: searchableText(pageParts.concat(sectionParts, fieldParts))
        });
        sectionParts = sectionParts.concat(fieldParts);
      });
      pageParts.push.apply(pageParts, sectionParts);
    });
    INDEX[pageId] = searchableText(pageParts);
  });

  function openSearchRecord(record) {
    if (!SETTINGS_MODE_PARITY && record.advanced && settingsComplexity !== "advanced") {
      settingsComplexity = "advanced";
      applySettingsComplexity(true);
    }
    if (record.sectionId) activeTabByPage[record.pageId] = record.sectionId;
    const input = document.getElementById("oswSearch");
    input.value = "";
    applySearch("");
    showPage(record.pageId);
    requestAnimationFrame(function () {
      const target = document.querySelector('[data-field-host="' + record.fieldId + '"]') ||
        document.querySelector('[data-field="' + record.fieldId + '"]');
      if (!target) return;
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      target.classList.add("osw-search-hit");
      setTimeout(function () { target.classList.remove("osw-search-hit"); }, 1800);
    });
  }

  function renderSearchResults(needle) {
    const matches = SEARCH_RECORDS.filter(function (record) {
      if (!SETTINGS_MODE_PARITY && settingsComplexity === "advanced" && record.simpleOnly) return false;
      if (!pageIsAvailable(pageById[record.pageId])) return false;
      return record.text.indexOf(needle) !== -1;
    }).slice(0, 120);
    document.getElementById("oswPageTitle").textContent = str("search", "Search");
    document.getElementById("oswPageDesc").textContent = matches.length +
      (matches.length === 1 ? " setting found" : " settings found");
    const tabs = document.getElementById("oswPageTabs");
    tabs.innerHTML = "";
    tabs.classList.remove("is-icons");
    const host = document.getElementById("oswPage");
    host.innerHTML = "";
    const list = el("div", "osw-search-results");
    matches.forEach(function (record) {
      const button = el("button", "osw-search-result");
      button.type = "button";
      const trail = [record.pageTitle, record.sectionTitle].filter(Boolean).join(" › ");
      button.appendChild(el("div", "osw-search-result-trail", trail));
      const title = el("div", "osw-search-result-title", record.title || record.fieldId);
      if (!SETTINGS_MODE_PARITY && record.advanced) title.appendChild(el("span", "osw-search-result-badge", str("advanced", "Advanced")));
      button.appendChild(title);
      if (record.desc) button.appendChild(el("div", "osw-search-result-desc", record.desc));
      button.addEventListener("click", function () { openSearchRecord(record); });
      list.appendChild(button);
    });
    if (!matches.length) list.appendChild(el("div", "osw-search-results-empty", "No settings match “" + needle + "”."));
    host.appendChild(list);
    const scroller = document.getElementById("oswPageScroll");
    scroller.scrollTop = 0;
    measureDesc();
    refreshEdgeFades();
  }

  function applySearch(query) {
    const needle = String(query || "").trim().toLowerCase();
    let visible = 0;
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-item]"), function (node) {
      const id = node.getAttribute("data-nav-item");
      const hit = pageIsAvailable(pageById[id]) &&
        (!needle || INDEX[id].indexOf(needle) !== -1);
      node.classList.toggle("is-hidden", !hit);
      if (hit) visible += 1;
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-group]"), function (group) {
      const anyVisible = group.querySelector("[data-nav-item]:not(.is-hidden)");
      group.style.display = anyVisible ? "" : "none";
    });
    const empty = document.getElementById("oswNavEmpty");
    if (empty) empty.style.display = visible ? "none" : "";
    if (needle) renderSearchResults(needle);
    else if (currentPage) showPage(currentPage);
    refreshEdgeFades();
  }

  // ── scroll edge fade ───────────────────────────────────────────────────────

  /* Keeps --osw-fade-top/bottom in step with how far a scroller actually is from
     its ends, so content dissolves into the panel edge instead of being cut off
     square. Proportional on purpose: a fixed fade toggled by a class pops into
     existence on the first pixel of scroll, and CSS cannot transition a
     mask-image, so the length itself is the animation. */
  const EDGE_FADE = 30;

  function updateEdgeFade(node) {
    if (!node) return;
    const top = Math.min(node.scrollTop, EDGE_FADE);
    const remaining = node.scrollHeight - node.clientHeight - node.scrollTop;
    // Sub-pixel scroll heights are common; treat anything under 1px as the end.
    const bottom = Math.min(remaining < 1 ? 0 : remaining, EDGE_FADE);
    node.style.setProperty("--osw-fade-top", top.toFixed(1) + "px");
    node.style.setProperty("--osw-fade-bottom", bottom.toFixed(1) + "px");
  }

  function attachEdgeFade(node) {
    if (!node) return;
    node.addEventListener("scroll", function () { updateEdgeFade(node); }, { passive: true });
    updateEdgeFade(node);
  }

  function refreshEdgeFades() {
    updateEdgeFade(document.getElementById("oswPageScroll"));
    updateEdgeFade(document.getElementById("oswNav"));
  }

  // ── collapsing page description ────────────────────────────────────────────

  /* The description folds into the header as the page scrolls, at a 1:1 pace
     with the scroll itself — driven straight from scrollTop on every scroll
     event, never a CSS transition — so it always tracks the wheel/finger
     exactly, with nothing to catch up on and nothing that can pop. Scrolling
     back to the top reverses it the same way. The fold distance is the
     description's own natural height, so it reads as the text being carried
     away by the content beneath it rather than shrinking on an arbitrary
     timer — a short description tucks away almost immediately, a long one
     takes longer, both feeling equally "1:1". */
  let descMaxHeight = 0;
  let descMarginTop = 0;

  function measureDesc() {
    const desc = document.getElementById("oswPageDesc");
    if (!desc) return;
    // Clear any inline override from the previous page/scroll position before
    // reading the natural size, or this measures the already-collapsed state.
    desc.style.maxHeight = "";
    desc.style.marginTop = "";
    desc.style.opacity = "";
    descMaxHeight = desc.scrollHeight;
    descMarginTop = parseFloat(getComputedStyle(desc).marginTop) || 0;
    const scroller = document.getElementById("oswPageScroll");
    if (scroller) {
      updateDescCollapse(scroller);
    }
  }

  function updateDescCollapse(scroller) {
    const desc = document.getElementById("oswPageDesc");
    if (!desc || !scroller || !descMaxHeight) return;
    if (scroller.scrollTop === 0) {
      desc.style.maxHeight = "";
      desc.style.marginTop = "";
      desc.style.opacity = "";
      return;
    }
    const t = Math.max(0, Math.min(1, scroller.scrollTop / descMaxHeight));
    desc.style.maxHeight = ((1 - t) * descMaxHeight).toFixed(1) + "px";
    desc.style.marginTop = ((1 - t) * descMarginTop).toFixed(1) + "px";
    desc.style.opacity = (1 - t).toFixed(3);
  }

  // ── toast ──────────────────────────────────────────────────────────────────

  function toast(message, options) {
    const node = document.getElementById("oswToast");
    if (!node || !message) return;
    const simpleNotice = options && options.simpleNotice;
    node.classList.toggle("is-simple-notice", !!simpleNotice);
    node.textContent = "";
    if (simpleNotice) {
      const logo = el("img", "osw-toast-logo");
      logo.src = CTX.addonBase + "system_files/onigiri_mini_logo.svg";
      logo.alt = "";
      logo.setAttribute("aria-hidden", "true");
      node.appendChild(logo);
      node.appendChild(el("span", "osw-toast-message", message));
    } else {
      node.textContent = message;
    }
    node.classList.add("is-visible");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.classList.remove("is-visible"); }, simpleNotice ? 5500 : 3200);
  }

  // ── boot ───────────────────────────────────────────────────────────────────

  // ── rail (pinned open / collapsed to icons) ────────────────────────────────

  let railCollapsed = !!CTX.railCollapsed;

  function applyRail(persist) {
    const shell = document.getElementById("oswShell");
    shell.classList.toggle("is-collapsed", railCollapsed);
    const toggle = document.getElementById("oswRailToggle");
    toggle.setAttribute("aria-expanded", railCollapsed ? "false" : "true");
    const icons = CTX.chromeIcons || {};
    const glyph = railCollapsed ? icons.railExpand : icons.railCollapse;
    if (glyph) toggle.innerHTML = glyph;
    refreshEdgeFades();
    // Rail width is window chrome, not a setting: it persists on its own.
    if (persist) bridge("osw:rail:" + (railCollapsed ? "1" : "0"));
  }

  function setIcon(hostId, selector, svg) {
    const host = document.getElementById(hostId);
    if (!host || !svg) return;
    const slot = selector ? host.querySelector(selector) : host;
    if (slot) slot.innerHTML = svg;
  }

  function wireChrome() {
    const icons = CTX.chromeIcons || {};
    // The rail toggle's glyph is set by applyRail(), which knows the direction.
    setIcon("oswDonate", ".osw-rail-action-icon", icons.donate);
    setIcon("oswBugs", ".osw-rail-action-icon", icons.bugs);
    setIcon("oswDone", ".osw-btn-icon", icons.done);

    document.querySelector("#oswDonate .osw-rail-action-label").textContent =
      str("donate", "Donate");
    document.querySelector("#oswBugs .osw-rail-action-label").textContent =
      str("report_bugs", "Report bugs");
    document.querySelector("#oswDone .osw-btn-label").textContent = str("done", "Done");
    document.getElementById("oswSearch").placeholder = str("search", "Search");
    const complexityButtons = document.querySelectorAll("[data-complexity]");
    Array.prototype.forEach.call(complexityButtons, function (button) {
      const mode = button.getAttribute("data-complexity");
      button.textContent = mode === "advanced" ? str("advanced", "Advanced") : str("simple", "Simple");
      button.addEventListener("click", function () {
        if (settingsComplexity === mode) return;
        settingsComplexity = mode;
        applySettingsComplexity(true);
        if (mode === "simple") {
          toast(str("simple_mode_notice", "Simple Mode hides some Onigiri customization options. Switch to Advanced to see them all."), { simpleNotice: true });
        } else {
          const notice = document.getElementById("oswToast");
          if (notice && notice.classList.contains("is-simple-notice")) {
            notice.classList.remove("is-visible");
            if (toastTimer) clearTimeout(toastTimer);
          }
        }
      });
    });

    document.getElementById("oswRailToggle").addEventListener("click", function () {
      railCollapsed = !railCollapsed;
      applyRail(true);
      // Expanding from the toggle is usually a prelude to searching or reading
      // labels, so don't steal focus; collapsing must drop focus out of the
      // now-hidden search field or typing would go nowhere visible.
      if (railCollapsed) document.getElementById("oswSearch").blur();
    });
    document.getElementById("oswDonate").addEventListener("click", function () {
      bridge("osw:donate:");
    });
    document.getElementById("oswBugs").addEventListener("click", function () {
      bridge("osw:bugs:");
    });
    document.getElementById("oswDone").addEventListener("click", function () {
      flush();
      bridge("osw:close:");
    });
    document.getElementById("oswSearch").addEventListener("input", function (event) {
      applySearch(event.target.value);
    });
    document.addEventListener("keydown", function (event) {
      // The gallery popover owns the keyboard while it is up — most of all
      // Escape, which must dismiss the popover rather than the whole window.
      if (galleryOpen()) return;
      if ((event.metaKey || event.ctrlKey) && event.key === "s") {
        // Nothing to save on demand, but muscle memory shouldn't feel broken:
        // force the pending patch out now instead of waiting for the debounce.
        event.preventDefault();
        if (flushTimer) clearTimeout(flushTimer);
        flush();
      }
      if (event.key === "Escape") {
        const search = document.getElementById("oswSearch");
        if (document.activeElement === search && search.value) {
          search.value = "";
          applySearch("");
          return;
        }
        flush();
        bridge("osw:close:");
      }
    });
  }

  applyTheme();
  buildNav();
  wireChrome();
  const mainScroller = document.getElementById("oswPageScroll");
  attachEdgeFade(mainScroller);
  attachEdgeFade(document.getElementById("oswNav"));
  if (mainScroller) {
    mainScroller.addEventListener("scroll", function () {
      updateDescCollapse(mainScroller);
    }, { passive: true });
  }
  window.addEventListener("resize", function () {
    measureDesc();
    refreshEdgeFades();
  });
  applyRail(false);
  applySettingsComplexity(false);
  setStatus("idle");
  if (currentPage) showPage(currentPage);

  window.onigiriSettings = {
    showPage: showPage,
    toast: toast,
    setGridBackground: function (background) {
      if (activeWidgetGridBackgroundReceiver) activeWidgetGridBackgroundReceiver(background);
    },
    afterNativeShow: function () {
      measureDesc();
      refreshEdgeFades();
    },
    /* Called from Python after a native picker returns a value. */
    setFieldValue: function (id, value) {
      // Resolved before the write: a linked colour pair is recognised by its
      // two colours being equal, which stops being true the moment one moves.
      const linked = linkedPairForLightKey(id);
      // The native picker has no alpha channel, so a colour that carries one
      // (the level chip's background) would come back opaque.
      const next = chipPreserveAlpha(id, value);
      setValue(id, next);
      if (linked) setValue(linked.darkField, next);
    }
  };
  setInterval(refreshLiveProfileContext, 1000);
  window.addEventListener("focus", refreshLiveProfileContext);
  // Qt checks this marker after loadFinished. Removing the HTML guard first
  // means the dialog's first visible frame already has the final theme,
  // populated navigation, active page, labels, and button styling. Do not use
  // pycmd for this startup signal: Anki may install that bridge slightly later.
  document.documentElement.classList.remove("osw-booting");
  document.documentElement.classList.add("osw-ready");
})();
