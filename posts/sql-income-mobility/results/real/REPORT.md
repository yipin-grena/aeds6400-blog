# Real PSID results for Blog Post 6

The analysis uses the same **1,522 adult children** in every comparison, from **952 families of origin**. These are real PSID and FIMS records. The estimates are unweighted and describe the retained sample.

| Income measure | Estimated IGE | 95% family bootstrap interval |
| --- | --- | --- |
| One observation for each generation, mature adult child | 0.434 | 0.365 to 0.505 |
| Average parental income, one mature adult child observation | 0.517 | 0.445 to 0.592 |
| Average both, adult child ages 40 to 44 | 0.508 | 0.441 to 0.575 |
| Average both, adult child ages 25 to 29 | 0.445 | 0.387 to 0.506 |
| Average both, adult child ages 30 to 34 | 0.490 | 0.425 to 0.556 |
| Average both, adult child ages 35 to 39 | 0.504 | 0.439 to 0.569 |

A higher IGE means a stronger association between parental and adult child family income. It is not the causal effect of giving parents more money.

Using averages for both generations changes the estimate from 0.434 to 0.508. The paired difference is 0.074, with a bootstrap interval from 0.030 to 0.126. Averaging only parental income gives 0.517. Averaging adult child income too produces a lower point estimate than that intermediate specification, so the effect of averaging differs across the two generations.

Holding the parental average fixed, the estimate is 0.445 when adult children are 25 to 29 and 0.508 at 40 to 44. This is evidence of sensitivity to measurement age. It does not identify a true lifetime IGE or isolate lifecycle bias from calendar-period and observation-count differences.

![Income averaging comparison](income-averages.png)

![Comparison across adult child ages](child-age.png)

## Checks and limitations

The program verifies compound identifiers, household income consistency, foreign keys, distinct children and identical samples. It checks the simple OLS estimate against an independent covariance formula. SQL and normalization tests use invented records, including negative incomes and missing years.

Income is converted to 2022 dollars before averaging. Parental income is measured in the child's co-resident family at approximate ages 15 to 19. Adult income requires reference person or spouse/partner status. Survey weights were not supplied. The sample requires linked parents and repeated observations, so it does not represent all US children. The income measure is family income, not personal earnings. Family membership is observed at interview, while income covers the previous calendar year.

With the linear cohort and sex adjustment, the one-year and averaged estimates are 0.423 and 0.497. After excluding inconsistent age histories, the retained sample has 1,476 children; the one-year and averaged estimates are 0.452 and 0.528.

Only aggregate results and figures are included here. The normalized tables and matched records stayed in memory. [Replication details](../../README-real.md).
