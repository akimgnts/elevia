import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProfileStore } from "../store/profileStore";
import { buildMatchingProfile } from "../lib/profileMatching";
import { buildCorrectionEvent, postCorrectionMetric } from "../lib/api";

const CAPABILITY_LEVELS = ["beginner", "intermediate", "expert"] as const;
const CAPABILITY_NAMES = [
  "data_visualization",
  "spreadsheet_logic",
  "crm_management",
  "programming_scripting",
  "project_management",
] as const;

type Capability = {
  name: string;
  level: string;
  score: number;
  proofs: string[];
  tools_detected: string[];
};

type ProfileData = {
  candidate_info?: {
    first_name?: string;
    last_name?: string;
    email?: string;
    years_of_experience?: number;
  };
  detected_capabilities?: Capability[];
  languages?: { code: string; level: string; raw_text?: string }[];
  education_summary?: { level: string; raw_text?: string };
  unmapped_skills_high_confidence?: { raw_skill: string; confidence: number; proof: string }[];
};

export default function ProfilePage() {
  const navigate = useNavigate();
  const { aiProfile, userProfile, profileHash, sessionId, setUserProfile, clear } = useProfileStore();

  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [saving, setSaving] = useState(false);

  // Redirect if no profile
  useEffect(() => {
    if (!aiProfile || !userProfile) {
      navigate("/analyze", { replace: true });
    }
  }, [aiProfile, userProfile, navigate]);

  // Initialize capabilities from userProfile
  useEffect(() => {
    if (userProfile) {
      const profile = userProfile as ProfileData;
      setCapabilities(profile.detected_capabilities || []);
    }
  }, [userProfile]);

  if (!aiProfile || !userProfile) {
    return <div style={{ padding: 24 }}>Redirection...</div>;
  }

  const profile = userProfile as ProfileData;
  const aiProfileData = aiProfile as ProfileData;
  const { profile: matchingProfile } = buildMatchingProfile(
    profile,
    profileHash || "anonymous"
  );

  // Compute diff
  const aiCapNames = new Set((aiProfileData.detected_capabilities || []).map((c) => c.name));
  const userCapNames = new Set(capabilities.map((c) => c.name));
  const added = capabilities.filter((c) => !aiCapNames.has(c.name));
  const removed = (aiProfileData.detected_capabilities || []).filter((c) => !userCapNames.has(c.name));
  const modified = capabilities.filter((c) => {
    const aiCap = (aiProfileData.detected_capabilities || []).find((ac) => ac.name === c.name);
    return aiCap && aiCap.level !== c.level;
  });

  const hasChanges = added.length > 0 || removed.length > 0 || modified.length > 0;

  function handleLevelChange(index: number, newLevel: string) {
    const updated = [...capabilities];
    updated[index] = { ...updated[index], level: newLevel };
    setCapabilities(updated);
  }

  function handleRemove(index: number) {
    setCapabilities(capabilities.filter((_, i) => i !== index));
  }

  function handleAdd(name: string) {
    if (capabilities.some((c) => c.name === name)) return;
    setCapabilities([
      ...capabilities,
      {
        name,
        level: "beginner",
        score: 30,
        proofs: ["Ajouté manuellement"],
        tools_detected: [],
      },
    ]);
  }

  async function handleSaveAndMatch() {
    setSaving(true);

    // Update store with modified capabilities
    const updatedProfile = {
      ...profile,
      detected_capabilities: capabilities,
    };
    await setUserProfile(updatedProfile);

    // Post correction metric (VERROU #1 - format normalisé)
    const correctionEvent = buildCorrectionEvent({
      sessionId: sessionId || `session_${Date.now()}`,
      profileHash: profileHash || "unknown",
      added: added.map((c) => c.name),
      deleted: removed.map((c) => c.name),
      modifiedLevel: modified.map((c) => ({
        name: c.name,
        from: (aiProfileData.detected_capabilities || []).find((ac) => ac.name === c.name)?.level || "unknown",
        to: c.level,
      })),
      unmappedCount: profile.unmapped_skills_high_confidence?.length || 0,
      detectedCapabilitiesCount: capabilities.length,
    });

    await postCorrectionMetric(correctionEvent);

    setSaving(false);
    navigate("/dashboard");
  }

  const availableToAdd = CAPABILITY_NAMES.filter((n) => !capabilities.some((c) => c.name === n));

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: "0 auto" }}>
      <h1>Validation du Profil</h1>

      {/* Candidate Info */}
      <div style={{ marginBottom: 24, padding: 16, backgroundColor: "#f9fafb", borderRadius: 8 }}>
        <h3 style={{ margin: 0 }}>
          {profile.candidate_info?.first_name} {profile.candidate_info?.last_name}
        </h3>
        <div style={{ fontSize: 14, opacity: 0.7 }}>
          {profile.candidate_info?.email} | {profile.candidate_info?.years_of_experience || 0} ans d'exp.
        </div>
      </div>

      {/* Capabilities */}
      <h2>Capacités Détectées ({capabilities.length})</h2>
      <div style={{ display: "grid", gap: 12, marginBottom: 24 }}>
        {capabilities.map((cap, idx) => {
          const isAdded = added.some((a) => a.name === cap.name);
          const isModified = modified.some((m) => m.name === cap.name);

          return (
            <div
              key={cap.name}
              style={{
                padding: 12,
                border: isAdded ? "2px solid #22c55e" : isModified ? "2px solid #f59e0b" : "1px solid #e5e7eb",
                borderRadius: 8,
                backgroundColor: isAdded ? "#f0fdf4" : isModified ? "#fffbeb" : "white",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>{cap.name.replace(/_/g, " ")}</strong>
                  {isAdded && <span style={{ marginLeft: 8, color: "#22c55e", fontSize: 12 }}>+Ajouté</span>}
                  {isModified && <span style={{ marginLeft: 8, color: "#f59e0b", fontSize: 12 }}>Modifié</span>}
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <select
                    value={cap.level}
                    onChange={(e) => handleLevelChange(idx, e.target.value)}
                    style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #d1d5db" }}
                  >
                    {CAPABILITY_LEVELS.map((lvl) => (
                      <option key={lvl} value={lvl}>
                        {lvl}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => handleRemove(idx)}
                    style={{ padding: "4px 8px", backgroundColor: "#fee2e2", border: "none", borderRadius: 4, cursor: "pointer" }}
                  >
                    Supprimer
                  </button>
                </div>
              </div>
              <div style={{ fontSize: 13, opacity: 0.7, marginTop: 4 }}>
                Score: {cap.score} | Outils: {cap.tools_detected.join(", ") || "—"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Capability */}
      {availableToAdd.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Ajouter une capacité</h3>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {availableToAdd.map((name) => (
              <button
                key={name}
                onClick={() => handleAdd(name)}
                style={{ padding: "6px 12px", backgroundColor: "#e0f2fe", border: "none", borderRadius: 4, cursor: "pointer" }}
              >
                + {name.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Removed capabilities */}
      {removed.length > 0 && (
        <div style={{ marginBottom: 24, padding: 12, backgroundColor: "#fef2f2", borderRadius: 8 }}>
          <strong>Capacités supprimées:</strong>{" "}
          {removed.map((r) => r.name.replace(/_/g, " ")).join(", ")}
        </div>
      )}

      {/* Unmapped Skills */}
      {profile.unmapped_skills_high_confidence && profile.unmapped_skills_high_confidence.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3>Compétences hors référentiel ({profile.unmapped_skills_high_confidence.length})</h3>
          <div style={{ fontSize: 13, opacity: 0.7, marginBottom: 8 }}>
            Ces compétences sont utilisées dans le matching si elles figurent dans votre profil.
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {profile.unmapped_skills_high_confidence.map((skill) => (
              <span
                key={skill.raw_skill}
                style={{ padding: "4px 8px", backgroundColor: "#f3f4f6", borderRadius: 4, fontSize: 13 }}
              >
                {skill.raw_skill} ({Math.round(skill.confidence * 100)}%)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Matching profile truth */}
      <div style={{ marginBottom: 24, padding: 16, backgroundColor: "#f8fafc", borderRadius: 8 }}>
        <h3 style={{ marginTop: 0 }}>Profil utilisé pour le matching</h3>
        <div style={{ fontSize: 13, opacity: 0.7, marginBottom: 8 }}>
          Ce sont les données réellement utilisées pour calculer vos scores.
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ fontSize: 13 }}>
            <strong>Skills utilisées pour le matching ({matchingProfile.matching_skills.length}):</strong>{" "}
            {matchingProfile.matching_skills.length > 0 ? matchingProfile.matching_skills.join(", ") : "—"}
          </div>
          <div style={{ fontSize: 13 }}>
            <strong>Langues:</strong>{" "}
            {Array.isArray(matchingProfile.languages) && matchingProfile.languages.length > 0
              ? matchingProfile.languages
                  .map((lang) => (typeof lang === "string" ? lang : lang?.code || ""))
                  .filter(Boolean)
                  .join(", ")
              : "—"}
          </div>
          <div style={{ fontSize: 13 }}>
            <strong>Niveau d'études:</strong>{" "}
            {matchingProfile.education || matchingProfile.education_summary?.level || "—"}
          </div>
          <div style={{ fontSize: 13 }}>
            <strong>Pays préférés:</strong>{" "}
            {matchingProfile.preferred_countries && matchingProfile.preferred_countries.length > 0
              ? matchingProfile.preferred_countries.join(", ")
              : "—"}
          </div>
        </div>
        <div style={{ fontSize: 12, opacity: 0.6, marginTop: 8 }}>
          Les capacités détectées restent un signal secondaire d'UX, pas la base du matching.
        </div>
      </div>

      {/* Diff Summary */}
      {hasChanges && (
        <div style={{ marginBottom: 24, padding: 12, backgroundColor: "#eff6ff", borderRadius: 8 }}>
          <strong>Modifications:</strong> {added.length} ajout(s), {removed.length} suppression(s), {modified.length} changement(s) de niveau
        </div>
      )}

      {/* Save Button */}
      <button
        onClick={handleSaveAndMatch}
        disabled={saving}
        style={{
          padding: "12px 24px",
          backgroundColor: "#2563eb",
          color: "white",
          border: "none",
          borderRadius: 8,
          fontSize: 16,
          fontWeight: 600,
          cursor: saving ? "wait" : "pointer",
          opacity: saving ? 0.7 : 1,
        }}
      >
        {saving ? "Enregistrement..." : "Valider & Voir mes Matchs"}
      </button>

      {/* Debug: Profile Hash + Reset */}
      <div style={{ marginTop: 24, display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 12, opacity: 0.5 }}>
          Profile Hash: {profileHash?.slice(0, 16)}...
        </span>
        <button
          onClick={() => {
            clear();
            navigate("/analyze", { replace: true });
          }}
          style={{
            padding: "4px 8px",
            backgroundColor: "#f3f4f6",
            border: "1px solid #d1d5db",
            borderRadius: 4,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          Reset profil
        </button>
      </div>
    </div>
  );
}
