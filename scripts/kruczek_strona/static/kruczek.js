// Kruczek — motyw z ustawień systemu i przycisk „Kopiuj”. Bez zależności i bez kodu inline (CSP: 'self').
(() => {
  const ciemny = window.matchMedia("(prefers-color-scheme: dark)");
  const ustawMotyw = () => { document.documentElement.dataset.theme = ciemny.matches ? "dark" : "light"; };
  ustawMotyw();
  ciemny.addEventListener("change", ustawMotyw);

  document.addEventListener("click", async (zdarzenie) => {
    const przycisk = zdarzenie.target.closest("[data-kopiuj]");
    if (!przycisk) return;
    const pole = document.getElementById(przycisk.dataset.kopiuj);
    const komunikat = document.getElementById(`${przycisk.dataset.kopiuj}-komunikat`);
    const etykieta = przycisk.querySelector("[data-etykieta]");
    try {
      await navigator.clipboard.writeText(pole.value);
      przycisk.dataset.copied = "";
      etykieta.textContent = "Skopiowano";
      komunikat.textContent = "Skopiowano polecenie do schowka. Wklej je w rozmowie z Claude.";
      setTimeout(() => {
        delete przycisk.dataset.copied;
        etykieta.textContent = "Kopiuj";
        komunikat.textContent = "";
      }, 2000);
    } catch {
      pole.focus();
      pole.select();
      komunikat.textContent = "Zaznaczono — skopiuj skrótem ⌘C albo Ctrl+C.";
    }
  });
})();
