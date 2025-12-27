// firebase-messaging.js

import { app, auth, db } from "./firebase.js";

import {
  getMessaging,
  getToken,
  onMessage
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";

import {
  doc,
  setDoc
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

import {
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

// -------------------- INIT --------------------
const messaging = getMessaging(app);
let swRegistration = null;

// -------------------- REGISTER SERVICE WORKER --------------------
if ("serviceWorker" in navigator) {
  try {
    swRegistration = await navigator.serviceWorker.register(
      "/firebase-messaging-sw.js"
    );
    console.log("✅ Service Worker registered");
  } catch (err) {
    console.error("❌ SW registration failed:", err);
  }
}

// -------------------- REQUEST PERMISSION + SAVE TOKEN --------------------
export async function initNotifications() {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      console.warn("🔕 Notifications blocked by user");
      return;
    }

    const token = await getToken(messaging, {
      vapidKey: "BECWG_Ge9EOcfeDcuRvLOIKvhpUFGCPMU1GenJKDHyDuPR65efUtZVQSvERWTMs2kxt9mg6UvY7sBFwVnrLARjo",
      serviceWorkerRegistration: swRegistration
    });

    if (!token) {
      console.warn("⚠️ FCM token not generated");
      return;
    }

    console.log("✅ FCM TOKEN:", token);

    onAuthStateChanged(auth, async (user) => {
      if (!user) return;

      await setDoc(
        doc(db, "users", user.uid),
        {
          fcmToken: token,
          platform: "web",
          notificationsEnabled: true,
          updatedAt: Date.now()
        },
        { merge: true }
      );

      console.log("✅ Token saved to Firestore");
    });

  } catch (err) {
    console.error("❌ Notification init failed:", err);
  }
}

// -------------------- FOREGROUND NOTIFICATION --------------------
// 👉 Works when TAB is OPEN
onMessage(messaging, (payload) => {
  console.log("🔔 Foreground message:", payload);

  if (!payload.notification) return;

  new Notification(payload.notification.title, {
    body: payload.notification.body,
    icon: "/android-chrome-192x192.png",
    badge: "/android-chrome-192x192.png",
    silent: false
  });
});