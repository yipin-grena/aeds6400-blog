WITH parent_family_years AS (
    -- One row per child and year: the income of the family in which the
    -- child's parent was reference person or spouse. DISTINCT keeps one row
    -- when the mother and father lived in the same family that year.
    SELECT DISTINCT l.child_id68, l.child_pn, y.year, y.interview_number,
           f.family_income
    FROM parent_links AS l
    JOIN individuals AS c
      ON c.id68 = l.child_id68 AND c.pn = l.child_pn
    JOIN individual_years AS y
      ON y.id68 = l.parent_id68 AND y.pn = l.parent_pn
    JOIN family_years AS f
      ON f.year = y.year AND f.interview_number = y.interview_number
    WHERE y.sequence_number IN (1, 2)
      AND y.relation_to_rp IN ('reference person', 'spouse')
      AND y.year - c.birth_year BETWEEN :p_start AND :p_end
),
parent_income AS (
    SELECT child_id68, child_pn, AVG(family_income) AS parent_income
    FROM parent_family_years
    GROUP BY child_id68, child_pn
    HAVING COUNT(*) = :p_years
       AND COUNT(DISTINCT year) = :p_years
),
child_income AS (
    SELECT c.id68, c.pn, AVG(f.family_income) AS child_income
    FROM individuals AS c
    JOIN individual_years AS y
      ON y.id68 = c.id68 AND y.pn = c.pn
    JOIN family_years AS f
      ON f.year = y.year AND f.interview_number = y.interview_number
    WHERE y.sequence_number IN (1, 2)
      AND y.relation_to_rp IN ('reference person', 'spouse')
      AND y.year - c.birth_year BETWEEN :c_start AND :c_end
    GROUP BY c.id68, c.pn
    HAVING COUNT(*) = :c_years
       AND COUNT(DISTINCT y.year) = :c_years
)
SELECT p.child_id68 AS id68, p.child_pn AS pn,
       p.parent_income, c.child_income
FROM parent_income AS p
JOIN child_income AS c
  ON c.id68 = p.child_id68 AND c.pn = p.child_pn
ORDER BY id68, pn;
