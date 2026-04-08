import { create } from "zustand";
import {
  fetchCurrentUser,
  fetchSavedProfile,
  login as loginRequest,
  logout as logoutRequest,
  saveSavedProfile,
} from "../lib/api";
import { useProfileStore } from "./profileStore";

export interface AuthUser {
  id: string;
  email: string;
  role: string;
}

export interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  isChecking: boolean;
  sessionChecked: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  restoreSession: () => Promise<void>;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isHydrated: true,
  isChecking: false,
  sessionChecked: false,

  login: async (email: string, password: string) => {
    const result = await loginRequest(email, password);
    const existingProfile = useProfileStore.getState().userProfile;
    try {
      if (existingProfile && typeof existingProfile === "object") {
        await saveSavedProfile(existingProfile as Record<string, unknown>);
      } else {
        const saved = await fetchSavedProfile().catch(() => ({ profile: null, updated_at: null }));
        if (saved.profile) {
          await useProfileStore.getState().setIngestResult(saved.profile);
        }
      }
    } catch {
      // Session is already created. Profile sync stays best-effort.
    }
    set({
      user: result.user,
      isAuthenticated: true,
      isChecking: false,
      sessionChecked: true,
    });
  },

  logout: async () => {
    try {
      await logoutRequest();
    } catch {
      // Best-effort logout.
    }
    set({
      user: null,
      isAuthenticated: false,
      isChecking: false,
      sessionChecked: true,
    });
  },

  restoreSession: async () => {
    set({ isChecking: true });
    try {
      const result = await fetchCurrentUser();
      if (!result.authenticated || !result.user) {
        throw new Error("Session invalid");
      }
      const saved = await fetchSavedProfile().catch(() => ({ profile: null, updated_at: null }));
      if (saved.profile && !useProfileStore.getState().userProfile) {
        await useProfileStore.getState().setIngestResult(saved.profile);
      }
      set({
        user: result.user,
        isAuthenticated: true,
        isChecking: false,
        sessionChecked: true,
      });
    } catch {
      set({
        user: null,
        isAuthenticated: false,
        isChecking: false,
        sessionChecked: true,
      });
    }
  },

  clear: () => {
    set({
      user: null,
      isAuthenticated: false,
      isChecking: false,
      sessionChecked: true,
    });
  },
}));
