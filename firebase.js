// firebase.js (frontend-safe)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyCt27Y4VmFPGgMvqvKYv5jcI90N8VoUHfY",
  authDomain: "virginai-6b615.firebaseapp.com",
  projectId: "virginai-6b615",
  storageBucket: "virginai-6b615.firebasestorage.app",
  messagingSenderId: "444972440350",
  appId: "1:444972440350:web:03651aa7be5213c710470f"
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);