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

// -------------------- INIT MESSAGING --------------------
const messaging = getMessaging(app);

// -------------------- REQUEST PERMISSION + SAVE TOKEN --------------------
export async function initNotifications() {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      console.warn("🔕 Notification permission denied");
      return;
    }

    const token = await getToken(messaging, {
      vapidKey: "BECWG_Ge9EOcfeDcuRvLOIKvhpUFGCPMU1GenJKDHyDuPR65efUtZVQSvERWTMs2kxt9mg6UvY7sBFwVnrLARjo"
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
          updatedAt: Date.now()
        },
        { merge: true }
      );

      console.log("✅ FCM token saved to Firestore");
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