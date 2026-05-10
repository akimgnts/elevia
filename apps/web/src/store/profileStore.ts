import { create } from "zustand";
import { canonicalStringify } from "../lib/canonicalStringify";

const STORAGE_KEY = "elevia.profile.v1";
const ACTIVE_PROFILE_KEY = "elevia.active_profile_id";

export interface ProfileState {
  aiProfile: unknown | null;
  userProfile: unknown | null;
  profileHash: string | null;
  profileId: string | null;  // NEW: UUID from /parse-file response
  activeProfileId: string | null;  // Profile ID currently being used across pages
  sessionId: string | null;
  isHydrated: boolean;
  setIngestResult: (data: unknown, profileId?: string) => Promise<void>;
  setUserProfile: (data: unknown, profileId?: string) => Promise<void>;
  setProfileId: (id: string) => void;  // NEW: Set profile_id explicitly
  setActiveProfileId: (id: string) => void;
  clearActiveProfileId: () => void;
  clear: () => void;
}

interface StoredProfile {
  aiProfile: unknown;
  userProfile: unknown;
  profileId: string | null;
  sessionId: string;
  profileHash: string;
  ts_saved: number;
}

async function computeHash(data: unknown): Promise<string> {
  const canonicalString = canonicalStringify(data);

  // Try crypto.subtle (browser)
  if (typeof crypto !== "undefined" && crypto.subtle) {
    try {
      const encoder = new TextEncoder();
      const dataBuffer = encoder.encode(canonicalString);
      const hashBuffer = await crypto.subtle.digest("SHA-256", dataBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
    } catch {
      // fallback below
    }
  }

  // Fallback: deterministic but non-crypto hash
  return `${canonicalString.length}:${canonicalString.slice(0, 32)}`;
}

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Save profile to localStorage.
 */
function saveToStorage(state: {
  aiProfile: unknown;
  userProfile: unknown;
  sessionId: string;
  profileHash: string;
  profileId?: string | null;
}): void {
  try {
    const stored: StoredProfile = {
      aiProfile: state.aiProfile,
      userProfile: state.userProfile,
      profileId: state.profileId ?? null,
      sessionId: state.sessionId,
      profileHash: state.profileHash,
      ts_saved: Date.now(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
  } catch {
    // localStorage full or unavailable - ignore
  }
}

/**
 * Load profile from localStorage.
 * Returns null if invalid/missing.
 */
function loadFromStorage(): StoredProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as StoredProfile;

    // Validate required fields
    if (
      !parsed.aiProfile ||
      !parsed.userProfile ||
      !parsed.sessionId ||
      !parsed.profileHash
    ) {
      // Corrupted - clean up
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }

    return parsed;
  } catch {
    // Parse error - clean up
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

/**
 * Clear localStorage.
 */
function clearStorage(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

// Rehydrate initial state from localStorage
function getInitialState(): {
  aiProfile: unknown | null;
  userProfile: unknown | null;
  profileHash: string | null;
  profileId: string | null;
  activeProfileId: string | null;
  sessionId: string | null;
  isHydrated: boolean;
} {
  const stored = loadFromStorage();
  let activeProfileId: string | null = null;
  try {
    activeProfileId = localStorage.getItem(ACTIVE_PROFILE_KEY);
  } catch {
    // ignore
  }

  if (stored) {
    return {
      aiProfile: stored.aiProfile,
      userProfile: stored.userProfile,
      profileHash: stored.profileHash,
      profileId: stored.profileId,
      activeProfileId,
      sessionId: stored.sessionId,
      isHydrated: true,
    };
  }
  return {
    aiProfile: null,
    userProfile: null,
    profileHash: null,
    profileId: null,
    activeProfileId,
    sessionId: null,
    isHydrated: true,
  };
}

export const useProfileStore = create<ProfileState>((set) => ({
  ...getInitialState(),

  setIngestResult: async (data: unknown, profileId?: string) => {
    const hash = await computeHash(data);
    const sessionId = generateSessionId();
    const newState = {
      aiProfile: deepClone(data),
      userProfile: deepClone(data),
      profileHash: hash,
      profileId: profileId ?? null,
      sessionId,
    };

    // Persist to localStorage
    saveToStorage(newState);

    set(newState);
  },

  setUserProfile: async (data: unknown, profileId?: string) => {
    const hash = await computeHash(data);
    set((state) => {
      const newState = {
        userProfile: deepClone(data),
        profileHash: hash,
        profileId: profileId ?? state.profileId,
      };

      // Update localStorage with new userProfile
      if (state.aiProfile && state.sessionId) {
        saveToStorage({
          aiProfile: state.aiProfile,
          userProfile: newState.userProfile,
          sessionId: state.sessionId,
          profileHash: newState.profileHash,
          profileId: newState.profileId,
        });
      }

      return newState;
    });
  },

  setProfileId: (id: string) => {
    set((state) => {
      const newState = { profileId: id };
      if (state.aiProfile && state.sessionId && state.profileHash) {
        saveToStorage({
          aiProfile: state.aiProfile,
          userProfile: state.userProfile,
          sessionId: state.sessionId,
          profileHash: state.profileHash,
          profileId: id,
        });
      }
      return newState;
    });
  },

  setActiveProfileId: (id: string) => {
    try {
      localStorage.setItem(ACTIVE_PROFILE_KEY, id);
    } catch {
      // localStorage full or unavailable - ignore
    }
    set({ activeProfileId: id });
  },

  clearActiveProfileId: () => {
    try {
      localStorage.removeItem(ACTIVE_PROFILE_KEY);
    } catch {
      // ignore
    }
    set({ activeProfileId: null });
  },

  clear: () => {
    clearStorage();
    try {
      localStorage.removeItem(ACTIVE_PROFILE_KEY);
    } catch {
      // ignore
    }
    set({
      aiProfile: null,
      userProfile: null,
      profileHash: null,
      profileId: null,
      activeProfileId: null,
      sessionId: null,
    });
  },
}));
