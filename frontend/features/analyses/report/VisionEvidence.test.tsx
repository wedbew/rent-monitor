import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VisionEvidence } from "./VisionEvidence";

const withEvidence = {
  model: "vision-model",
  prompt_version: "vision-v2",
  photos_total: 3,
  photos_excluded: 0,
  equipment: [
    {
      item: "klimatyzacja",
      media_ordinal: 0,
      provenance: "photo",
      sale_status: "included",
      confidence: "0.85",
    },
    {
      item: "szafa",
      media_ordinal: null,
      provenance: "unattributed",
      sale_status: "unknown",
      confidence: "1",
    },
  ],
  floor_plan_text: "Sypialnia 12 m2",
  notes: "Brak zdjęcia łazienki.",
};

describe("VisionEvidence", () => {
  it("shows equipment with its source, sale status and confidence, labelled as the model's view", () => {
    render(<VisionEvidence vision={withEvidence} degraded={false} />);
    expect(screen.getByRole("heading", { name: "Wyposażenie widoczne na zdjęciach" })).toBeVisible();
    expect(screen.getByText("klimatyzacja")).toBeVisible();
    expect(screen.getByText("źródło: zdjęcie nr 1")).toBeVisible();
    expect(screen.getByText("wg ogłoszenia: w cenie")).toBeVisible();
    expect(screen.getByText("pewność modelu 85%")).toBeVisible();
    expect(screen.getByText("źródło: bez przypisania do zdjęcia")).toBeVisible();
    expect(screen.getByText("Sypialnia 12 m2")).toBeVisible();
    expect(screen.getByText("Brak zdjęcia łazienki.")).toBeVisible();
  });

  it("says a failed analysis differently from one that was never run", () => {
    const { unmount } = render(<VisionEvidence vision={null} degraded />);
    expect(screen.getByText(/Analiza zdjęć nie zakończyła się/)).toBeVisible();
    unmount();
    render(<VisionEvidence vision={null} degraded={false} />);
    expect(screen.getByText("Zdjęć nie oceniono, więc stan mieszkania jest założeniem.")).toBeVisible();
    expect(screen.queryByText(/Analiza zdjęć nie zakończyła się/)).toBeNull();
  });

  it("says an older report has no evidence to show", () => {
    render(<VisionEvidence vision={{ model: "m", prompt_version: "vision-v1" }} degraded={false} />);
    expect(screen.getByText(/Ten raport powstał przed zapisywaniem/)).toBeVisible();
  });

  it("says when the evidence fields are present but empty", () => {
    render(
      <VisionEvidence vision={{ equipment: [], floor_plan_text: null, notes: null }} degraded={false} />,
    );
    expect(screen.getByText("Analiza zdjęć nie wykryła wyposażenia ani tekstu z rzutu.")).toBeVisible();
  });

  it("renders hostile text as plain text, never as markup", () => {
    const hostile = {
      equipment: [
        {
          item: '<img src=x onerror="window.__pwned = 1">',
          media_ordinal: 0,
          provenance: "photo",
          sale_status: "unknown",
          confidence: "0.5",
        },
      ],
      floor_plan_text: "<b>tekst</b>",
      notes: "<script>window.__pwned = 1</script>",
    };
    const { container } = render(<VisionEvidence vision={hostile} degraded={false} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("<b>tekst</b>")).toBeVisible();
  });

  it("does not throw on malformed fields and shows the count it could not read", () => {
    render(
      <VisionEvidence
        vision={{ equipment: [42, { item: "" }, { item: "kominek" }], floor_plan_text: { x: 1 }, notes: 7 }}
        degraded={false}
      />,
    );
    expect(screen.getByText("kominek")).toBeVisible();
    expect(screen.getByText("Nie udało się odczytać pozycji wyposażenia: 2.")).toBeVisible();
  });

  it("says an unreadable vision value is unreadable", () => {
    render(<VisionEvidence vision="zepsute" degraded={false} />);
    expect(screen.getByText(/Nie udało się odczytać zapisu analizy zdjęć/)).toBeVisible();
  });
});
