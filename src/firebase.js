import { initializeApp } from "firebase/app";
import { createUserWithEmailAndPassword, getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithEmailAndPassword, signInWithPopup, signOut, updateProfile } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

const requiredKeys = ["apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId"];
const missingFirebaseConfig = requiredKeys.filter((key) => !firebaseConfig[key]);
const maskedConfig = {
  ...firebaseConfig,
  apiKey: firebaseConfig.apiKey ? `${firebaseConfig.apiKey.slice(0, 6)}…${firebaseConfig.apiKey.slice(-4)}` : "missing",
};
export let firebaseEnabled = false;
let app = null;
let auth = null;
let provider = null;
export let firebaseInitializationError = null;

console.info("[Firebase] Vite configuration received:", maskedConfig);
if (missingFirebaseConfig.length) {
  firebaseInitializationError = new Error(`Firebase configuration is missing: ${missingFirebaseConfig.join(", ")}.`);
  console.error("[Firebase] Initialization skipped. Missing Vite variables:", missingFirebaseConfig.map((key) => `VITE_FIREBASE_${key.replace(/[A-Z]/g, (letter) => `_${letter}`).toUpperCase()}`));
} else {
  try {
    app = initializeApp(firebaseConfig);
    console.info("[Firebase] initializeApp succeeded for project:", firebaseConfig.projectId);
    try {
      auth = getAuth(app);
      console.info("[Firebase] getAuth succeeded.");
    } catch (error) {
      throw new Error(`getAuth failed: ${error.code || "unknown"} ${error.message || error}`);
    }
    try {
      provider = new GoogleAuthProvider();
      console.info("[Firebase] GoogleAuthProvider succeeded.");
    } catch (error) {
      throw new Error(`GoogleAuthProvider failed: ${error.code || "unknown"} ${error.message || error}`);
    }
    firebaseEnabled = true;
  } catch (error) {
    firebaseInitializationError = error instanceof Error ? error : new Error(String(error));
    console.error("[Firebase] Authentication initialization failed:", { code: firebaseInitializationError.code || "unknown", message: firebaseInitializationError.message });
  }
}

const configuredApiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE_URL = configuredApiBase.startsWith("/") ? "http://localhost:8000" : configuredApiBase.replace(/\/+$/, "");

async function synchronizeUser(user) {
  const response = await fetch(`${API_BASE_URL}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: user.displayName || user.email?.split("@")[0] || "Traveler", email: user.email, firebase_uid: user.uid, profile_photo: user.photoURL || null }),
  });
  if (!response.ok) throw new Error("Signed in, but we could not synchronize your travel profile.");
}

function requireAuth() {
  if (auth) return auth;
  if (firebaseInitializationError) throw firebaseInitializationError;
  throw new Error("Firebase Authentication could not be initialized.");
}

export function subscribeToAuth(callback) { return auth ? onAuthStateChanged(auth, callback) : (callback(null), () => {}); }
export async function loginWithGoogle() { if (!provider) requireAuth(); const user = (await signInWithPopup(requireAuth(), provider)).user; await synchronizeUser(user); return user; }
export async function loginWithEmail(email, password) { const user = (await signInWithEmailAndPassword(requireAuth(), email, password)).user; await synchronizeUser(user); return user; }
export async function registerWithEmail(name, email, password) { const credential = await createUserWithEmailAndPassword(requireAuth(), email, password); await updateProfile(credential.user, { displayName: name }); const user = { ...credential.user, displayName: name }; await synchronizeUser(user); return user; }
export async function logout() { if (auth) await signOut(auth); }
