import { app, auth, db } from "./firebase.js";
import { getMessaging, getToken, onMessage }
from "https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging.js";
import { doc, setDoc }
from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { onAuthStateChanged }
from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const messaging = getMessaging(app);

export async function initNotifications() {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return;

  const token = await getToken(messaging, {
    vapidKey: "BECWG_Ge9EOcfeDcuRvLOIKvhpUFGCPMU1GenJKDHyDuPR65efUtZVQSvERWTMs2kxt9mg6UvY7sBFwVnrLARjo"
  });

  if (!token) return;

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
  });
}

// Foreground notifications
onMessage(messaging, (payload) => {
  new Notification(payload.notification.title, {
    body: payload.notification.body,
    icon: "/android-chrome-512x512.png"
  });
});