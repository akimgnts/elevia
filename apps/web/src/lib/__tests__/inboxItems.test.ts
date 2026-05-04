import { describe, it, expect } from "vitest";
import {
  sortInboxItemsForDisplay,
  normalizeAndSortInboxItems,
  type NormalizedInboxItem,
} from "../inboxItems";

describe("inboxItems sorting", () => {
  it("should sort by score descending as primary key", () => {
    const items: NormalizedInboxItem[] = [
      {
        offer_id: "offer-1",
        title: "O1",
        score: 60,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-2",
        title: "O2",
        score: 85,
        signal_score: 0.7,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-3",
        title: "O3",
        score: 90,
        signal_score: 0.6,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
    ];

    const sorted = sortInboxItemsForDisplay(items);
    const ids = sorted.map((i) => i.offer_id);

    // Should be: 90, 85, 60 by score
    expect(ids).toEqual(["offer-3", "offer-2", "offer-1"]);
  });

  it("should use signal_score as tiebreaker for same score", () => {
    const items: NormalizedInboxItem[] = [
      {
        offer_id: "offer-a",
        title: "A",
        score: 80,
        signal_score: 0.3,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-b",
        title: "B",
        score: 80,
        signal_score: 0.8,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-c",
        title: "C",
        score: 80,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
    ];

    const sorted = sortInboxItemsForDisplay(items);
    const ids = sorted.map((i) => i.offer_id);

    // Same score, ordered by signal_score: 0.8, 0.5, 0.3
    expect(ids).toEqual(["offer-b", "offer-c", "offer-a"]);
  });

  it("should use offer_id lexicographic tiebreaker", () => {
    const items: NormalizedInboxItem[] = [
      {
        offer_id: "z-offer",
        title: "Z",
        score: 80,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "a-offer",
        title: "A",
        score: 80,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "m-offer",
        title: "M",
        score: 80,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
    ];

    const sorted = sortInboxItemsForDisplay(items);
    const ids = sorted.map((i) => i.offer_id);

    // Same score and signal, ordered by offer_id: a, m, z
    expect(ids).toEqual(["a-offer", "m-offer", "z-offer"]);
  });

  it("should be deterministic on multiple sorts", () => {
    const items: NormalizedInboxItem[] = [
      {
        offer_id: "offer-1",
        title: "O1",
        score: 70,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-2",
        title: "O2",
        score: 85,
        signal_score: 0.7,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-3",
        title: "O3",
        score: 85,
        signal_score: 0.3,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
    ];

    const sorted1 = sortInboxItemsForDisplay(items);
    const sorted2 = sortInboxItemsForDisplay(items);

    const ids1 = sorted1.map((i) => i.offer_id);
    const ids2 = sorted2.map((i) => i.offer_id);

    expect(ids1).toEqual(ids2);
    expect(ids1).toEqual(["offer-2", "offer-3", "offer-1"]);
  });

  it("should preserve order when filtering", () => {
    const items: NormalizedInboxItem[] = [
      {
        offer_id: "offer-1",
        title: "O1",
        score: 90,
        signal_score: 0.5,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-2",
        title: "O2",
        score: 85,
        signal_score: 0.7,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
      {
        offer_id: "offer-3",
        title: "O3",
        score: 70,
        signal_score: 0.3,
        explanation: { fit_label: "test", summary_reason: "test" },
      } as NormalizedInboxItem,
    ];

    // Filter preserves order
    const filtered = items.filter((i) => i.offer_id !== "offer-2");
    const ids = filtered.map((i) => i.offer_id);

    expect(ids).toEqual(["offer-1", "offer-3"]);
  });
});
