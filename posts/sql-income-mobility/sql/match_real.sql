-- The input tables contain only current family members and use income-year
-- ages. Parent resources are measured in the child's co-resident family.
-- A five-calendar-year window need not contain five survey observations.
WITH eligible_children AS (
    SELECT id68, pn, birth_year_proxy
    FROM people
    WHERE birth_year_proxy BETWEEN :birth_min AND :birth_max
),
parent_observations AS (
    SELECT DISTINCT c.id68, c.pn, f.survey_year, f.income_year,
           f.interview_number, f.family_income, cy.income_age
    FROM eligible_children AS c
    JOIN parent_links AS l
      ON l.child_id68 = c.id68 AND l.child_pn = c.pn
    JOIN person_years AS cy
      ON cy.id68 = c.id68 AND cy.pn = c.pn
    JOIN person_years AS py
      ON py.id68 = l.parent_id68 AND py.pn = l.parent_pn
     AND py.survey_year = cy.survey_year
     AND py.interview_number = cy.interview_number
    JOIN family_years AS f
      ON f.survey_year = cy.survey_year
     AND f.interview_number = cy.interview_number
    WHERE py.is_reference_or_partner = 1
      AND cy.income_age BETWEEN :p_start AND :p_end
      AND f.family_income IS NOT NULL
),
parent_ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY id68, pn
        ORDER BY ABS(income_age - :p_midpoint), income_year,
                 survey_year, interview_number
    ) AS midpoint_rank
    FROM parent_observations
),
parent_measures AS (
    SELECT id68, pn,
           AVG(family_income) AS parent_income,
           MAX(CASE WHEN midpoint_rank = 1 THEN family_income END)
               AS parent_single,
           COUNT(DISTINCT income_year) AS parent_n,
           AVG(income_age) AS parent_mean_age,
           MAX(CASE WHEN midpoint_rank = 1 THEN income_age END)
               AS parent_single_age,
           MIN(income_year) AS parent_first_year,
           MAX(income_year) AS parent_last_year
    FROM parent_ranked
    GROUP BY id68, pn
    HAVING COUNT(DISTINCT income_year) >= :p_min_obs
       AND AVG(family_income) > 0
),
child_observations AS (
    SELECT c.id68, c.pn, f.survey_year, f.income_year,
           f.interview_number, f.family_income, cy.income_age
    FROM eligible_children AS c
    JOIN person_years AS cy
      ON cy.id68 = c.id68 AND cy.pn = c.pn
    JOIN family_years AS f
      ON f.survey_year = cy.survey_year
     AND f.interview_number = cy.interview_number
    WHERE cy.is_reference_or_partner = 1
      AND cy.income_age BETWEEN :c_start AND :c_end
      AND f.family_income IS NOT NULL
),
child_ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY id68, pn
        ORDER BY ABS(income_age - :c_midpoint), income_year,
                 survey_year, interview_number
    ) AS midpoint_rank
    FROM child_observations
),
child_measures AS (
    SELECT id68, pn,
           AVG(family_income) AS child_income,
           MAX(CASE WHEN midpoint_rank = 1 THEN family_income END)
               AS child_single,
           COUNT(DISTINCT income_year) AS child_n,
           AVG(income_age) AS child_mean_age,
           MAX(CASE WHEN midpoint_rank = 1 THEN income_age END)
               AS child_single_age,
           MIN(income_year) AS child_first_year,
           MAX(income_year) AS child_last_year
    FROM child_ranked
    GROUP BY id68, pn
    HAVING COUNT(DISTINCT income_year) >= :c_min_obs
       AND AVG(family_income) > 0
)
SELECT c.id68, c.pn, c.birth_year_proxy,
       p.parent_income, p.parent_single, p.parent_n, p.parent_mean_age,
       p.parent_single_age, p.parent_first_year, p.parent_last_year,
       a.child_income, a.child_single, a.child_n, a.child_mean_age,
       a.child_single_age, a.child_first_year, a.child_last_year
FROM eligible_children AS c
JOIN parent_measures AS p ON p.id68 = c.id68 AND p.pn = c.pn
JOIN child_measures AS a ON a.id68 = c.id68 AND a.pn = c.pn
ORDER BY c.id68, c.pn;
