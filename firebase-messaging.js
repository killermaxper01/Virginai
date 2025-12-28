// firebase-messaging.js

import { app, auth, db } from "./firebase.js";
import { getMessaging, getToken, onMessage } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";
import { doc, setDoc } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { onAuthStateChanged } from
  "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const messaging = getMessaging(app);

// ✅ Service Worker registration (REQUIRED)
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

// ✅ FOREGROUND MESSAGE HANDLER (TAB OPEN)
onMessage(messaging, (payload) => {
  console.log("Foreground message:", payload);

  // Allowed: in-app UI (NOT browser popup)
  alert(`${payload.data.title}\n\n${payload.data.body}`);
});