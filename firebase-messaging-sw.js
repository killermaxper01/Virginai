/* firebase-messaging-sw.js */

importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js");

// 🔹 Firebase config (SAME project as frontend)
firebase.initializeApp({
  apiKey: "AIzaSyCt27Y4VmFPGgMvqvKYv5jcI90N8VoUHfY",
  authDomain: "virginai-6b615.firebaseapp.com",
  projectId: "virginai-6b615",
  messagingSenderId: "444972440350",
  appId: "1:444972440350:web:03651aa7be5213c710470f"
});

const messaging = firebase.messaging();

/**
 * ✅ BACKGROUND & CLOSED STATE
 * Works ONLY with `data:{}` payload (which you are using correctly)
 */
messaging.onBackgroundMessage((payload) => {
  console.log("[SW] Background message received:", payload);

  const title = payload.data?.title || "VirginAI 🔔";
  const options = {
    body: payload.data?.body || "New notification",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: {
      url: payload.data?.url || "https://virginai.in"
    },
    vibrate: [200, 100, 200]
  };

  self.registration.showNotification(title, options);
});

/**
 * ✅ NOTIFICATION CLICK
 */
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === event.notification.data.url && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(event.notification.data.url);
      }
    })
  );
});