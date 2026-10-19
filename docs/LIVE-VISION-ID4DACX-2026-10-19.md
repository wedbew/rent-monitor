# Live vision check — ID4DACX — 2026-10-19

Owner-authorized sample: [Otodom listing ID4DACX](https://www.otodom.pl/pl/oferta/swietna-lokalizacja-i-bezposrednio-47-6-m2-i-pietro-stan-idealny-ID4DACX).

**Result:** current `vision-v2` successfully processed real listing photographs and returned equipment
observations. This is live-provider **stage** evidence. It is not a full API/queue/report-UI journey,
an OCR-positive test, an accuracy benchmark or a deployment of the current application.

## Method and limits

- Source: merged `8b738ffe561494cdb50d3499424b497d95d452e8`.
- Start: 2026-10-19 10:10:03 Europe/Warsaw (08:10:03 UTC).
- Existing local API container had `vision-v1`, while its application environment had a configured
  OpenRouter client and enabled image processing. Current tracked Python source was extracted into
  a new temporary directory; the running API/workers/images were not replaced or restarted.
- Used current production listing fetch, image preparation, `OpenRouterVision`, OpenRouter payload/
  parsing, price-catalog estimate, shared limiter and Postgres budget gate. Existing credentials
  stayed inside the application process and were never printed or copied into evidence.
- One listing fetch attempt, one model POST attempt, at most 25 photos + 2 plans, existing image
  host/size/pixel restrictions and model deadline. Additional per-run estimated-cost ceiling:
  USD 0.05; no automatic retry. The existing monthly budget remained configured as before.
- No market import, finance valuation, customer account/credit charge, seller contact or production
  action. Normal provider usage/budget/throttle records remain; no existing audit was deleted.
- Persisted the returned typed `VisionRecord` to a private local JSON file and validated an equal
  read-back. This proves a file/contract round trip, **not live `audit.result` DB persistence**.
  DB pipeline persistence remains covered by the separately recorded offline integration tests.

## Observed results

| Field | Result |
|---|---|
| Model | `google/gemini-2.5-flash-lite` |
| Prompt | `vision-v2` |
| Advert images / submitted usable images | 13 / 13 |
| Extracted separate floor plans | 0; source `floorPlans` absent/empty |
| Image classifications | 11 interior, 2 exterior |
| OCR / notes | Both absent (`floor_plan_text: null`, `notes: null`) |
| Equipment observations | 5; all `visible_only`, none claimed included in sale |
| Tokens | 3,933 prompt; 478 completion |
| Reserved cost estimate | USD 0.002844 |
| Provider-reported cost | **USD 0.0005845** |
| Typed record file reload | Equal |

All 13 submitted images were visually inspected after the call; none is a floor-plan drawing.
Therefore null floor-plan OCR is consistent with this input. This sample cannot establish that
floor-plan extraction or transcription works on a real advert containing a readable plan.

## Equipment source verification: a real association defect

Ordinals below are zero-based, as required by the current prompt and contract.

| Returned item | Returned ordinal / confidence | Visual check |
|---|---|---|
| shower | 8 / 1 | Shower visible in image 8. |
| toilet | 8 / 1 | Toilet visible in image 8. |
| sink | 8 / 1 | Sink partially visible at image 8's left edge, clearly visible in image 7. |
| doorbell | 11 / 0.8 | Image 11 is an exterior balcony/garden view, not evidence of this item. Entrance fittings are in image 10. |
| intercom | 11 / 0.8 | Image 11 is exterior; the handset is visibly mounted beside the entrance in image 10. |

The last two associations are **confirmed wrong**. A model using one-based positions is a plausible
explanation (11 points to the eleventh image, zero-based 10), not a proven parser bug. The worker's
deterministic selected-image remapping cannot establish that an in-range model index semantically
identifies the right image. Do not fix this by subtracting one from every answer.

Proposed issue: **“Ground equipment observations in explicit image identities and validate source links.”**
Description: provide unambiguous per-image identities/labels in the model input, require matching
identities in observations, preserve mapping through failures/deduplication, and present associations
as unverified until validated. Add hand-built tests for ambiguous/index-convention responses and
source-order changes; evaluate against a small labelled sample. Preserve current behavior for old
reports and do not promote model confidence to a verified probability. Link G-01b/G-02b and #94.
No third-party image or raw listing payload should be copied into committed test fixtures.

## Additional runner defect found before execution

`scripts/live_audit_check.py` calls `journey_check.remove()`, which deletes **all audits, snapshots and
the listing row for the supplied reference**, not just the test user's rows. It is unsafe to reuse
against a previously analysed listing. That runner was **not used** in this check.

Proposed issue: **“Scope live-audit-check cleanup to resources created by the canary.”**
Acceptance: pre-create another user's audit/snapshot for the same listing; run/fail/clean the canary;
all pre-existing rows remain unchanged, only canary-owned rows are removed, and shared snapshots are
retained while referenced. Test failure/cancellation/concurrent runs. Do not infer deletion ownership
from the listing reference. Correct its docstring's one-request claim if normal retry/import behavior
can issue additional requests.

## Evidence and next step

Private, ignored local evidence:
[summary](../data/audit-evidence/2026-10-19/live-ID4DACX/summary.json),
[typed vision record](../data/audit-evidence/2026-10-19/live-ID4DACX/vision-record.json),
and `image-00.jpg` through `image-12.jpg` in the same directory. These are audit artifacts, not
application media persistence, public assets or reusable production test fixtures.

Next positive OCR proof needs a separately authorized sample with a readable floor plan. This
authorization/result does not justify repeated paid calls, national import or automatic reanalysis.
Keep the UI, media and seller-question work moving; their implementation does not require another
paid request. No issue was filed or closed by this check.
