// firebase-messaging.js

import { app, auth, db } from "./firebase.js";
import { getMessaging, getToken, onMessage } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";
import { doc, setDoc } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { onAuthStateChanged } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const messaging = getMessaging(app);

// ✅ Service Worker registration
const swReg = await navigator.serviceWorker.register("/firebase-messaging-sw.js");

export async function initNotifications() {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return;

  const token = await getToken(messaging, {
    vapidKey: "BECWG_Ge9EOcfeDcuRvLOIKvhpUFGCPMU1GenJKDHyDuPR65efUtZVQSvERWTMs2kxt9mg6UvY7sBFwVnrLARjo",
    serviceWorkerRegistration: swReg
  });

  if (!token) return;

  onAuthStateChanged(auth, async (user) => {
    if (!user) return;

    await setDoc(doc(db, "users", user.uid), {
      fcmToken: token,
      platform: "web",
      updatedAt: Date.now()
    }, { merge: true });
  });
}

// ✅ FOREGROUND NOTIFICATION (SYSTEM LEVEL)
onMessage(messaging, (payload) => {
  console.log("Foreground message:", payload);

  if (Notification.permission !== "granted") return;

  new Notification(payload.data?.title || "VirginAI 🔔", {
    body: payload.data?.body || "New message",
    icon: "/icon-192.png",
    data: {
      url: payload.data?.url || "/"
    }
  });
});