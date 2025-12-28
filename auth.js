import { auth } from "./firebase.js";
import {
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const path = window.location.pathname;

onAuthStateChanged(auth, (user) => {

  // ❌ NOT LOGGED IN → BLOCK INDEX
  if (!user && path.includes("index")) {
    console.log("❌ Not logged in → redirect to login");
    window.location.replace("/login.html");
    return;
  }

  // ✅ LOGGED IN → BLOCK LOGIN & SIGNUP
  if (user && (path.includes("login") || path.includes("signup"))) {
    console.log("✅ Logged in → redirect to index");
    window.location.replace("/index.html");
  }

});