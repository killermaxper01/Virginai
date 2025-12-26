import { auth } from "./firebase.js";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  signInWithPopup
} from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

const provider = new GoogleAuthProvider();

window.login = async () => {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  try {
    await signInWithEmailAndPassword(auth, email, password);
    window.location.href = "/";
  } catch (e) {
    alert(e.message);
  }
};

window.googleLogin = async () => {
  try {
    await signInWithPopup(auth, provider);
    window.location.href = "/";
  } catch (e) {
    alert(e.message);
  }
};