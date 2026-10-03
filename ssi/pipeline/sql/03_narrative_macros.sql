-- Accident narrative macros. Persistent (no TEMP); safe to re-run.
--
-- narrative_reports_death(txt): the narrative says the injured employee died, e.g. days later in hospital
-- ("remained hospitalized until October 24, 2018, when he died"). OSHA's injury degree is recorded at the
-- time of the report ("hospitalized"), so these deaths carry no fatality flag and no fatal injury row.
-- Word-bounded ("Diedrich" drill rig is not a death) and conservative: deaths that are not work-related,
-- heart attacks, and things that "died" (a battery, an engine) don't count. tests/test_narrative.py.
CREATE OR REPLACE MACRO narrative_reports_death(txt) AS
  coalesce(regexp_matches(txt,
    '(?i)((employee|worker|victim|coworker|co-worker|\bhe|\bshe)( #?\s?[0-9]+)?( later| subsequently| eventually)? '
    || '(died|was killed|succumbed|passed away)\b)'
    || '|(\bdied (as a result of|from|of) (his|her|the|their) (injuries|wounds|burns))'
    || '|(\b(when|where|from which) (he|she) died\b)'
    || '|(\b(later|subsequently|eventually) died\b)'
    || '|(\bdied (during|while in) (hospitalization|the hospital|surgery))')
  AND NOT regexp_matches(txt,
    '(?i)(non-work|not work[- ]related|unrelated to (his |her |the )?work|\b(battery|engine|motor) (had )?died\b'
    || '|vacation|heart attack|natural causes)'), false);
