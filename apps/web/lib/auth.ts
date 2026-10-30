import { FIREBASE_CONFIG } from "@/lib/env";

export interface SignedInUser {
  email: string | null;
}

/** Firebase is imported on first use, so pages that never sign anyone in never download it. */
async function firebase() {
  if (!FIREBASE_CONFIG.apiKey || !FIREBASE_CONFIG.projectId) {
    throw new Error("Sign-in is not configured.");
  }
  const [{ getApp, getApps, initializeApp }, auth] = await Promise.all([
    import("firebase/app"),
    import("firebase/auth"),
  ]);
  const app = getApps().length > 0 ? getApp() : initializeApp(FIREBASE_CONFIG);
  return { auth: auth.getAuth(app), module: auth };
}

export async function onAuthChange(callback: (user: SignedInUser | null) => void): Promise<() => void> {
  const { auth, module } = await firebase();
  return module.onAuthStateChanged(auth, (user) => callback(user ? { email: user.email } : null));
}

export async function signInWithGoogle(): Promise<void> {
  const { auth, module } = await firebase();
  await module.signInWithPopup(auth, new module.GoogleAuthProvider());
}

export async function signOutUser(): Promise<void> {
  const { auth, module } = await firebase();
  await module.signOut(auth);
}

/** A fresh ID token for the API. Firebase refreshes it automatically when it is near expiry. */
export async function getIdToken(): Promise<string | null> {
  const { auth } = await firebase();
  return (await auth.currentUser?.getIdToken()) ?? null;
}
