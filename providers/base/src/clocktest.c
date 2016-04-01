/* clocktest.c - check for clock jitter on SMP machines */

#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>

#define __USE_GNU 1
#include <sched.h>

#define NSEC_PER_SEC    1000000000
#define MAX_JITTER      (double)0.2
#define ITERATIONS      10000

#define NSEC(ts) (ts.tv_sec*NSEC_PER_SEC + ts.tv_nsec)

#ifdef OLD_SCHED_SETAFFINITY
#define setaffinity(mask) sched_setaffinity(0,&mask)
#else
#define setaffinity(mask) sched_setaffinity(0,sizeof(mask),&mask)
#endif

int test_clock_jitter(){
    cpu_set_t cpumask;
    struct timespec *time;
    unsigned long nsec;
    unsigned slow_cpu, fast_cpu;
    double jitter;
    double largest_jitter = 0.0;
    unsigned cpu, num_cpus, iter;
    int failures = 0;

    num_cpus = sysconf(_SC_NPROCESSORS_CONF);
    if (num_cpus == 1) {
        printf("Single CPU detected. No clock jitter testing necessary.\n");
        return 0;
    }

    printf ("Testing for clock jitter on %u cpus\n", num_cpus);

    time=malloc(num_cpus * sizeof(struct timespec));

    for (iter=0; iter<ITERATIONS; iter++){
        for (cpu=0; cpu < num_cpus; cpu++) {
            CPU_ZERO(&cpumask); CPU_SET(cpu,&cpumask);
	        if (setaffinity(cpumask) < 0){
    	        perror ("sched_setaffinity"); return 1;
    	    }
    	    /*
    	     * by yielding this process should get scheduled on the cpu
        	 * specified by setaffinity
	         */
        	sched_yield();
            if (clock_gettime(CLOCK_REALTIME, &time[cpu]) < 0) {
                perror("clock_gettime"); return 1;
            }
        }

        slow_cpu = fast_cpu = 0;
        for (cpu=0; cpu < num_cpus; cpu++) {
            nsec = NSEC(time[cpu]);
            if (nsec < NSEC(time[slow_cpu])) { slow_cpu = cpu; }
            if (nsec > NSEC(time[fast_cpu])) { fast_cpu = cpu; }
        }
        jitter = ((double)(NSEC(time[fast_cpu]) - NSEC(time[slow_cpu]))
                  / (double)NSEC_PER_SEC);

#ifdef DEBUG
        printf("DEBUG: max jitter for pass %u was %f (cpu %u,%u)\n",
                iter,jitter,slow_cpu,fast_cpu);
#endif

    	if (jitter > MAX_JITTER || jitter < -MAX_JITTER){
	        printf ("ERROR, jitter = %f\n",jitter);
	        printf ("iter = %u, cpus = %u,%u\n",iter,slow_cpu,fast_cpu);
            failures++;
    	}
	    if (jitter > largest_jitter)
	        largest_jitter = jitter;
    }

    if (failures == 0)
        printf ("PASSED: largest jitter seen was %lf\n",largest_jitter);
    else
	    printf ("FAILED: %u iterations failed\n",failures);

    return (failures > 0);
}

/*
 * This is the original test_clock_direction() function. I've left it here for
 * reference and in case we wish to resurrect it for some reason. 
 * This should be removed in the future if the new version pans out.
int test_clock_direction()
{
	time_t starttime = 0;
	time_t stoptime = 0;
	int sleeptime = 60;
	float delta = 0;

	time(&starttime);
	sleep(sleeptime);
	time(&stoptime);

	delta = (int)stoptime - (int)starttime - sleeptime;
	printf("clock direction test: start time %d, stop time %d, sleeptime %u, delta %f\n",
				(int)starttime, (int)stoptime, sleeptime, delta);
	if (delta != 0)
	{
		printf("FAILED\n");
		return 1;
	}
	/// * otherwise * /
	printf("PASSED\n");
	return 0;
}*/

int test_clock_direction()
{
    struct timeval tval_start, tval_stop, tval_result;
    int sleeptime = 60;
    int failures = 0;
    int iteration;
    double deltas[5];
    
    printf("\nTesting clock direction for 5 minutes...\n");
    /* Because skew can vary, we'll run it 5 times */
    for (iteration = 0; iteration < 5; iteration++) {
        /* Replace time() calls with POSIX gettimeofday() */
        gettimeofday(&tval_start, NULL);
        sleep(sleeptime);
        gettimeofday(&tval_stop, NULL);
 
        /* timersub() gives us the delta pretty simply */
        timersub(&tval_stop, &tval_start, &tval_result);
        double starttime = tval_start.tv_sec + (tval_start.tv_usec / 1000000.0);
        double stoptime = tval_stop.tv_sec + (tval_stop.tv_usec / 1000000.0);
        deltas[iteration] = (tval_result.tv_sec - sleeptime) + (tval_result.tv_usec / 1000000.0);
    }

    for (iteration = 0; iteration < 5; iteration++) {
        /* if any one iteration fails, test fails */
        if (deltas[iteration] > 0.01)
        {
            printf("FAILED: Iteration %d delta: %f\n", iteration, deltas[iteration]);
            failures += 1;
        }
        /* otherwise */
        else {
            printf("PASSED: Iteration %d delta: %f\n", iteration, deltas[iteration]);
        }
    }
    printf("clock direction test: sleeptime %u sec per iteration, failed iterations: %d\n",
            sleeptime, failures);
    return (failures > 0);
}

int main()
{
	int failures = test_clock_jitter();
    if (failures == 0)
	{
		failures = test_clock_direction();
	}
	return failures;
}
