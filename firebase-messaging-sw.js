/* firebase-messaging-sw.js */

// -------------------- IMPORT FIREBASE --------------------
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js");

// -------------------- FIREBASE INIT --------------------
firebase.initializeApp({
  apiKey: "AIzaSyCt27Y4VmFPGgMvqvKYv5jcI90N8VoUHfY",
  authDomain: "virginai-6b615.firebaseapp.com",
  projectId: "virginai-6b615",
  messagingSenderId: "444972440350",
  appId: "1:444972440350:web:03651aa7be5213c710470f"
});

// -------------------- MESSAGING INSTANCE --------------------
const messaging = firebase.messaging();

// -------------------- BACKGROUND NOTIFICATION --------------------
// 👉 Works when TAB is CLOSED / MINIMIZED
messaging.onBackgroundMessage((payload) => {
  console.log("[SW] Background message:", payload);

  const title = payload.notification?.title || "VirginAI 🔔";
  const options = {
    body: payload.notification?.body || "You have a new update",
    icon: "/android-chrome-192x192.png",   // ✅ MAIN ICON
    badge: "/android-chrome-192x192.png",  // ✅ ANDROID BADGE
    vibrate: [200, 100, 200],
    data: {
      url: "https://virginai.in"
    }
  };

  self.registration.showNotification(title, options);
});

// -------------------- NOTIFICATION CLICK --------------------
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url === "https://virginai.in" && "focus" in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow("https://virginai.in");
        }
      })
  );
});