# Flow of the suspend-cycles-stress-test test plan

This description will focus on the suspend cycles and reboot process.

The remaining work log check, suspend time check, and log attachments will be
executed at the end of a suspend and reboot jobs.

## Definition of the test case name

- **suspend\_cycles\_{n}\_reboot{k} :**
  - Indicates the execution of a suspend operation. $n$ is the suspend index of the $k$th reboot.
  - For example: $S_{n,k}$
- **suspend\_cycles\_reboot{k}:**
  - Indicate the execution of a reboot operation, k is the the reboot index.
  - For example: $R_k$

## Example

If we are doing 5 suspends per reboot for 3 reboots (N = 5, K = 3), it means we have these jobs:

- `suspend_cycles_1_reboot1`: $S_{1,1}$
- `suspend_cycles_1_reboot{{suspend_reboot_id}}`: $S_{k,1}$, where $k = 1,2,3$
- `suspend_cycles_{{suspend_id}}_reboot{{suspend_reboot_id}}`: $S_{n, k}$, where $n = 2,3,4,5$ and $k=2,3$
- suspend\_cycles\_reboot{{suspend\_reboot\_id}}: $R_k$, where $k=1,2,3$ 

The flow will be the following:

$$
\begin{matrix}
  \text{Start} \rightarrow& S_{1,1} &\rightarrow& S_{2,1} &\rightarrow& S_{3,1} &\rightarrow& S_{4,1}
&\rightarrow& S_{5,1} &\rightarrow& R_1\\
  &S_{1,2} &\rightarrow& S_{2,2} &\rightarrow& S_{3,2} &\rightarrow& S_{4,2}
&\rightarrow& S_{5,2} &\rightarrow& R_2\\
  &S_{1,3} &\rightarrow& S_{2,3} &\rightarrow& S_{3,3} &\rightarrow& S_{4,3}
&\rightarrow& S_{5,3} &\rightarrow& R_3 & \rightarrow \text{End}\\
\end{matrix}
$$

## Relation between template and resource jobs

- suspend\_cycles\_1\_reboot1: job
  - For example: S<sub>A</sub>1
- suspend\_cycles\_1\_reboot{2...k}: template job
  - For example: S<sub>B</sub>1, S<sub>C</sub>1
  - After job:
    - suspend\_cycles\_reboot{{suspend\_reboot\_previous}}
      - For example: R<sub>A</sub>,  R<sub>B</sub>
  - Resource job:
    - stress\_s3\_cycles\_iterations\_1
      - Output:
        - suspend\_reboot\_id: reboot index
          - For example: B, C
        - suspend\_reboot\_previous: previous reboot index
          - For example: A, B
- suspend\_cycles\_{2…n}\_reboot{1...k}: template job
  - For example:
    - S<sub>A</sub>2, S<sub>A</sub>3, S<sub>A</sub>4, S<sub>A</sub>5
    - S<sub>B</sub>2, S<sub>B</sub>3, S<sub>B</sub>4, S<sub>B</sub>5
    - S<sub>C</sub>2, S<sub>C</sub>3, S<sub>C</sub>4, S<sub>C</sub>5
  - After job:
    - suspend\_cycles\_{{suspend\_id\_previous}}\_reboot{{suspend\_reboot\_id}}
      - For example:
        - S<sub>A</sub>1, S<sub>A</sub>2, S<sub>A</sub>3, S<sub>A</sub>4
        - S<sub>B</sub>1, S<sub>B</sub>2, S<sub>B</sub>3, S<sub>B</sub>4
        - S<sub>B</sub>1, S<sub>C</sub>2, S<sub>C</sub>3, S<sub>C</sub>4
  - Resource job:
    - stress\_s3\_cycles\_iterations\_multiple
      - Output:
        - suspend\_id: suspend index
          - For example: 2, 3, 4, 5
        - suspend\_id\_previous: previous suspend index
          - For example: 1, 2, 3, 4
        - suspend\_reboot\_id: reboot index
          - For example: A, B, C
- suspend\_cycles\_reboot{1...k}: template job
  - For example: R<sub>A</sub>, R<sub>B</sub>, R<sub>C</sub>
  - After job:
    - suspend\_cycles\_{{s3\_iterations}}\_reboot{{suspend\_reboot\_id}}
      - For example: S<sub>A</sub>5, S<sub>B</sub>5, S<sub>C</sub>5
  - Resource job:
    - stress\_suspend\_reboot\_cycles\_iterations
      - Output:
        - s3\_iterations: numbers of suspend  in each reboo
          - For example: 5
        - suspend\_reboot\_id: reboot index
          - For example: A, B, C

Or, as a table:

| Name of Job or Template Job | S<sub>A</sub>1 |          S<sub>k</sub>1           |                                                S<sub>k</sub>n                                                 |                 R<sub>k</sub>                  |
| --------------------------- |:--------------:|:---------------------------------:|:-------------------------------------------------------------------------------------------------------------:|:----------------------------------------------:|
| Resource Job               |      None      | stress\_s3\_cycles\_iterations\_1 |                                   stress\_s3\_cycles\_iterations\_multiple                                    |  stress\_suspend\_reboot\_cycles\_iterations   |
| Generated Job               | S<sub>A</sub>1 |  S<sub>B</sub>1, S<sub>C</sub>1   | S<sub>A</sub>2, ..., S<sub>A</sub>5; S<sub>B</sub>2, ..., S<sub>B</sub>5; S<sub>C</sub>2, ..., S<sub>C</sub>5 |  R<sub>A</sub>, R<sub>B</sub>, R<sub>C</sub>   |
| After Job                   |      None      |   R<sub>A</sub>,  R<sub>B</sub>   | S<sub>A</sub>1, ..., S<sub>A</sub>4; S<sub>B</sub>1, ..., S<sub>B</sub>4; S<sub>C</sub>1, ..., S<sub>C</sub>4 | S<sub>A</sub>5, S<sub>B</sub>5, S<sub>C</sub>5 |

### Test case link flow

|    S<sub>A</sub>1  & S<sub>k</sub>1    |                                     S<sub>k</sub>n                                      |    R<sub>k</sub>     |
|:--------------------------------------:|:---------------------------------------------------------------------------------------:|:--------------------:|
|             S<sub>A</sub>1             | &rarr; S<sub>A</sub>2 &rarr; S<sub>A</sub>3 &rarr; S<sub>A</sub>4 &rarr; S<sub>A</sub>5 | &rarr; R<sub>A</sub> |
| ( R<sub>A</sub> )&rarr; S<sub>B</sub>1 | &rarr; S<sub>B</sub>2 &rarr; S<sub>B</sub>3 &rarr; S<sub>B</sub>4 &rarr; S<sub>B</sub>5 | &rarr; R<sub>B</sub> |
| ( R<sub>B</sub> )&rarr; S<sub>C</sub>1 | &rarr; S<sub>C</sub>2 &rarr; S<sub>C</sub>3 &rarr; S<sub>C</sub>4 &rarr; S<sub>C</sub>5 | &rarr; R<sub>C</sub> |
<!-- markdownlint-enbale MD033 -->
