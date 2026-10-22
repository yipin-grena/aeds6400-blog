PRAGMA foreign_keys = ON;

-- The layout mirrors the PSID's public documentation, but every value is
-- simulated. A person is identified by two numbers together: the 1968 family
-- ID (id68) and a person number (pn) within that family.
CREATE TABLE individuals (
    id68 INTEGER NOT NULL,
    pn INTEGER NOT NULL,
    birth_year INTEGER NOT NULL,
    sex TEXT NOT NULL CHECK (sex IN ('female', 'male')),
    PRIMARY KEY (id68, pn)
);

-- One row per child and parent, as in a FIMS parent map: a child can have a
-- mother row and a father row. Both people must exist in individuals.
CREATE TABLE parent_links (
    child_id68 INTEGER NOT NULL,
    child_pn INTEGER NOT NULL,
    parent_id68 INTEGER NOT NULL,
    parent_pn INTEGER NOT NULL,
    parent_type TEXT NOT NULL CHECK (parent_type IN ('M', 'F')),
    PRIMARY KEY (child_id68, child_pn, parent_type),
    FOREIGN KEY (child_id68, child_pn) REFERENCES individuals(id68, pn),
    FOREIGN KEY (parent_id68, parent_pn) REFERENCES individuals(id68, pn)
);

-- One row per family and survey year. The interview number identifies the
-- family in that year only, so income is keyed by year and interview number.
CREATE TABLE family_years (
    year INTEGER NOT NULL,
    interview_number INTEGER NOT NULL,
    family_income REAL NOT NULL CHECK (family_income > 0),
    PRIMARY KEY (year, interview_number)
);

-- One row per person and survey year: which family the person lived in that
-- year and their position in it. Sequence number 1 is the reference person
-- and 2 the spouse or partner; this simulation numbers others from 3.
CREATE TABLE individual_years (
    id68 INTEGER NOT NULL,
    pn INTEGER NOT NULL,
    year INTEGER NOT NULL,
    interview_number INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    relation_to_rp TEXT NOT NULL,
    PRIMARY KEY (id68, pn, year),
    FOREIGN KEY (id68, pn) REFERENCES individuals(id68, pn),
    FOREIGN KEY (year, interview_number) REFERENCES family_years(year, interview_number)
);
