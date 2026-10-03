/**
 * Demo fixtures for VITE_MOCK=1. Companies, people and events are fictional; the shapes,
 * codes and quirks (state-plan standards, open cases, shared sites, ID-prefixed names,
 * stale accident detail) follow docs/data-profile.md.
 */
import type { FxCitation, FxEstablishment, FxInspection, FxProject, FxSub, HazardKey, ViolType } from "./model";

export const DATA_AS_OF = "2026-10-02";
export const ACCIDENT_DETAIL_THROUGH = "2025-03-28";

function cit(
  id: string,
  type: ViolType,
  standard: string,
  hazard: HazardKey,
  initial: number | null,
  current: number | null,
  extra: Partial<FxCitation> = {},
): FxCitation {
  return { id, type, standard, hazard, initial, current, ...extra };
}

function insp(
  nr: number,
  open: string,
  close: string | null,
  type: string,
  city: string,
  state: string,
  est: string,
  cits: FxCitation[],
  extra: Partial<FxInspection> = {},
): FxInspection {
  return {
    nr,
    open,
    close,
    type,
    city,
    state,
    jurisdiction: "federal",
    est,
    fatality: "none",
    shared: 0,
    cits,
    ...extra,
  };
}

function est(
  key: string,
  display_name: string,
  variants: string[],
  address: string | null,
  city: string | null,
  state: string | null,
  zip: string | null,
  trade_label: string | null,
  rest: Partial<FxEstablishment> = {},
): FxEstablishment {
  return {
    key,
    display_name,
    name_variants: variants,
    address,
    city,
    state,
    zip,
    trade_label,
    bucket: "matched",
    method: "rule",
    rule_id: "M1_same_name_same_state",
    confidence: null,
    rationale: "Same cleaned name and mailing state as entered.",
    ...rest,
  };
}

// --- 1. High concern: cited fatality --------------------------------------------------------------
const summitRidge: FxSub = {
  sub_id: "sub-summit",
  entered_name: "Summit Ridge Roofing",
  entered_city: "Dallas",
  entered_state: "TX",
  trade: "roofing",
  display_name: "SUMMIT RIDGE ROOFING LLC",
  trade_label: "Roofing contractors (238160)",
  trade_p50: 0.9,
  trade_p75: 1.6,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-summit-1", "SUMMIT RIDGE ROOFING LLC", ["SUMMIT RIDGE ROOFING LLC", "SUMMIT RIDGE ROOFING, L.L.C.", "SUMMIT RIDGE ROOFING"], "4410 Irving Blvd", "Dallas", "TX", "75247", "Roofing contractors (238160)"),
    est("e-summit-2", "SUMMIT RIDGE ROOFING LLC", ["SUMMIT RIDGE ROOFING LLC"], "1200 E Lamar Blvd Ste 210", "Arlington", "TX", "76011", "Roofing contractors (238160)", {
      rule_id: "M2_same_name_other_address",
      rationale: "Same cleaned name in Texas at a second address (regional office); distinctive name, same trade.",
    }),
  ],
  inspections: [
    insp(1812044, "2026-06-03", null, "Planned", "Plano", "TX", "e-summit-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 16131, 16131),
      cit("01002", "S", "1926.503(a)(1)", "fall", 9677, 9677),
    ]),
    insp(1714390, "2024-08-19", "2025-02-11", "Complaint", "Frisco", "TX", "e-summit-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 15625, 11000),
      cit("01002", "S", "1926.1053(b)(1)", "ladder", 6250, 4400),
      cit("02001", "O", "1910.1200(e)(1)", "hazcom", 0, 0),
    ]),
    insp(1598712, "2022-03-14", "2022-11-30", "Fatality/Catastrophe", "McKinney", "TX", "e-summit-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 14502, 10150),
      cit("01002", "S", "1926.503(a)(1)", "fall", 9670, 6770),
      cit("01003", "S", "1926.20(b)(2)", "other", 9670, 6770),
    ], {
      fatality: "fatality_cited",
      shared: 2,
      accidents: [
        {
          summary_nr: 220481157,
          event_date: "2022-03-14",
          description: "Employee falls from roof edge and is killed",
          narrative:
            "At approximately 10:30 a.m. on March 14, 2022, an employee was installing underlayment on a two-story residence with a 6/12 roof pitch. The employee was not connected to a personal fall arrest system. The employee slipped near the eave and fell approximately 22 feet to a concrete driveway. Emergency services transported the employee to a hospital, where the employee died of the injuries.",
          fatal_n: 1,
          injured_n: 0,
          employers_on_site: 2,
        },
      ],
    }),
    insp(1533208, "2021-05-10", "2021-09-02", "Planned", "Arlington", "TX", "e-summit-2", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 13653, 9557),
    ], { shared: 4 }),
    insp(1427765, "2019-09-23", "2020-01-15", "Referral", "Denton", "TX", "e-summit-1", [
      cit("01001", "S", "1926.1053(b)(1)", "ladder", 5290, 3700),
      cit("01002", "S", "1926.102(a)(1)", "ppe", 3967, 2777),
    ]),
    insp(1305521, "2018-04-02", "2018-06-20", "Accident", "Dallas", "TX", "e-summit-1", [], {
      fatality: "accident_outcome_unknown",
      dq: ["Accident-type inspection with no accident detail in OSHA's accident tables."],
    }),
    insp(1208833, "2017-02-15", "2017-04-30", "Planned", "Garland", "TX", "e-summit-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 7500, 5250),
    ]),
  ],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 2. Review: repeat fall-protection citations ----------------------------------------------------
const loneStar: FxSub = {
  sub_id: "sub-lonestar",
  entered_name: "Lone Star Framing",
  entered_city: "Fort Worth",
  entered_state: "TX",
  trade: "framing",
  display_name: "LONE STAR FRAMING INC",
  trade_label: "Framing contractors (238130)",
  trade_p50: 1.0,
  trade_p75: 1.7,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-lonestar-1", "LONE STAR FRAMING INC", ["LONE STAR FRAMING INC", "LONE STAR FRAMING, INC.", "LONESTAR FRAMING INC"], "2901 Hemphill St", "Fort Worth", "TX", "76110", "Framing contractors (238130)"),
  ],
  inspections: [
    insp(1789310, "2025-11-04", null, "Planned", "Keller", "TX", "e-lonestar-1", [
      cit("01001", "R", "1926.501(b)(13)", "fall", 48387, 48387),
      cit("01002", "S", "1926.451(g)(1)", "scaffold", 16131, 16131),
    ], { shared: 3 }),
    insp(1695220, "2024-02-20", "2024-07-18", "Planned", "Southlake", "TX", "e-lonestar-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 15625, 11720),
      cit("01002", "S", "1926.1053(b)(4)", "ladder", 6250, 4690),
    ]),
    insp(1611904, "2022-06-07", "2022-10-21", "Complaint", "Fort Worth", "TX", "e-lonestar-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 14502, 10150),
      cit("01002", "S", "1926.503(a)(1)", "fall", 7251, 5076),
    ]),
    // A second repeat, outside the 5-year window: switching the lookback to 10 years makes this High concern.
    insp(1489012, "2020-08-12", "2020-12-03", "Planned", "Burleson", "TX", "e-lonestar-1", [
      cit("01001", "R", "1926.501(b)(13)", "fall", 26988, 18892),
    ]),
    insp(1402266, "2019-05-28", "2019-08-14", "Planned", "Mansfield", "TX", "e-lonestar-1", [
      cit("01001", "S", "1926.501(b)(13)", "fall", 9054, 6338),
    ]),
  ],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 3. No flags ----------------------------------------------------------------------------------------
const brazos: FxSub = {
  sub_id: "sub-brazos",
  entered_name: "Brazos Electric",
  entered_city: "Austin",
  entered_state: "TX",
  trade: "electrical",
  display_name: "BRAZOS ELECTRIC CO",
  trade_label: "Electrical contractors (238210)",
  trade_p50: 0.6,
  trade_p75: 1.2,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-brazos-1", "BRAZOS ELECTRIC CO", ["BRAZOS ELECTRIC CO", "BRAZOS ELECTRIC COMPANY"], "8700 Burnet Rd", "Austin", "TX", "78757", "Electrical contractors (238210)"),
  ],
  inspections: [
    insp(1776105, "2025-07-15", "2025-09-30", "Planned", "Round Rock", "TX", "e-brazos-1", [
      cit("01001", "O", "1926.405(g)(2)", "electrical", 1200, 900),
    ], { shared: 5 }),
    insp(1672450, "2023-10-03", "2023-10-03", "Planned", "Austin", "TX", "e-brazos-1", []),
    insp(1548877, "2021-09-21", "2021-09-21", "Planned", "Pflugerville", "TX", "e-brazos-1", []),
  ],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 4. No OSHA record ----------------------------------------------------------------------------------
const hillCountry: FxSub = {
  sub_id: "sub-hillcountry",
  entered_name: "Hill Country Glazing",
  entered_city: "San Marcos",
  entered_state: "TX",
  trade: "glazing",
  display_name: null,
  trade_label: "Glass and glazing contractors (238150)",
  trade_p50: 0.7,
  trade_p75: 1.3,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [],
  inspections: [],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 5. Pending match question (possible record with a red flag) -----------------------------------------
const trinity: FxSub = {
  sub_id: "sub-trinity",
  entered_name: "Trinity Concrete",
  entered_city: "Dallas",
  entered_state: "TX",
  trade: "concrete",
  display_name: "TRINITY CONCRETE LLC",
  trade_label: "Poured concrete contractors (238110)",
  trade_p50: 0.8,
  trade_p75: 1.4,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-trinity-1", "TRINITY CONCRETE LLC", ["TRINITY CONCRETE LLC", "TRINITY CONCRETE"], "3150 Commerce St", "Dallas", "TX", "75226", "Poured concrete contractors (238110)"),
    est("e-trinity-ok", "TRINITY CONCRETE CONSTRUCTION LLC", ["TRINITY CONCRETE CONSTRUCTION LLC", "TRINITY CONCRETE CONST LLC"], "5501 S Agnew Ave", "Oklahoma City", "OK", "73119", "Poured concrete contractors (238110)", {
      bucket: "possible",
      method: "llm",
      rule_id: null,
      confidence: 0.5,
      rationale: "Same trade (concrete) and active 2018–2022, overlapping the matched records, but a different state and no shared address.",
    }),
    est("e-trinity-x", "TRINITY CONCRETE PUMPING INC", ["TRINITY CONCRETE PUMPING INC"], "77 Industrial Pkwy", "Ennis", "TX", "75119", "Concrete pumping (238990)", {
      bucket: "excluded",
      method: "rule",
      rule_id: "X1_different_name_core",
      rationale: "Different name core (CONCRETE PUMPING) and a different trade.",
    }),
  ],
  inspections: [
    insp(1748822, "2025-03-11", "2025-08-05", "Planned", "Irving", "TX", "e-trinity-1", [
      cit("01001", "S", "1926.1153(d)(1)", "silica", 8500, 6000),
    ]),
    insp(1655093, "2023-04-24", "2023-04-24", "Planned", "Dallas", "TX", "e-trinity-1", []),
    insp(1580377, "2021-11-08", "2022-02-14", "Referral", "Grand Prairie", "TX", "e-trinity-1", [
      cit("01001", "S", "1926.701(b)", "struck", 9670, 6770),
    ], { shared: 2 }),
    insp(1471840, "2020-02-18", "2020-02-18", "Planned", "Dallas", "TX", "e-trinity-1", []),
    // Possible match (not counted until the GC answers):
    insp(1556019, "2021-07-27", "2022-05-19", "Planned", "Norman", "OK", "e-trinity-ok", [
      cit("01001", "W", "1926.652(a)(1)", "excavation", 136532, 95572),
      cit("01002", "S", "1926.651(c)(2)", "excavation", 13653, 9557),
    ]),
    insp(1352290, "2018-10-02", "2018-12-11", "Complaint", "Oklahoma City", "OK", "e-trinity-ok", [
      cit("01001", "S", "1926.651(k)(1)", "excavation", 12934, 9054),
    ]),
    insp(1690012, "2024-01-09", "2024-01-09", "Planned", "Waxahachie", "TX", "e-trinity-x", []),
  ],
  questions: [
    {
      question_id: "q-trinity-ok",
      text: "Is TRINITY CONCRETE CONSTRUCTION LLC (5501 S Agnew Ave, Oklahoma City, OK; inspected 2018–2022) the same company as Trinity Concrete of Dallas, TX?",
      establishment_keys: ["e-trinity-ok"],
      ai_suggestion: "unsure",
      ai_rationale: "Same trade (concrete) and overlapping years, but a different state and no shared address with the Dallas records.",
    },
  ],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 6. Generic name: needs adjudication, then possible matches (not counted) ------------------------------
const abcDrywall: FxSub = {
  sub_id: "sub-abc",
  entered_name: "ABC Drywall",
  entered_city: "Houston",
  entered_state: "TX",
  trade: "drywall",
  display_name: "ABC DRYWALL LLC",
  trade_label: "Drywall and insulation contractors (238310)",
  trade_p50: 0.7,
  trade_p75: 1.3,
  licence_status: null,
  needs_adjudication: true,
  adjudication: [
    { key: "e-abc-hou2", bucket: "matched", method: "llm", confidence: 0.86, rationale: "Same name and city as the matched record; a different Houston street address, active 2019–2021 like the matched records." },
    { key: "e-abc-la", bucket: "possible", method: "llm", confidence: 0.55, rationale: "Generic name in another state (Louisiana). Same trade, but no shared address and a different owner name on the filings." },
    { key: "e-abc-fl", bucket: "excluded", method: "llm", confidence: 0.9, rationale: "Different name core (A B C DRYWALL & ACOUSTICAL), Florida only, ceilings trade; no overlap with the entered company." },
  ],
  establishments: [
    est("e-abc-hou", "ABC DRYWALL LLC", ["ABC DRYWALL LLC", "ABC DRYWALL"], "6120 Westview Dr", "Houston", "TX", "77055", "Drywall and insulation contractors (238310)"),
    est("e-abc-hou2", "ABC DRYWALL", ["ABC DRYWALL"], "10450 Hammerly Blvd", "Houston", "TX", "77043", "Drywall and insulation contractors (238310)", {
      bucket: "possible", method: "rule", rule_id: null, rationale: "Same generic name and city at a different address; sent to the adjudicator.",
    }),
    est("e-abc-la", "ABC DRYWALL INC", ["ABC DRYWALL INC", "A.B.C. DRYWALL INC"], "4100 Florida Blvd", "Baton Rouge", "LA", "70806", "Drywall and insulation contractors (238310)", {
      bucket: "possible", method: "rule", rule_id: null, rationale: "Generic name in another state; sent to the adjudicator.",
    }),
    est("e-abc-fl", "A B C DRYWALL & ACOUSTICAL", ["A B C DRYWALL & ACOUSTICAL", "ABC DRYWALL AND ACOUSTICAL INC"], "2250 NW 7th Ave", "Miami", "FL", "33127", "Acoustical ceilings (238310)", {
      bucket: "possible", method: "rule", rule_id: null, rationale: "Similar name in another state; sent to the adjudicator.",
    }),
  ],
  inspections: [
    insp(1733480, "2024-12-02", "2025-03-20", "Planned", "Katy", "TX", "e-abc-hou", [
      cit("01001", "S", "1926.451(g)(1)", "scaffold", 8000, 5600),
    ], { shared: 6 }),
    insp(1641187, "2023-02-13", "2023-02-13", "Planned", "Houston", "TX", "e-abc-hou", []),
    insp(1460301, "2019-11-19", "2020-03-05", "Planned", "Sugar Land", "TX", "e-abc-hou2", [
      cit("01001", "S", "1926.1053(b)(1)", "ladder", 4500, 3150),
    ]),
    insp(1702264, "2024-04-15", "2024-08-29", "Planned", "Baton Rouge", "LA", "e-abc-la", [
      cit("01001", "S", "1926.451(e)(1)", "scaffold", 7600, 5320),
      cit("01002", "S", "1926.501(b)(1)", "fall", 9900, 6930),
    ]),
    insp(1620558, "2022-09-06", "2022-12-12", "Complaint", "Lafayette", "LA", "e-abc-la", [
      cit("01001", "S", "1926.451(g)(1)", "scaffold", 7000, 4900),
    ]),
    insp(1509946, "2020-10-26", "2020-10-26", "Planned", "Baton Rouge", "LA", "e-abc-la", []),
    insp(1418870, "2019-07-08", "2019-09-12", "Planned", "Metairie", "LA", "e-abc-la", [
      cit("01001", "O", "1926.405(a)(2)", "electrical", 1500, 1000),
    ]),
    insp(1590034, "2022-01-11", "2022-04-02", "Planned", "Miami", "FL", "e-abc-fl", [
      cit("01001", "S", "1926.501(b)(1)", "fall", 9500, 6650),
    ]),
    insp(1488152, "2020-06-30", "2020-06-30", "Planned", "Doral", "FL", "e-abc-fl", []),
  ],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: [],
};

// --- 7. WA state-plan sub with licence -------------------------------------------------------------------
const cascade: FxSub = {
  sub_id: "sub-cascade",
  entered_name: "Cascade Steel Erectors",
  entered_city: "Tacoma",
  entered_state: "WA",
  trade: "steel erection",
  display_name: "CASCADE STEEL ERECTORS INC",
  trade_label: "Structural steel contractors (238120)",
  trade_p50: 1.1,
  trade_p75: 1.8,
  licence_status: "Active",
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-cascade-1", "CASCADE STEEL ERECTORS INC", ["CASCADE STEEL ERECTORS INC", "WA603481225 - CASCADE STEEL ERECTORS INC", "CASCADE STEEL ERECTORS"], "3415 S Pine St", "Tacoma", "WA", "98409", "Structural steel contractors (238120)"),
  ],
  inspections: [
    insp(1801177, "2026-04-21", null, "Planned", "Seattle", "WA", "e-cascade-1", [
      cit("01001", "S", "WAC 296-155-24609(2)", "fall", 5400, 5400),
      cit("01002", "S", "WAC 296-155-24611(1)", "fall", 5400, 5400),
      cit("01003", "S", "WAC 296-155-53300(1)", "crane", 3600, 3600),
    ], { jurisdiction: "state_plan", dq: ["Employer name carried an ID prefix (WA603481225 - …); cleaned before matching."] }),
    insp(1687340, "2023-11-29", "2024-05-02", "Planned", "Bellevue", "WA", "e-cascade-1", [
      cit("01001", "S", "WAC 296-155-24609(2)", "fall", 4800, 3600),
      cit("01002", "S", "WAC 296-155-24615(2)", "fall", 4800, 3600),
    ], { jurisdiction: "state_plan", shared: 3 }),
    insp(1612233, "2022-07-11", "2022-12-08", "Complaint", "Everett", "WA", "e-cascade-1", [
      cit("01001", "S", "WAC 296-155-24609(2)", "fall", 3900, 2900),
      cit("01002", "S", "WAC 296-155-100(1)", "ppe", 1950, 1460),
    ], { jurisdiction: "state_plan", dq: ["Employer name carried an ID prefix (WA603481225 - …); cleaned before matching."] }),
    insp(1501288, "2020-09-15", "2021-01-26", "Planned", "Tacoma", "WA", "e-cascade-1", [
      cit("01001", "S", "WAC 296-155-53300(1)", "crane", 2800, 2100),
    ], { jurisdiction: "state_plan" }),
  ],
  questions: [],
  injury_rates: [],
  licences: [
    {
      source: "WA L&I",
      number: "CASCASE871NM",
      name: "CASCADE STEEL ERECTORS INC",
      status: "Active",
      expires: "2027-05-14",
      specialty: "Construction contractor, general",
    },
  ],
  dq_warnings: [
    "Washington is a state-plan state: inspections were done by WA L&I (DOSH) and cite Washington codes (WAC 296-155), mapped to the same hazard categories as federal codes.",
  ],
};

// --- 8. ITA injury rates -----------------------------------------------------------------------------------
const gulfCoast: FxSub = {
  sub_id: "sub-gulfcoast",
  entered_name: "Gulf Coast Mechanical",
  entered_city: "Houston",
  entered_state: "TX",
  trade: "mechanical",
  display_name: "GULF COAST MECHANICAL INC",
  trade_label: "Plumbing, heating and AC contractors (238220)",
  trade_p50: 0.7,
  trade_p75: 1.3,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-gulf-1", "GULF COAST MECHANICAL INC", ["GULF COAST MECHANICAL INC", "GULF COAST MECHANICAL, INC."], "7800 Harwin Dr", "Houston", "TX", "77036", "Plumbing, heating and AC contractors (238220)"),
  ],
  inspections: [
    insp(1759940, "2025-05-06", "2025-05-06", "Planned", "Pasadena", "TX", "e-gulf-1", [], { shared: 8 }),
    insp(1663712, "2023-06-20", "2023-10-11", "Referral", "Houston", "TX", "e-gulf-1", [
      cit("01001", "S", "1926.651(c)(2)", "excavation", 7700, 5390),
    ]),
    insp(1571209, "2021-12-01", "2021-12-01", "Planned", "Baytown", "TX", "e-gulf-1", []),
    insp(1444180, "2019-10-14", "2019-12-19", "Planned", "Houston", "TX", "e-gulf-1", [
      cit("01001", "O", "1910.1200(h)(1)", "hazcom", 960, 0),
    ]),
  ],
  questions: [],
  injury_rates: [
    { year: 2025, establishment_name: "GULF COAST MECHANICAL INC", hours: 412000, employees: 196, trir: 1.9, dart: 1.0, deaths: 0, peer_trir: 2.3, flagged: false },
    { year: 2024, establishment_name: "GULF COAST MECHANICAL INC", hours: 398500, employees: 188, trir: 2.0, dart: 1.0, deaths: 0, peer_trir: 2.4, flagged: false },
    { year: 2023, establishment_name: "GULF COAST MECHANICAL INC", hours: 371200, employees: 176, trir: 2.7, dart: 1.6, deaths: 0, peer_trir: 2.4, flagged: false },
    { year: 2022, establishment_name: "GULF COAST MECHANICAL INC", hours: 344900, employees: 165, trir: 3.5, dart: 2.3, deaths: 0, peer_trir: 2.5, flagged: false },
    { year: 2021, establishment_name: "GULF COAST MECHANICAL INC", hours: 3290000, employees: 158, trir: 0.4, dart: 0.2, deaths: 0, peer_trir: 2.5, flagged: true },
  ],
  licences: [],
  dq_warnings: ["2021 injury-rate filing reports about 10× the hours of other years (likely a typo); its TRIR is shown but excluded from comparisons."],
};

// --- 9. No recent record --------------------------------------------------------------------------------------
const pecos: FxSub = {
  sub_id: "sub-pecos",
  entered_name: "Pecos Masonry",
  entered_city: "El Paso",
  entered_state: "TX",
  trade: "masonry",
  display_name: "PECOS MASONRY & STONE",
  trade_label: "Masonry contractors (238140)",
  trade_p50: 1.0,
  trade_p75: 1.6,
  licence_status: null,
  needs_adjudication: false,
  adjudication: [],
  establishments: [
    est("e-pecos-1", "PECOS MASONRY & STONE", ["PECOS MASONRY & STONE", "PECOS MASONRY AND STONE CO"], "1921 Texas Ave", "El Paso", "TX", "79901", "Masonry contractors (238140)"),
  ],
  inspections: [
    insp(316845201, "2014-03-18", "2014-07-09", "Planned", "El Paso", "TX", "e-pecos-1", [
      cit("01001", "S", "1926.451(g)(1)", "scaffold", 2800, 1960),
      cit("01002", "S", "1926.451(b)(1)", "scaffold", 2100, 1470),
    ]),
    insp(315220984, "2011-05-24", "2011-08-30", "Planned", "Las Cruces", "NM", "e-pecos-1", [
      cit("01001", "S", "1926.1053(b)(1)", "ladder", 1500, 1050),
    ]),
  ],
  questions: [],
  injury_rates: [],
  licences: [],
  dq_warnings: ["Penalties before 2010 are often blank in OSHA's data; older history is judged by citation type, not dollars."],
};

export function seedProjects(): FxProject[] {
  return [
    {
      project_id: "demo-riverside",
      name: "Riverside Medical Office Building",
      state: "TX",
      lookback_years: 5,
      created_at: "2026-09-28T15:12:00Z",
      subs: [summitRidge, loneStar, brazos, hillCountry, trinity, abcDrywall, cascade, gulfCoast, pecos],
    },
    {
      project_id: "demo-northgate",
      name: "Northgate Elementary Addition",
      state: "WA",
      lookback_years: 10,
      created_at: "2026-09-30T18:40:00Z",
      subs: [],
    },
  ];
}
