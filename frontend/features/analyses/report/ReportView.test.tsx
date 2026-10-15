import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { type DealAnalysis, parseReport } from "../../../api/report";
import { SUCCEEDED_AUDITS } from "../../../test/scenarios";
import { ReportView } from "./ReportView";

function baseReport(): DealAnalysis {
  const parsed = parseReport(SUCCEEDED_AUDITS[0]?.result);
  if (parsed.kind !== "ready") throw new Error("the captured report must be readable");
  return parsed.report;
}

function withListing(patch: Partial<DealAnalysis["listing"]>): DealAnalysis {
  const report = baseReport();
  return { ...report, listing: { ...report.listing, ...patch } };
}

const open = (name: string | RegExp) => userEvent.click(screen.getByRole("button", { name }));
const visibleText = () => document.body.textContent ?? "";

describe("return measures in plain Polish", () => {
  it("never show IRR, CAGR or MOIC in a visible label or hint", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Zwroty, wyjście i wrażliwość na wzrost cen");
    expect(screen.getByText("Roczna stopa zwrotu")).toBeVisible();
    expect(screen.getByText("Średni roczny wzrost kapitału")).toBeVisible();
    expect(screen.getByText("Mnożnik zainwestowanego kapitału")).toBeVisible();
    expect(visibleText()).not.toMatch(/\b(IRR|CAGR|MOIC)\b/);
  });

  it("each has a help button that opens an explanation naming the acronym and its full name", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Zwroty, wyjście i wrażliwość na wzrost cen");
    const cases = [
      ["Roczna stopa zwrotu", /IRR, czyli wewnętrzna stopa zwrotu/],
      ["Średni roczny wzrost kapitału", /CAGR, czyli złożona roczna stopa wzrostu/],
      ["Mnożnik zainwestowanego kapitału", /MOIC, czyli mnożnik zainwestowanego kapitału/],
    ] as const;
    for (const [label, title] of cases) {
      await userEvent.click(screen.getByRole("button", { name: `Co oznacza: ${label}` }));
      const popup = await screen.findByRole("dialog");
      expect(within(popup).getByText(title)).toBeVisible();
      for (const heading of ["Co to jest", "Jak czytać wynik", "Jak to liczymy"]) {
        expect(within(popup).getByText(heading)).toBeVisible();
      }
      await userEvent.keyboard("{Escape}");
      await screen.findByRole("button", { name: `Co oznacza: ${label}`, expanded: false });
    }
  });

  it("states what the engine computes: CAGR is MOIC annualised, not a total annual return; IRR is unlevered and after tax", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Zwroty, wyjście i wrażliwość na wzrost cen");
    await userEvent.click(screen.getByRole("button", { name: "Co oznacza: Średni roczny wzrost kapitału" }));
    const cagr = await screen.findByRole("dialog");
    expect(cagr).toHaveTextContent(/wpłynęło dopiero na końcu/);
    expect(cagr).toHaveTextContent(/pierwiastek z mnożnika/);
    expect(cagr).toHaveTextContent(/nie uwzględnia, kiedy pieniądze naprawdę wpływają/i);
    expect(cagr).not.toHaveTextContent(/łączny roczny zwrot|całkowity zwrot z inwestycji/i);
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Co oznacza: Roczna stopa zwrotu" }));
    const irr = await screen.findByRole("dialog");
    expect(irr).toHaveTextContent(/Bez kredytu, po podatku od najmu/);
    expect(irr).toHaveTextContent(/sprzedaży mieszkania po kosztach i podatku/);
  });

  it("the horizon in the explanation is the engine's own number of years", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Zwroty, wyjście i wrażliwość na wzrost cen");
    await userEvent.click(
      screen.getByRole("button", { name: "Co oznacza: Mnożnik zainwestowanego kapitału" }),
    );
    expect(await screen.findByRole("dialog")).toHaveTextContent(/Horyzont 10\s+lat/);
  });

  it("the return at the asking price says 'roczna stopa zwrotu' and explains itself too", () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    expect(screen.getByText(/roczna stopa zwrotu w 10\s+lat, próg/)).toBeVisible();
    expect(visibleText()).not.toMatch(/\bIRR\b/);
    expect(screen.getByRole("button", { name: "Co oznacza: Zwrot przy cenie ofertowej" })).toBeVisible();
  });
});

describe("the preliminary renovation estimate", () => {
  it("puts the badge on the label, so the amount stays alone in the value column", () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    const label = screen.getByText("Remont (szacunek)").closest("dt");
    expect(label).toHaveTextContent("wstępny");
    const value = label?.nextElementSibling;
    expect(value?.tagName).toBe("DD");
    expect(value).not.toHaveTextContent("wstępny");
    expect(value?.textContent).toMatch(/^[\d\s,.\u00a0\u202f]+zł$/);
  });
});

describe("renovation assumptions", () => {
  it("do not show the price-list version or the vague city category, and keep the multiplier", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Remont: szacunek i założenia");
    expect(visibleText()).not.toMatch(/Wersja cennika|placeholder-2026/);
    expect(visibleText()).not.toMatch(/Rodzaj miasta|pozostałe miasta/);
    expect(screen.getByText("Współczynnik cen w mieście")).toBeVisible();
  });
});

describe("technical metadata", () => {
  it("is not shown: no model, prompt version, engine or assumptions version", async () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    await open("Ocena zdjęć");
    expect(screen.getByText("Korekta czynszu")).toBeVisible();
    expect(visibleText()).not.toMatch(/Model i wersja instrukcji|vendor\/smoke-model|vision-v1/);
    expect(visibleText()).not.toMatch(/silnik 0\.1\.0|założenia 2026|Wersje:/);
    expect(screen.getByText("Zdjęcia z ogłoszenia nie są tu wyświetlane.")).toBeVisible();
  });

  it("the disclosure group owns the last divider: the footer draws none of its own", () => {
    render(<ReportView report={baseReport()} degraded={false} />);
    const footer = screen.getByText("Zdjęcia z ogłoszenia nie są tu wyświetlane.").parentElement;
    expect(footer?.className).toMatch(/footer/);
  });
});

describe("Otodom attributes", () => {
  it("are shown in Polish, never as provider codes", async () => {
    render(
      <ReportView
        report={withListing({
          floor: "floor_1",
          building_floors: 4,
          heating: "gas",
          windows: "plastic",
          building_type: "tenement",
        })}
        degraded={false}
      />,
    );
    expect(screen.getByText(/1\. piętro z 4/)).toBeVisible();
    await open("Dane z ogłoszenia");
    const rows = screen.getByText("Ogrzewanie").closest("dl");
    expect(rows).toHaveTextContent("Gazowe");
    expect(rows).toHaveTextContent("PCV");
    expect(rows).toHaveTextContent("Kamienica");
    expect(rows).toHaveTextContent("1. piętro");
    expect(visibleText()).not.toMatch(/floor_1|\bgas\b|\bplastic\b|tenement|piętro floor|piętro 1\. piętro/);
  });

  it("handle the ground floor, a missing value and an unknown value without leaking a code", async () => {
    render(
      <ReportView
        report={withListing({
          floor: "ground_floor",
          building_floors: 3,
          heating: null,
          windows: "triple_glazed_new",
          building_type: "",
        })}
        degraded={false}
      />,
    );
    expect(screen.getByText(/parter/)).toBeVisible();
    expect(visibleText()).not.toMatch(/parter z 3/);
    await open("Dane z ogłoszenia");
    const rows = screen.getByText("Ogrzewanie").closest("dl");
    expect(rows).toHaveTextContent("Parter");
    expect(rows?.textContent).toMatch(/Ogrzewanie\s*brak w ogłoszeniu/);
    expect(rows?.textContent).toMatch(/Okna\s*nierozpoznana wartość/);
    expect(rows?.textContent).toMatch(/Rodzaj budynku\s*brak w ogłoszeniu/);
    expect(visibleText()).not.toMatch(/ground_floor|triple_glazed_new/);
  });

  it("keep the provider's value intact in the report data", () => {
    const report = withListing({ heating: "gas", floor: "floor_1" });
    render(<ReportView report={report} degraded={false} />);
    expect(report.listing.heating).toBe("gas");
    expect(report.listing.floor).toBe("floor_1");
  });
});
