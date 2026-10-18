WITH parent_means AS (
    SELECT p.family_id, p.person_id,
           AVG(i.real_income) AS parent_income
    FROM people AS p
    JOIN incomes AS i ON i.person_id = p.person_id
    WHERE p.generation = 'parent'
      AND i.year - p.birth_year BETWEEN :p_start AND :p_end
    GROUP BY p.family_id, p.person_id
    HAVING COUNT(i.real_income) = :p_years
       AND COUNT(DISTINCT i.year) = :p_years
),
child_means AS (
    SELECT p.family_id, p.person_id,
           AVG(i.real_income) AS child_income
    FROM people AS p
    JOIN incomes AS i ON i.person_id = p.person_id
    WHERE p.generation = 'child'
      AND i.year - p.birth_year BETWEEN :c_start AND :c_end
    GROUP BY p.family_id, p.person_id
    HAVING COUNT(i.real_income) = :c_years
       AND COUNT(DISTINCT i.year) = :c_years
)
SELECT l.family_id, l.parent_id, l.child_id,
       p.parent_income, c.child_income
FROM links AS l
JOIN parent_means AS p
  ON p.family_id = l.family_id AND p.person_id = l.parent_id
JOIN child_means AS c
  ON c.family_id = l.family_id AND c.person_id = l.child_id
ORDER BY l.child_id;
