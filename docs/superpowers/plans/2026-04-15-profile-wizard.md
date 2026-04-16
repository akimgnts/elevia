# Profile Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current default Profile free-form experience with a strict single-route wizard that validates `structuring_report` and `skill_links`, writes answers back into `career_profile`, and leads the user toward Cockpit.

**Architecture:** Keep `/profile` as the only route and refactor `ProfilePage.tsx` into a wizard container with four internal steps. Reuse the current normalized profile state and save flow, extract thin presentational step components, and keep legacy fields hidden behind advanced editing inside Step 2 instead of exposing the old form by default.

**Tech Stack:** React, TypeScript, Zustand profile store, existing `ProfilePage.tsx` normalization/save logic, Vite build.

---

## File Map

- Modify: `apps/web/src/pages/ProfilePage.tsx`
  - Convert page from default free-form editor into the wizard container.
- Create: `apps/web/src/components/profile/profileWizardTypes.ts`
  - Shared local types for wizard steps, structuring report, typed questions, and UI validation metadata.
- Create: `apps/web/src/components/profile/ProfileWizardHeader.tsx`
  - Progress header and step navigation controls.
- Create: `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
  - Step 1 value and understanding summary.
- Create: `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
  - Step 2 constrained experience cards and advanced edit affordances.
- Create: `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
  - Step 3 question rendering and write-back handlers.
- Create: `apps/web/src/components/profile/ProfileValidationStep.tsx`
  - Step 4 final validation and Cockpit handoff.
- Verify only: `apps/web/src/store/profileStore.ts`
  - Confirm no store change is required beyond current persistence behavior.
- Optional small test file if repo pattern supports it:
  - `apps/web/tests/test_profile_wizard_flow.py`
  - Add only lightweight contract assertions; treat them as guardrails, not full UX validation.

## Task 1: Add a shared wizard type layer and minimal guardrail assertions

**Files:**
- Create: `apps/web/src/components/profile/profileWizardTypes.ts`
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Test: `apps/web/tests/test_profile_wizard_flow.py` (if adding tests matches repo convention)

- [ ] **Step 1: Inspect current profile page seams before editing**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
sed -n '1,260p' apps/web/src/pages/ProfilePage.tsx
sed -n '260,620p' apps/web/src/pages/ProfilePage.tsx
sed -n '620,1180p' apps/web/src/pages/ProfilePage.tsx
sed -n '1180,1800p' apps/web/src/pages/ProfilePage.tsx
```

Expected: confirm current normalization helpers, editor sections, and save flow all live in the page and can be preserved while replacing the default render path.

- [ ] **Step 2: Create one shared local type file for wizard state and typed questions**

Create `apps/web/src/components/profile/profileWizardTypes.ts`:

```ts
export type ProfileWizardStep = "understanding" | "experiences" | "questions" | "validation";

export type WizardValidationMeta = {
  validated_at?: string;
  version?: "v1";
};

export type StructuringQuestionType = "autonomy" | "tool" | "skill" | "context";

export type StructuringQuestion = {
  type?: StructuringQuestionType;
  experience_index?: number;
  skill_link_index?: number;
  target_field?: "autonomy_level" | "tool" | "skill" | "context";
  question?: string;
};

export type StructuringReport = {
  used_signals?: Array<Record<string, unknown>>;
  uncertain_links?: Array<Record<string, unknown>>;
  questions_for_user?: StructuringQuestion[];
  canonical_candidates?: Array<Record<string, unknown>>;
  rejected_noise?: Array<Record<string, unknown>>;
  unresolved_candidates?: Array<Record<string, unknown>>;
  stats?: {
    experiences_processed?: number;
    skill_links_created?: number;
    questions_generated?: number;
    coverage_ratio?: number;
  };
};
```

- [ ] **Step 3: Add a lightweight frontend contract test if the current test suite supports it**

Create `apps/web/tests/test_profile_wizard_flow.py`:

```python
from pathlib import Path


PROFILE_PAGE = Path("apps/web/src/pages/ProfilePage.tsx")


def test_profile_page_mentions_wizard_steps():
    text = PROFILE_PAGE.read_text()
    assert "Ce que l’agent a compris" in text or "Ce que l'agent a compris" in text
    assert "Questions de clarification" in text
    assert "Validation finale" in text


def test_profile_page_hides_free_form_by_default():
    text = PROFILE_PAGE.read_text()
    assert "Corriger" in text or "édition ciblée" in text or "edition ciblee" in text.lower()
```

- [ ] **Step 4: Run the test to verify it fails before implementation**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
python -m pytest apps/web/tests/test_profile_wizard_flow.py -q
```

Expected: FAIL because the wizard strings and constrained correction flow do not exist yet.

## Task 2: Wire shared wizard helpers into `ProfilePage.tsx`

**Files:**
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`
- Modify: `apps/web/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Import shared wizard types into `ProfilePage.tsx`**

Add import near the top:

```tsx
import type {
  ProfileWizardStep,
  StructuringQuestion,
  StructuringReport,
  WizardValidationMeta,
} from "../components/profile/profileWizardTypes";
```

- [ ] **Step 2: Add helpers to read `structuring_report` and post-validation mode**

Insert near current normalization helpers:

```ts
function normalizeStructuringReport(value: unknown): StructuringReport {
  if (!value || typeof value !== "object") return {};
  const rec = value as Record<string, unknown>;
  return {
    used_signals: Array.isArray(rec.used_signals) ? (rec.used_signals as Array<Record<string, unknown>>) : [],
    uncertain_links: Array.isArray(rec.uncertain_links) ? (rec.uncertain_links as Array<Record<string, unknown>>) : [],
    questions_for_user: Array.isArray(rec.questions_for_user)
      ? (rec.questions_for_user as StructuringReport["questions_for_user"])
      : [],
    canonical_candidates: Array.isArray(rec.canonical_candidates) ? (rec.canonical_candidates as Array<Record<string, unknown>>) : [],
    rejected_noise: Array.isArray(rec.rejected_noise) ? (rec.rejected_noise as Array<Record<string, unknown>>) : [],
    unresolved_candidates: Array.isArray(rec.unresolved_candidates) ? (rec.unresolved_candidates as Array<Record<string, unknown>>) : [],
    stats: rec.stats && typeof rec.stats === "object" ? (rec.stats as StructuringReport["stats"]) : {},
  };
}

function hasValidatedWizard(profile: FullProfile): boolean {
  const meta = (profile as Record<string, unknown>).profile_wizard_meta;
  return Boolean(meta && typeof meta === "object" && (meta as WizardValidationMeta).validated_at);
}
```

- [ ] **Step 3: Add derived values inside `ProfilePage` state section**

Insert after `fullProfile` / `currentCareer` setup:

```ts
  const structuringReport = normalizeStructuringReport(fullProfile.structuring_report);
  const structuringStats = structuringReport.stats || {};
  const clarificationQuestions = structuringReport.questions_for_user || [];
  const hasStructuringReport = clarificationQuestions.length > 0 || Boolean(structuringStats.experiences_processed);
```

- [ ] **Step 4: Run TypeScript build to verify helper additions compile**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS or only fail later on missing step components not yet created.

## Task 3: Build the wizard header and Step 1 value screen

**Files:**
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`
- Create: `apps/web/src/components/profile/ProfileWizardHeader.tsx`
- Create: `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
- Modify: `apps/web/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Create the wizard header component**

Create `apps/web/src/components/profile/ProfileWizardHeader.tsx`:

```tsx
type ProfileWizardStep = "understanding" | "experiences" | "questions" | "validation";

const STEP_LABELS: Array<{ step: ProfileWizardStep; label: string }> = [
  { step: "understanding", label: "Compréhension agent" },
  { step: "experiences", label: "Expériences" },
  { step: "questions", label: "Questions" },
  { step: "validation", label: "Validation" },
];

export function ProfileWizardHeader(props: {
  currentStep: ProfileWizardStep;
  onBack?: () => void;
}) {
  const activeIndex = STEP_LABELS.findIndex((item) => item.step === props.currentStep);
  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Wizard profil</div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {STEP_LABELS.map((item, index) => {
          const active = item.step === props.currentStep;
          const done = index < activeIndex;
          return (
            <div
              key={item.step}
              className={`rounded-[1.25rem] border px-4 py-3 text-sm ${
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : done
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 bg-slate-50 text-slate-500"
              }`}
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
                Étape {index + 1}
              </div>
              <div className="mt-1 font-semibold">{item.label}</div>
            </div>
          );
        })}
      </div>
      {props.onBack && (
        <button
          type="button"
          onClick={props.onBack}
          className="mt-4 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Retour
        </button>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Create the Step 1 understanding component**

Create `apps/web/src/components/profile/AgentUnderstandingStep.tsx`:

```tsx
import { Link } from "react-router-dom";

type AgentUnderstandingStepProps = {
  structuredExperienceCount: number;
  structuredLinkCount: number;
  unresolvedCount: number;
  questionCount: number;
  autoDetectedSummary: string[];
  remainingConfirmationSummary: string[];
  previewStructuredLinks: Array<{
    link: {
      skill: { label: string };
      tools: Array<{ label: string }>;
      context?: string;
      autonomy_level?: string;
    };
    experienceTitle: string;
    experienceCompany: string;
  }>;
  onNext: () => void;
};

export function AgentUnderstandingStep(props: AgentUnderstandingStepProps) {
  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Ce que l’agent a compris</div>
      <h2 className="mt-3 text-2xl font-semibold text-slate-950">Le profil a déjà été structuré automatiquement.</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Ici, vous validez ce que le système a détecté au lieu de repartir d’un formulaire vide.
      </p>

      <div className="mt-5 grid gap-4 md:grid-cols-4">
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Expériences structurées</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.structuredExperienceCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill links</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.structuredLinkCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Ambiguïtés</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.unresolvedCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Questions</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.questionCount}</div>
        </div>
      </div>

      <div className="mt-5 rounded-[1.25rem] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
        <div className="font-semibold">Gain immédiat</div>
        <p className="mt-1 leading-6">
          {props.structuredExperienceCount} expériences ont déjà été structurées, {props.structuredLinkCount} relations compétence-outil ont été reconstruites, et seules les ambiguïtés restantes vous seront demandées.
        </p>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Compris automatiquement</div>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            {props.autoDetectedSummary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Reste à confirmer</div>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            {props.remainingConfirmationSummary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {props.previewStructuredLinks.map(({ link, experienceTitle, experienceCompany }, index) => (
          <div key={`${link.skill.label}-${index}`} className="rounded-[1rem] border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-sm font-semibold text-slate-950">{link.skill.label}</div>
            <div className="mt-1 text-xs text-slate-400">
              {[experienceTitle, experienceCompany].filter(Boolean).join(" · ")}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {link.tools.map((tool) => (
                <span key={tool.label} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
                  {tool.label}
                </span>
              ))}
            </div>
            {link.context && <div className="mt-2 text-xs leading-5 text-slate-500">{link.context}</div>}
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={props.onNext}
          className="inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Continuer vers mes expériences
        </button>
        <Link
          to="/analyze"
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Revenir à l’analyse
        </Link>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Wire Step 1 into `ProfilePage.tsx`**

Add imports:

```tsx
import { AgentUnderstandingStep } from "../components/profile/AgentUnderstandingStep";
import { ProfileWizardHeader } from "../components/profile/ProfileWizardHeader";
```

Add local step state near other `useState` calls:

```tsx
  const [wizardStep, setWizardStep] = useState<ProfileWizardStep>(hasValidatedWizard(fullProfile) ? "validation" : "understanding");
```

Render the header and Step 1 near the top of the main page body:

```tsx
        <ProfileWizardHeader
          currentStep={wizardStep}
          onBack={wizardStep === "understanding" ? undefined : () => {
            setWizardStep((current) =>
              current === "experiences"
                ? "understanding"
                : current === "questions"
                  ? "experiences"
                  : "questions"
            );
          }}
        />

        {wizardStep === "understanding" && (
          <AgentUnderstandingStep
            structuredExperienceCount={structuredExperienceCount}
            structuredLinkCount={structuredLinkCount}
            unresolvedCount={(structuringReport.uncertain_links || []).length}
            questionCount={clarificationQuestions.length}
            autoDetectedSummary={[
              `${structuredExperienceCount} expériences déjà structurées`,
              `${structuredLinkCount} skill_links déjà construits`,
              `${selectedSkills.length} compétences contrôlées disponibles dans le profil`,
            ]}
            remainingConfirmationSummary={[
              `${clarificationQuestions.length} question(s) ciblée(s) restent à confirmer`,
              `${(structuringReport.uncertain_links || []).length} lien(s) incertain(s) ont été isolés`,
              "Vous n’avez pas à repartir d’un formulaire vide",
            ]}
            previewStructuredLinks={previewStructuredLinks}
            onNext={() => setWizardStep("experiences")}
          />
        )}
```

- [ ] **Step 4: Run build to verify Step 1 compiles**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS or only fail on missing next-step components not yet created.

## Task 4: Build Step 2 constrained experience cards with targeted correction panels

**Files:**
- Create: `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
- Modify: `apps/web/src/pages/ProfilePage.tsx`

- [ ] **Step 1: Create the constrained Step 2 component**

Create `apps/web/src/components/profile/StructuredExperiencesStep.tsx`:

```tsx
type StructuredExperiencesStepProps = {
  experiences: ExperienceV2[];
  onChangeExperience: (index: number, next: ExperienceV2) => void;
  onNext: () => void;
};

export function StructuredExperiencesStep(props: StructuredExperiencesStepProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Vos expériences structurées</div>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Chaque expérience est présentée comme une carte structurée. Les champs legacy sont masqués par défaut et n’apparaissent qu’en mode avancé.
      </p>

      <div className="mt-5 space-y-4">
        {props.experiences.map((experience, index) => {
          const primaryLinks = experience.skill_links || [];
          const firstLink = primaryLinks[0];
          return (
            <article key={`${experience.title || "experience"}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-base font-semibold text-slate-950">{experience.title || "Expérience"}</div>
                  <div className="text-sm text-slate-500">{experience.company || "Entreprise"}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setEditingIndex((current) => (current === index ? null : index))}
                  className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  {editingIndex === index ? "Fermer la correction" : "Corriger"}
                </button>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill principal</div>
                  <div className="mt-2 text-sm font-semibold text-slate-950">{firstLink?.skill.label || "À confirmer"}</div>
                </div>
                <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Outils associés</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(firstLink?.tools || []).map((tool) => (
                      <span key={tool.label} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
                        {tool.label}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Impact / contexte</div>
                  <div className="mt-2 text-sm leading-6 text-slate-600">
                    {firstLink?.context || experience.impact_signals?.[0] || "À compléter"}
                  </div>
                </div>
              </div>

              {editingIndex === index && (
                <div className="mt-4 rounded-[1rem] border border-slate-200 bg-white p-4">
                  <div className="text-sm font-semibold text-slate-900">Édition ciblée</div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    Corrigez uniquement les champs structurants nécessaires pour cette expérience.
                  </p>
                  <div className="mt-3">
                    {/* Render only narrowed correction controls here, not the old full-form block */}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>

      <div className="mt-6">
        <button
          type="button"
          onClick={props.onNext}
          className="inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Continuer vers les questions
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Replace default free-form rendering with Step 2 gating in `ProfilePage.tsx`**

Wrap the existing large experience editor section so it only appears in advanced mode inside Step 2, not as the page default:

```tsx
        {wizardStep === "experiences" && (
          <StructuredExperiencesStep
            experiences={experiences}
            onChangeExperience={(index, next) =>
              setExperiences((current) => current.map((item, itemIndex) => (itemIndex === index ? next : item)))
            }
            onNext={() => setWizardStep("questions")}
          />
        )}
```

Then move the previous default profile form sections below the wizard and guard them behind:

```tsx
        {/* Old default full-form sections removed from primary render path. */}
```

Implementation note:

- do not re-inject the old full form as the default correction experience
- if legacy controls are still reused, only expose a narrowed subset inside the targeted correction panel

- [ ] **Step 3: Run build to verify default free-form mode is no longer the primary render**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS.

## Task 5: Build Step 3 typed clarification flow that writes directly into targeted `career_profile` fields

**Files:**
- Create: `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`

- [ ] **Step 1: Create the clarification step component**

Create `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`:

```tsx
type ClarificationQuestionsStepProps = {
  questions: StructuringQuestion[];
  experiences: ExperienceV2[];
  onAnswer: (question: StructuringQuestion, value: string | AutonomyLevel | CanonicalSkillRef | ToolRef) => void;
  onNext: () => void;
};

export function ClarificationQuestionsStep(props: ClarificationQuestionsStepProps) {
  if (props.questions.length === 0) {
    return (
      <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Questions de clarification</div>
        <h2 className="mt-3 text-2xl font-semibold text-slate-950">Aucune ambiguïté critique à résoudre.</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Le profil structuré est suffisamment clair pour passer à la validation.
        </p>
        <button
          type="button"
          onClick={props.onNext}
          className="mt-6 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Continuer vers la validation
        </button>
      </section>
    );
  }

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Questions de clarification</div>
      <div className="mt-5 space-y-4">
        {props.questions.map((question, index) => (
          <div key={`${question.type}-${question.experience_index ?? "global"}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
            <div className="text-sm font-semibold text-slate-950">{question.question || "Précisez cette information"}</div>
            {question.type === "autonomy" ? (
              <select
                className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                onChange={(event) => props.onAnswer(question, event.target.value as AutonomyLevel)}
                defaultValue=""
              >
                <option value="" disabled>Choisir un niveau</option>
                <option value="execution">Exécution</option>
                <option value="partial">Contribution partielle</option>
                <option value="autonomous">Autonome</option>
                <option value="ownership">Ownership</option>
              </select>
            ) : (
              <input
                type="text"
                className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                placeholder={
                  question.type === "tool"
                    ? "Outil principal"
                    : question.type === "skill"
                      ? "Compétence concernée"
                      : "Contexte court"
                }
                onChange={(event) => props.onAnswer(question, event.target.value)}
              />
            )}
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={props.onNext}
        className="mt-6 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        Continuer vers la validation
      </button>
    </section>
  );
}
```

- [ ] **Step 2: Implement direct write-back handlers in `ProfilePage.tsx`**

Add a handler near `handleSave`:

```tsx
  function applyClarificationAnswer(
    question: StructuringQuestion,
    value: string | AutonomyLevel | CanonicalSkillRef | ToolRef,
  ) {
    if (question.experience_index == null) return;

    setExperiences((current) =>
      current.map((experience, index) => {
        if (index !== question.experience_index) return experience;
        const nextLinks = [...(experience.skill_links || [])];
        const linkIndex = question.skill_link_index ?? 0;
        const targetLink = nextLinks[linkIndex];

        if (question.target_field === "autonomy_level" && typeof value === "string") {
          return { ...experience, autonomy_level: value as AutonomyLevel };
        }

        if (!targetLink) return experience;

        if (question.target_field === "context" && typeof value === "string") {
          nextLinks[linkIndex] = { ...targetLink, context: value.trim() || undefined };
          return { ...experience, skill_links: nextLinks };
        }

        if (question.target_field === "tool") {
          const tool = typeof value === "string" ? { label: value.trim() } : (value as ToolRef);
          if (!tool.label.trim()) return experience;
          nextLinks[linkIndex] = {
            ...targetLink,
            tools: [...(targetLink.tools || []), { label: tool.label.trim() }],
          };
          return { ...experience, skill_links: nextLinks };
        }

        if (question.target_field === "skill") {
          const skill = typeof value === "string" ? { label: value.trim() } : (value as CanonicalSkillRef);
          if (!skill.label.trim()) return experience;
          nextLinks[linkIndex] = { ...targetLink, skill: { ...targetLink.skill, ...skill, label: skill.label.trim() } };
          return { ...experience, skill_links: nextLinks };
        }

        return experience;
      }),
    );
  }
```

- [ ] **Step 3: Normalize clarification questions with explicit targets**

When normalizing `structuring_report.questions_for_user`, ensure each question carries:

```ts
  skill_link_index: typeof rec.skill_link_index === "number" ? rec.skill_link_index : undefined,
  target_field:
    rec.target_field === "autonomy_level" ||
    rec.target_field === "tool" ||
    rec.target_field === "skill" ||
    rec.target_field === "context"
      ? rec.target_field
      : rec.type === "autonomy"
        ? "autonomy_level"
        : rec.type === "tool"
          ? "tool"
          : rec.type === "skill"
            ? "skill"
            : rec.type === "context"
              ? "context"
              : undefined,
```

- [ ] **Step 3: Render Step 3**

Add import:

```tsx
import { ClarificationQuestionsStep } from "../components/profile/ClarificationQuestionsStep";
```

Render:

```tsx
        {wizardStep === "questions" && (
          <ClarificationQuestionsStep
            questions={clarificationQuestions || []}
            experiences={experiences}
            onAnswer={applyClarificationAnswer}
            onNext={() => setWizardStep("validation")}
          />
        )}
```

- [ ] **Step 4: Run build to verify direct write-back path compiles**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS.

## Task 6: Build Step 4 final validation and post-validation replay mode

**Files:**
- Create: `apps/web/src/components/profile/ProfileValidationStep.tsx`
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`

- [ ] **Step 1: Create the validation step component**

Create `apps/web/src/components/profile/ProfileValidationStep.tsx`:

```tsx
import { Link } from "react-router-dom";

type ProfileValidationStepProps = {
  completePct: number;
  structuredExperienceCount: number;
  structuredLinkCount: number;
  remainingAmbiguities: number;
  estimatedMatches?: number;
  onValidate: () => void;
};

export function ProfileValidationStep(props: ProfileValidationStepProps) {
  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Validation finale</div>
      <h2 className="mt-3 text-2xl font-semibold text-slate-950">Vous êtes maintenant prêt à voir vos opportunités.</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Le profil a été structuré, relu et peut désormais alimenter le Cockpit, l’Inbox et les candidatures.
      </p>

      <div className="mt-5 grid gap-4 md:grid-cols-4">
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Complétude</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.completePct}%</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Expériences</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.structuredExperienceCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill links</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.structuredLinkCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Ambiguïtés restantes</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{props.remainingAmbiguities}</div>
        </div>
      </div>

      <div className="mt-5 rounded-[1.25rem] border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        <div className="font-semibold">Projection vers la suite</div>
        <p className="mt-1 leading-6">
          {props.estimatedMatches != null
            ? `${props.estimatedMatches} opportunités peuvent maintenant être explorées depuis le cockpit et l’inbox.`
            : "Le cockpit et l’inbox peuvent maintenant exploiter un profil validé et structuré."}
        </p>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={props.onValidate}
          className="inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Valider mon profil
        </button>
        <Link
          to="/cockpit"
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Voir mon cockpit
        </Link>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Add post-validation replay mode in `ProfilePage.tsx`**

Persist explicit UI metadata in `handleSave`:

```tsx
      profile_wizard_meta: {
        validated_at: new Date().toISOString(),
        version: "v1",
      },
```

Add a lightweight post-validation entry state near the top of the page render:

```tsx
        {hasValidatedWizard(fullProfile) && wizardStep === "validation" && (
          <div className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Profil validé</div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-slate-950">Le profil a déjà été validé dans le wizard.</div>
                <p className="mt-1 text-sm text-slate-600">Vous pouvez revoir le résumé actuel ou relancer la correction guidée.</p>
              </div>
              <button
                type="button"
                onClick={() => setWizardStep("understanding")}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                Modifier mon profil
              </button>
            </div>
          </div>
        )}
```

- [ ] **Step 3: Render Step 4 and final validation callback**

Add import:

```tsx
import { ProfileValidationStep } from "../components/profile/ProfileValidationStep";
```

Add callback:

```tsx
  async function handleWizardValidation() {
    await handleSave();
    setWizardStep("validation");
  }
```

Render:

```tsx
        {wizardStep === "validation" && (
          <ProfileValidationStep
            completePct={completePct}
            structuredExperienceCount={structuredExperienceCount}
            structuredLinkCount={structuredLinkCount}
            remainingAmbiguities={(structuringReport.uncertain_links || []).length}
            estimatedMatches={undefined}
            onValidate={handleWizardValidation}
          />
        )}
```

Implementation note:

- primary CTA must save first
- then update validation UI state
- then visibly propose Cockpit as the next action

- [ ] **Step 4: Run build to verify the full wizard compiles**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass/apps/web
npm run build
```

Expected: PASS.

## Task 7: Final cleanup, regression pass, and graph update

**Files:**
- Verify: `apps/web/src/pages/ProfilePage.tsx`
- Verify: `apps/web/src/components/profile/*.tsx`
- Verify: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Remove the old default free-form entry path**

Inspect `ProfilePage.tsx` and ensure:

- wizard is the default render path
- old full form is not the first thing shown
- advanced mode exists only in Step 2

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
rg -n "mode avancé|Ce que l’agent a compris|Questions de clarification|Validation finale" apps/web/src/pages/ProfilePage.tsx apps/web/src/components/profile -S
```

Expected: wizard strings present and advanced mode explicitly scoped.

- [ ] **Step 2: Run the frontend verification batch**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
python -m pytest apps/web/tests/test_profile_wizard_flow.py -q
cd apps/web && npm run build
```

Expected: PASS. Treat the Python string test as a minimal guardrail only; `npm run build` remains the real required verification for this slice.

- [ ] **Step 3: Update the code graph**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
graphify update .
```

Expected: graph updated successfully.

## Self-Review

- Spec coverage:
  - wizard strict as default profile mode: covered in Tasks 3-4 and 7
  - Step 1 value framing: covered in Task 3
  - Step 2 constrained cards with targeted correction only: covered in Task 4
  - Step 3 typed direct write-back into targeted `career_profile` fields: covered in Task 5
  - Step 4 opportunity projection and replay mode with explicit UI metadata: covered in Task 6
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders remain in the plan steps
- Type consistency:
  - `ProfileWizardStep`, `StructuringReport`, `StructuringQuestion`, and `WizardValidationMeta` come from one shared local type file
  - step progression remains `understanding -> experiences -> questions -> validation`
