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

messaging.onBackgroundMessage(payload => {
  self.registration.showNotification(
    payload.notification.title,
    {
      body: payload.notification.body,
      icon: "/logo.png"
    }
  );
});