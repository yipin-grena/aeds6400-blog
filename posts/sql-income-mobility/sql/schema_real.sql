PRAGMA foreign_keys = ON;

-- Private, normalized tables for the real-data analysis. The caller creates
-- this database in memory; none of these tables is a publishable output.
CREATE TABLE people (
    id68 INTEGER NOT NULL,
    pn INTEGER NOT NULL,
    sex INTEGER,
    birth_year_proxy INTEGER,
    sample_member INTEGER,
    PRIMARY KEY (id68, pn)
);

CREATE TABLE parent_links (
    child_id68 INTEGER NOT NULL,
    child_pn INTEGER NOT NULL,
    parent_id68 INTEGER NOT NULL,
    parent_pn INTEGER NOT NULL,
    parent_type TEXT NOT NULL CHECK (parent_type IN ('M', 'F')),
    PRIMARY KEY (child_id68, child_pn, parent_type),
    FOREIGN KEY (child_id68, child_pn) REFERENCES people(id68, pn),
    FOREIGN KEY (parent_id68, parent_pn) REFERENCES people(id68, pn)
);

CREATE TABLE family_years (
    survey_year INTEGER NOT NULL,
    income_year INTEGER NOT NULL,
    interview_number INTEGER NOT NULL,
    family_income_nominal REAL,
    -- Constant 2022 dollars. Valid zeros and negative values remain available
    -- for averaging; nonpositive window means are excluded by the match query.
    family_income REAL,
    PRIMARY KEY (survey_year, interview_number)
);

CREATE TABLE person_years (
    id68 INTEGER NOT NULL,
    pn INTEGER NOT NULL,
    survey_year INTEGER NOT NULL,
    interview_number INTEGER NOT NULL,
    age INTEGER,
    income_age INTEGER,
    sequence_number INTEGER NOT NULL CHECK (sequence_number BETWEEN 1 AND 20),
    relation_code INTEGER NOT NULL,
    is_reference_or_partner INTEGER NOT NULL
        CHECK (is_reference_or_partner IN (0, 1)),
    PRIMARY KEY (id68, pn, survey_year),
    FOREIGN KEY (id68, pn) REFERENCES people(id68, pn),
    FOREIGN KEY (survey_year, interview_number)
        REFERENCES family_years(survey_year, interview_number)
);
