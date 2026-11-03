// UC Merced CAPE Election Lab: page views and clicks, counted with GoatCounter (no cookies, no personal data).
// Every page loads this file. Pages count as path + hash (so each race page counts separately); taps on tabs,
// buttons and links count as events named "tab:…", "link:…", "out:…", "open:…".
(function () {
  if (location.hostname !== "lab.nathanwmonroe.com") return;
  window.goatcounter = { no_onload: true, no_events: true };
  var s = document.createElement("script"); s.async = true; s.src = "https://gc.zgo.at/count.js";
  s.setAttribute("data-goatcounter", "https://capelab.goatcounter.com/count"); document.head.appendChild(s);
  var base = location.pathname.replace(/index\.html$/, "");
  function page() { return base + (location.search || "") + (location.hash || ""); }
  function send(o) { try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count(o); } catch (e) { } }
  var lastPage = null;
  function view() { var p = page(); if (p === lastPage) return; lastPage = p; send({ path: p, title: document.title }); }
  s.onload = view;
  addEventListener("hashchange", view);
  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("button,a,summary") : null; if (!el) return;
    var t = (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40);
    var name;
    if (el.tagName === "A") {
      var h = el.getAttribute("href") || "";
      if (/^https?:/.test(h) && h.indexOf("lab.nathanwmonroe.com") < 0) name = "out:" + h.replace(/^https?:\/\//, "").slice(0, 60);
      else name = "link:" + (t || h.slice(0, 40));
    } else if (el.tagName === "SUMMARY") name = "open:" + t;
    else name = "tab:" + t;
    send({ path: base + " " + name, title: name, event: true });
  }, true);
})();
