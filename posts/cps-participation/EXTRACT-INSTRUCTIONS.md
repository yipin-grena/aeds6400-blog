# Recreating the IPUMS CPS extract

The completed analysis uses the supplied cps_00001 data and XML. These instructions document how to request an equivalent extract.

## Create the extract

1. Visit https://cps.ipums.org/cps/ and sign in or register for free CPS access.
2. Choose **Select Data**, then **Select Samples**.
3. Select every **Basic Monthly** sample from **January 2019 through December 2024**, inclusive: 72 monthly samples. Include March Basic, but **do not select ASEC**.
4. Add **AGE**, **LABFORCE**, and **WTFINL**. Keep/add **YEAR**, **MONTH**, **SERIAL**, **PERNUM**, and **ASECFLAG** for validation. Keep all persons; the script restricts the population.
5. Create a rectangular person-level extract. The preferred format is the default fixed-width data file with its **DDI/XML codebook**. Alternatively, request CSV with numeric category codes, retaining the codebook separately.
6. Download the data (`cps_XXXXX.dat.gz`) and XML (`cps_XXXXX.xml`). Keep their original matching names and place both in `data/raw/`. For CSV, place just one `.csv` or `.csv.gz` extract in that directory.
7. Save the extract description, creation/access date, IPUMS version/citation, sample list, and any case-selection settings in a provenance note.

The import does not require a password or API key. Do not share credentials.

## Why these variables?

- AGE: creates exhaustive groups 16-24, 25-54, 55-64, and 65+.
- LABFORCE: 1 = not in the labor force; 2 = in the labor force. Other codes are outside the analysis denominator.
- WTFINL: the Basic Monthly person weight. Earnings and ASEC weights are not appropriate for this analysis.
- Identifiers: catch duplicate records and missing months. People legitimately appear in several months; do not deduplicate across months.
- ASECFLAG: rejects ASEC records and confirms March Basic records (code 2).

## Official documentation

- Extraction: https://cps.ipums.org/cps/extract_instructions.shtml
- Weights: https://cps.ipums.org/cps-action/variables/WTFINL
- Labor-force status: https://cps.ipums.org/cps-action/variables/LABFORCE
- Age: https://cps.ipums.org/cps-action/variables/AGE
- ASEC distinction: https://cps.ipums.org/cps-action/variables/ASECFLAG
- Citation: https://cps.ipums.org/cps/citation.shtml
