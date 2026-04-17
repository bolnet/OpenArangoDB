// Signal Room — small interactions only.
// (1) live-refresh pulse on the footer, (2) layer-toggle visual state.

(function () {
  document.querySelectorAll(".layer-toggles input[type='checkbox']").forEach((box) => {
    const wrap = box.closest(".layer-toggle");
    const sync = () => wrap.classList.toggle("layer-toggle--on", box.checked);
    sync();
    box.addEventListener("change", sync);
  });

  // kbd-jump: "/" focuses the first visible search field
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !(e.target instanceof HTMLInputElement)) {
      const q = document.querySelector("input[name='q']");
      if (q) { e.preventDefault(); q.focus(); q.select(); }
    }
  });
})();
