/* Meta Pixel for djlabsiam.com — NOT used on /book/ (that page holds customers' names and phone numbers).
   The Pixel ID lives in this file and nowhere else. Empty = nothing loads, nothing is shown, no request leaves the page.
   Only three things are counted: PageView · ViewContent on /courses/ and /teachers/* · Contact when a LINE or phone link is pressed.
   Nothing the visitor typed and no link address is ever sent; advanced matching is off (autoConfig false, no user data passed to init). */
(function () {
  "use strict";
  var PIXEL_ID = "3603381756488600";   // dataset "DJ LAB SIAM" in Events Manager · digits only (15–16) · empty keeps the Pixel switched off
  var KEY = "djl_pixel_off";    // localStorage: "1" = the visitor turned measurement off in this browser

  if (!PIXEL_ID) return;

  var TEXT = {
    th: { off: "ปิดการวัดผลโฆษณา", on: "เปิดการวัดผลโฆษณาอีกครั้ง", stOn: "วัดผลโฆษณาด้วย Meta Pixel: เปิดอยู่", stOff: "วัดผลโฆษณาด้วย Meta Pixel: ปิดอยู่", stSig: "วัดผลโฆษณาด้วย Meta Pixel: ปิดอยู่ ตามการตั้งค่าเบราว์เซอร์ของคุณ (Do Not Track / GPC)" },
    en: { off: "Turn off ad measurement", on: "Turn ad measurement back on", stOn: "Ad measurement with Meta Pixel: on", stOff: "Ad measurement with Meta Pixel: off", stSig: "Ad measurement with Meta Pixel: off, following your browser setting (Do Not Track / GPC)" }
  };

  var signal = navigator.doNotTrack === "1" || navigator.doNotTrack === "yes" || window.doNotTrack === "1" ||
    navigator.msDoNotTrack === "1" || navigator.globalPrivacyControl === true;

  function stored() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function store(off) { try { if (off) localStorage.setItem(KEY, "1"); else localStorage.removeItem(KEY); } catch (e) { /* storage blocked: the choice lasts for this page only */ } }

  var off = signal || stored();
  var started = false;

  // Only the page's name goes to Meta (taken from the path, never from page text or the query string).
  function pageName() {
    var p = location.pathname.replace(/index\.html$/, "");
    if (p === "/") return "home";
    if (p === "/courses/") return "courses";
    var t = p.match(/^\/teachers\/([a-z0-9-]+)\/$/);
    if (t) return "teacher-" + t[1];
    if (p === "/content/") return "content";
    if (p === "/privacy.html") return "privacy-th";
    if (p === "/privacy-en.html") return "privacy-en";
    return "other";
  }

  function start() {
    if (started) return;
    started = true;
    !function (f, b, e, v, n, t, s) {
      if (f.fbq) return;
      n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
      if (!f._fbq) f._fbq = n;
      n.push = n; n.loaded = true; n.version = "2.0"; n.queue = [];
      t = b.createElement(e); t.async = true; t.src = v;
      s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
    }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
    fbq("set", "autoConfig", false, PIXEL_ID);
    fbq("init", PIXEL_ID);
    fbq("track", "PageView");
    var n = pageName();
    if (n === "courses" || n.indexOf("teacher-") === 0) {
      fbq("track", "ViewContent", { content_name: n, content_category: n === "courses" ? "courses" : "teacher" });
    }
  }

  // Pressing a LINE or phone link counts as Contact; only the channel is sent, never the address (it can carry a pre-filled message).
  document.addEventListener("click", function (e) {
    if (off || !started || !e.target.closest) return;
    var a = e.target.closest("a[href]");
    if (!a) return;
    var h = a.getAttribute("href") || "";
    var channel = /^tel:/i.test(h) ? "tel" : /^https?:\/\/(line\.me|lin\.ee)\//i.test(h) ? "line" : "";
    if (channel) fbq("track", "Contact", { content_name: pageName(), channel: channel });
  }, true);

  function clearCookies() {
    var host = location.hostname, parts = host.split("."), apex = parts.length > 1 ? "." + parts.slice(-2).join(".") : "";
    ["_fbp", "_fbc"].forEach(function (name) {
      [ "", ";domain=" + host, apex ? ";domain=" + apex : "" ].forEach(function (d) {
        document.cookie = name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/" + d;
      });
    });
  }

  var row = document.querySelector("[data-pixel-row]");
  var btn = row && row.querySelector("[data-pixel-toggle]");
  var state = row && row.querySelector("[data-pixel-state]");
  if (row && btn && state) {
    var css = document.createElement("style");
    css.textContent =
      "[data-pixel-row]{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:16px 0 0;font-size:14px;line-height:1.6}" +
      ".foot>[data-pixel-row]{grid-column:1/-1;margin:0}" +
      "[data-pixel-toggle]{font:inherit;font-size:14px;font-weight:600;color:inherit;background:transparent;border:1px solid currentColor;border-radius:0;padding:10px 16px;min-height:44px;cursor:pointer}" +
      "[data-pixel-toggle]:disabled{opacity:.6;cursor:default}" +
      "[data-pixel-row][hidden]{display:none}";
    document.head.appendChild(css);
    var paint = function () {
      var t = TEXT[(document.documentElement.lang || "th").slice(0, 2)] || TEXT.th;
      btn.textContent = off ? t.on : t.off;
      btn.disabled = signal;
      state.textContent = signal ? t.stSig : off ? t.stOff : t.stOn;
    };
    btn.addEventListener("click", function () {
      if (signal) return;
      off = !off;
      store(off);
      if (off) clearCookies(); else start();
      paint();
    });
    paint();
    row.hidden = false;
  }

  if (!off) start();
})();
