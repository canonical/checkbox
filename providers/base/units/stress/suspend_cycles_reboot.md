# Flow of the suspend-cycles-stress-test test plan

This doc describes the execution flow of the `suspend-cycles-stress-test` test plan, specifically the `suspend_cycles_{n}_reboot{k}` and `suspend_cycles_reboot{k}`
jobs.

The remaining jobs in the test plan (`suspend-{n}-cycles-with-reboot-{k}-log-check`,
`-time-check`, and `-log-attach`) run once at the end, after all
suspend and reboot jobs have completed.

## Test case name definition

Let $N$ be the total number of suspends per reboot and $K$ be the total number of reboots. Then the following test case will be generated for all $n=1,\dots,N$ and $k=1,\dots,K$

- **`suspend_cycles_{n}_reboot{k}`**
  - Indicates the execution of a suspend operation. $n$ is the suspend index of the $k$th reboot.
  - Let $S_{n,k}$ denote this job
- **`suspend_cycles_reboot{k}`**
  - Indicate the execution of a reboot operation, $k$ is the the reboot index.
  - Let $R_k$ denote this job

The value of $N$ and $K$ can be controlled by `STRESS_S3_ITERATIONS` and `STRESS_SUSPEND_REBOOT_ITERATIONS` respectively.

## Example

If we are doing 5 suspends per reboot for 3 reboots ($N = 5, K = 3$), it means we have these jobs:

- `suspend_cycles_1_reboot1`: $S_{1,1}$
- `suspend_cycles_1_reboot{{suspend_reboot_id}}`: $S_{k,1}$, where $k = 1,2,3$
- `suspend_cycles_{{suspend_id}}_reboot{{suspend_reboot_id}}`: $S_{n, k}$, where $n = 2,3,4,5$ and $k=2,3$
- suspend_cycles_reboot{{suspend_reboot_id}}: $R_k$, where $k=1,2,3$ 

The execution flow will look like the following:

$$
\begin{matrix}
  \text{Start} &\rightarrow& S_{1,1} &\rightarrow& S_{2,1} &\rightarrow& S_{3,1} &\rightarrow& S_{4,1}
&\rightarrow& S_{5,1} &\rightarrow& R_1\\
  &\hookrightarrow&S_{1,2} &\rightarrow& S_{2,2} &\rightarrow& S_{3,2} &\rightarrow& S_{4,2}
&\rightarrow& S_{5,2} &\rightarrow& R_2\\
  &\hookrightarrow&S_{1,3} &\rightarrow& S_{2,3} &\rightarrow& S_{3,3} &\rightarrow& S_{4,3}
&\rightarrow& S_{5,3} &\rightarrow& R_3 & \rightarrow& \text{End}\\
\end{matrix}
$$

## Relation between template and resource jobs

To define the dependency relationship between these jobs, we first need the base case:

- `suspend_cycles_1_reboot1`: A simple job unit, no template involved.
  - This is $S_{1,1}$ from the flow graph above

Now we can consider jobs with a single variable $k$
- `suspend_cycles_1_reboot{2...K}`: template jobs
  - For example: $S_{1,2}$, $S_{1,3}$
  - They need to run after `suspend_cycles_reboot{{suspend_reboot_previous}}`
    - For example: $R_1$, $R_2$

To generate $k = 2,\dots,K$, we use the resource job `stress_s3_cycles_iterations_1`. It gives us 2 values 
  - `suspend_reboot_id`: current reboot index, $k$
  - `suspend_reboot_previous`: previous reboot index, $k-1$

The reboot jobs $R_k$ uses `stress_suspend_reboot_cycles_iterations`.
  - `suspend_reboot_id`, same $k$ as above


### Jobs with 2 variables

So far we have successfully generated the "initial" jobs for each reboot cycle $S_{1, 1\dots K}$ and the reboot jobs $R_{1\dots K}$. For each cycle $k$, we need to generate $S_{n, k}$ for $n=2,\dots,N$. To do this, we use another resource job `stress_s3_cycles_iterations_multiple`, which generates these values:
  - `suspend_id`: suspend index, $n$
  - `suspend_id_previous`: previous suspend index, $n-1$
  - `suspend_reboot_id`: reboot index $k$ from before 

Let's consider a concrete example. Using $N=5, K=3$ from before, we already have:

$$
\begin{matrix}
  S_{1,1} & S_{1,2}& S_{1,3}
\end{matrix}
$$

Using `stress_s3_cycles_iterations_multiple`, we can generate:

$$
\begin{matrix}
S_{2,1}& S_{3,1}& S_{4,1}& S_{5,1}\\
S_{2,2}& S_{3,2}& S_{4,2}& S_{5,2}\\
S_{2,3}& S_{3,3}& S_{4,3}& S_{5,3}
\end{matrix}
$$

which has the following dependency relationships:

1. Later suspend checks in the same reboot cycle should run after the previous suspend checks:
    $$
    \text{For all}\, k=1\dots K, n=2\dots N\\
    S_{n, k} \text{ runs after } S_{n-1, k}
    $$
2. All jobs in the current boot must run after the jobs in the previous boot.
    $$
    \text{For all}\, k=1\dots K-1\\
    R_k \text{ runs after } S_{N, k}\\
    S_{1, k+1} \text{ runs after } R_k
    $$

## Summary

| Job/Template ID | $S_{1,1}$ |    $S_{1,k}$    |                       $S_{n,k}$                       |   $R_k$   |
| --------------------------- |:---------:|:---------------:|:------------------------------------------------------:|:---------:|
| Resource Job               |      None      | `stress_s3_cycles_iterations_1` |                                   `stress_s3_cycles_iterations_multiple`                                    |  `stress_suspend_reboot_cycles_iterations`   |
| Generated Job               | $S_{1,1}$ |  $S_{1,2}$, $S_{1,3}$   | $S_{2,1}$, ..., $S_{5,1}$; $S_{2,2}$, ..., $S_{5,2}$; $S_{2,3}$, ..., $S_{5,3}$ |  $R_1$, $R_2$, $R_3$   |
| After Job                   |      None      |   $R_1$, $R_2$   | $S_{1,1}$, ..., $S_{4,1}$; $S_{1,2}$, ..., $S_{4,2}$; $S_{1,3}$, ..., $S_{4,3}$ | $S_{5,1}$, $S_{5,2}$, $S_{5,3}$ |