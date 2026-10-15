# Adres — a Polish workspace for property decisions

13 October 2026

## Character

A small architectural practice, rather than a trading terminal. The grid is exact; the language is human. Off-white mineral surfaces, ink-green text, restrained forest-green actions, numbered objects and measured linework make the interface feel deliberate. The doorway mark suggests a threshold: moving from an attractive listing toward understanding it.

Light is the default. Dark uses green-black surfaces and a pale lime action, with the same hierarchy and semantic labels. The theme is controlled explicitly and persists across pages. There is no automatic switch based on the operating system.

The original decorative floor-plan drawing is a brand graphic, not an inferred apartment plan. The login image evokes Polish interwar modernism; it is a fictional, AI-generated building and is labeled accordingly. Neither asset is listing evidence.

## Polish context is a product behavior

Use Polish units and conventions: `425 000 zł`, `42 m²`, monthly rent, clear city/district identity. Say “czynsz administracyjny” when describing the fee to the building association. Keep that cost separate from the rent paid to the owner. A price from an advertisement remains an offer price, not evidence of a completed transaction.

Do not let polished visuals imply certainty. Home cards retain missing-data warnings. A ready rent estimate still identifies unverified costs and renovation. The report asks the user to clarify the most useful missing input, with a ready-to-read seller question. No return, Max Bid or net income is calculated by the prototype.

## Information sequence

1. Home: one listing input, credit disclosure, activity, three recent analyses, local context.
2. Collection: search and status filter, meaningful empty state, dedicated report URLs.
3. Report: identity, price basis and limitation; concrete next step; rent, costs, purchase and evidence.
4. Details: native disclosures explain the estimate and definitions without hiding material uncertainty.
5. Login: minimal form, visibility control, recovery, alternative sign-in, clear route back. Decorative imagery follows the form on mobile.

No looping animation, rotating marketing slide or invented progress. Motion is subtle and respects reduced-motion preferences. Navigation stays page-based. Drawers are for mobile navigation; dialogs handle bounded confirmations and recovery.

## Tokens and implementation

`tokens.css` owns colors and themes; `v3.css` defines the Adres components on top of the inherited layout/interaction foundation. Local Arial/system sans requires no runtime font request. Buttons and fields have visible borders and keyboard focus. The theme control has an accessible action label and pressed state. Missing-data and progress states use words, not only color. Native dialogs retain focus containment; form errors are associated with their inputs and announced.

## Asset provenance

`plan.svg` is an original code-authored conceptual drawing. `daylight-building.jpg` is generated with the built-in imagegen tool and stored locally; no remote image is loaded at runtime.

Image prompt: portrait editorial architectural photograph of a fictional 1930s Polish modernist corner apartment building inspired by Gdynia; cream mineral plaster, curved balconies, dark-green steel railings, warm daylight and tree shadows; natural imperfections, lived-in residential character; no people, text, logos, watermark or recognizable real address; foliage at the bottom for overlay contrast.

Login composition was informed by the user-supplied screenshot and https://app.getartcraft.com/login. Its content, branding, imagery and code were not copied.

## Before production

Test whether people can distinguish rent from administrative fees, recognize missing costs, identify offer prices and find the next action without assistance. Check keyboard and screen-reader journeys, all contrast pairs and actual API content. Visual preference is not evidence of improved task completion; no user research has yet been performed.
