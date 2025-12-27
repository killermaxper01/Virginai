// firebase-messaging-sw.js

importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyCt27Y4VmFPGgMvqvKYv5jcI90N8VoUHfY",
  authDomain: "virginai-6b615.firebaseapp.com",
  projectId: "virginai-6b615",
  messagingSenderId: "444972440350",
  appId: "1:444972440350:web:03651aa7be5213c710470f"
});

const messaging = firebase.messaging();

// ✅ DATA MESSAGE HANDLER (MOST IMPORTANT)
messaging.onBackgroundMessage((payload) => {
  console.log("[SW] DATA MESSAGE:", payload);

  const title = payload.data?.title || "VirginAI 🔔";
  const options = {
    body: payload.data?.body || "New update available",
    icon: "/android-chrome-192x192.png",
    badge: "/android-chrome-192x192.png",
    data: { url: payload.data?.url || "https://virginai.in" },
    vibrate: [200, 100, 200]
  };

  self.registration.showNotification(title, options);
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});