# Real PSID results for Blog Post 6

The income averaging comparison uses the same **1,522 adult children** from **952 families of origin** in every specification. The career-stage comparison uses its own common sample of **1,504 adult children** from **949 families of origin**, with positive single-observation income at every stage. Estimates are unweighted and describe the retained PSID sample.

## Income averaging

Adult child income is measured at ages 40 to 44 in all three specifications.

| Income measure | Estimated IGE | 95% family bootstrap interval |
| --- | --- | --- |
| One observation for each generation | 0.434 | 0.365 to 0.505 |
| Average parental income, one child observation | 0.517 | 0.445 to 0.592 |
| Average both generations | 0.508 | 0.441 to 0.575 |

Averaging income for both generations changes the IGE from 0.434 to 0.508. The paired difference is 0.074, with a 95% family bootstrap interval of 0.030 to 0.126. Averaging parental income alone gives 0.517. Averaging adult child income as well gives a lower point estimate than that intermediate specification.

Parental averages contain 3 to 7 observations per child (median 4). Mature adult child averages contain 2 to 3 observations (median 2).

![Income averaging comparison](income-averages.png)

## One observation at each career stage

Each estimate uses one selected adult child income observation from its age window and the same parental income average. Selection is nearest the midpoint of the age window, with the earlier income year breaking ties. The child sample is held fixed across all four windows. The final column also averages child income within each window on this same career-stage sample, so the one-observation and average columns can be compared within a window.

| Adult child age window | One child observation: IGE | 95% family bootstrap interval | Average child income: IGE |
| --- | --- | --- | --- |
| 25 to 29 | 0.468 | 0.397 to 0.536 | 0.431 |
| 30 to 34 | 0.513 | 0.440 to 0.596 | 0.472 |
| 35 to 39 | 0.501 | 0.434 to 0.578 | 0.493 |
| 40 to 44 | 0.511 | 0.438 to 0.584 | 0.501 |

Holding the parental income average fixed, the one-observation IGE is 0.468 at ages 25 to 29 and 0.511 at ages 40 to 44. The paired difference is 0.044, with a 95% family bootstrap interval of -0.023 to 0.122. The interval includes zero, so this comparison does not clearly distinguish the endpoint difference from zero. The sequence is not monotonic across these age windows.

![One adult child income observation at each career stage](child-age.png)

| Adult child age window | Mean selected age | Income years |
| --- | --- | --- |
| 25 to 29 | 26.77 | 1985 to 2006 |
| 30 to 34 | 31.67 | 1990 to 2010 |
| 35 to 39 | 36.54 | 1996 to 2016 |
| 40 to 44 | 41.58 | 2000 to 2020 |

The comparison holds the number of selected child observations at one per stage. Calendar period and family circumstances still change with age. It does not identify a true lifetime IGE or the amount of lifecycle bias.

## Checks and limitations

A higher IGE means a stronger association between parental and adult child family income. It is not the causal effect of giving parents more money.

Confidence intervals use 1,000 paired bootstrap draws that resample families of origin. The same draw is used across specifications within each comparison. Separate family-cluster standard errors are saved in the aggregate tables.

Income is converted to 2022 dollars before averaging. Parental income is measured in the child's co-resident family at approximate ages 15 to 19. Adult child income requires reference person or spouse/partner status. Family membership is observed at interview, while income covers the previous calendar year.

Survey weights were not supplied. The sample requires linked parents and repeated observations, so it does not represent all US children. The income measure is family income, rather than personal earnings.

With the linear cohort and sex adjustment on the same main sample, the one-observation and averaged estimates are 0.423 and 0.497. Restricting to consistent age histories retains 1,476 children; those two estimates are 0.452 and 0.528.

The source analysis checks compound identifiers, household income consistency, foreign keys, identical samples and positive finite regression inputs. It also verifies the simple OLS slope against an independent covariance calculation. The R aggregate check independently verifies measure keys, counts, finite estimates and intervals, paired differences, age coverage and wave totals before rendering this report.

Only aggregate results and figures are saved. The normalized tables and matched records stay in memory. [Replication details](../../README-real.md).
