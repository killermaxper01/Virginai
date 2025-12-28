importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "YOUR_API_KEY",
  authDomain: "virginai-6b615.firebaseapp.com",
  projectId: "virginai-6b615",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
});

const messaging = firebase.messaging();

/**
 * 🔥 BACKGROUND / CLOSED TAB
 */
messaging.onBackgroundMessage(function (payload) {
  console.log("[SW] Background message:", payload);

  const title = payload.data?.title || "VirginAI 🔔";
  const options = {
    body: payload.data?.body || "New update",
    icon: "/icon-192.png",
    data: {
      url: payload.data?.url || "/"
    }
  };

  self.registration.showNotification(title, options);
});

/**
 * 🔔 CLICK ACTION
 */
self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  const url = event.notification.data?.url || "/";

  event.waitUntil(
    clients.matchAll({ type: "window" }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});