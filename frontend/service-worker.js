const CACHE_NAME = "aether-shell-v38-payment-work-queue";
const SHARE_DATABASE = "aether-share-target";
const SHARE_STORE = "receipts";
const APP_SHELL = [
  "/app/",
  "/app/index.html",
  "/app/scripts/app-core.js",
  "/app/scripts/app-assets.js",
  "/app/scripts/app-services.js",
  "/app/scripts/app-billing.js",
  "/app/scripts/app-operations.js",
  "/app/scripts/app-administration.js",
  "/app/scripts/app-events.js",
  "/app/styles.css",
  "/app/assets/aether-mark.png",
  "/app/assets/aether-horizontal.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.pathname === "/app/share" && request.method === "POST") {
    event.respondWith(receiveSharedReceipt(request));
    return;
  }
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }
  if (APP_SHELL.includes(url.pathname)) {
    const cacheKey = new Request(`${url.origin}${url.pathname}`);
    event.respondWith(networkFirst(request, cacheKey));
    return;
  }
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});

async function networkFirst(request, cacheKey = request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(cacheKey, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(cacheKey);
    if (cached) return cached;
    throw error;
  }
}

function shareDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SHARE_DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(SHARE_STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function receiveSharedReceipt(request) {
  const formData = await request.formData();
  const file = findSharedReceiptFile(formData);
  if (!file) {
    return Response.redirect("/app/?shared_error=missing-file", 303);
  }
  const id = crypto.randomUUID();
  const entry = {
    id,
    file,
    fileName: file.name || sharedReceiptFileName(file.type),
    fileType: file.type || "application/octet-stream",
    title: String(formData.get("title") || ""),
    text: String(formData.get("text") || ""),
    url: String(formData.get("url") || ""),
    receivedAt: Date.now(),
  };
  const database = await shareDatabase();
  await new Promise((resolve, reject) => {
    const transaction = database.transaction(SHARE_STORE, "readwrite");
    transaction.objectStore(SHARE_STORE).put(entry);
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
  return Response.redirect(`/app/?shared_receipt=${encodeURIComponent(id)}`, 303);
}

function findSharedReceiptFile(formData) {
  // Android share targets are not consistent about preserving the manifest's
  // field name or the File prototype. Search every multipart value and accept
  // any non-empty binary payload that the browser can store in IndexedDB.
  const preferredNames = ["proof_file", "file", "files", "image", "photo"];
  const candidates = preferredNames.flatMap((name) => formData.getAll(name));
  for (const [, value] of formData.entries()) candidates.push(value);
  return candidates.find((value) => (
    value
    && typeof value === "object"
    && typeof value.arrayBuffer === "function"
    && Number(value.size) > 0
  )) || null;
}

function sharedReceiptFileName(contentType = "") {
  if (contentType === "application/pdf") return "comprobante-compartido.pdf";
  if (contentType === "image/png") return "comprobante-compartido.png";
  if (contentType === "image/webp") return "comprobante-compartido.webp";
  return "comprobante-compartido.jpg";
}
