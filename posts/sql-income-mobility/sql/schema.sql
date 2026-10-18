PRAGMA foreign_keys = ON;

CREATE TABLE families (
    family_id INTEGER PRIMARY KEY
);

CREATE TABLE people (
    person_id INTEGER PRIMARY KEY,
    family_id INTEGER NOT NULL REFERENCES families(family_id),
    birth_year INTEGER NOT NULL,
    generation TEXT NOT NULL CHECK (generation IN ('parent', 'child')),
    UNIQUE (family_id, person_id)
);

-- family_id is a stable family of origin identifier, not a current household.
-- The explicit relationship identifies the parent, even if a family has others.
CREATE TABLE links (
    child_id INTEGER PRIMARY KEY,
    parent_id INTEGER NOT NULL,
    family_id INTEGER NOT NULL,
    CHECK (child_id != parent_id),
    FOREIGN KEY (family_id, child_id) REFERENCES people(family_id, person_id),
    FOREIGN KEY (family_id, parent_id) REFERENCES people(family_id, person_id)
);

CREATE TABLE incomes (
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    year INTEGER NOT NULL,
    real_income REAL NOT NULL CHECK (real_income > 0),
    PRIMARY KEY (person_id, year)
);
