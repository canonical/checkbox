/* $Id: threaded_memtest.c,v 1.7 2008/02/12 01:17:07 gnichols Exp $
 *
 * A scalable, threaded memory exerciser/tester.
 *
 * Author: Will Woods <wwoods@redhat.com>
 * Copyright (C) 2006 Red Hat, Inc. All Rights Reserved.
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
 *
 * Notes:
 * This program uses sched_setaffinity(), which is Linux-specific. This could
 * probably be ported to other systems with a fairly simple #ifdef / #define
 * of setaffinity(), below. You might also have to find a replacement for
 * sysconf(), which (while a POSIX function) is not available on some other
 * systems (e.g. OSX).
 */

#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#ifdef __linux__
#include <sys/sysinfo.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <signal.h>
#define __USE_GNU 1
#include <pthread.h>
#include <sched.h>
#ifdef OLD_SCHED_SETAFFINITY
#define setaffinity(mask) sched_setaffinity(0,&mask)
#else
#define setaffinity(mask) sched_setaffinity(0,sizeof(mask),&mask)
#endif

#define VERSION "$Revision: 1.7 $" /* CVS version info */
#define DEFAULT_THREADS 2
#define DEFAULT_RUNTIME 60*15
#define DEFAULT_MEMPCT 0.95
#define BARLEN 40

/* configurable values used by the threads */
int verbose = 0;
int quiet = 0;
int parallel = 0;
unsigned num_threads, default_threads = DEFAULT_THREADS;
unsigned runtime, default_runtime = DEFAULT_RUNTIME;
unsigned long memsize, default_memsize;
/* system info */
unsigned num_cpus;
unsigned long total_ram;
/* statistic gathering */
struct timeval start={0,0}, finish={0,0}, duration={0,0};
unsigned long *loop_counters = NULL;
/* pointers for threads and their memory regions */
pthread_t *threads;
char **mmap_regions = NULL;
/* Thread mutexes and conditions */
unsigned created_threads = 0;
pthread_mutex_t ct_mutex = PTHREAD_MUTEX_INITIALIZER;
unsigned live_threads = 0;
pthread_mutex_t lt_mutex = PTHREAD_MUTEX_INITIALIZER;
unsigned mmap_done = 0;
pthread_mutex_t init_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t init_cond = PTHREAD_COND_INITIALIZER;
pthread_mutex_t mmap_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t mmap_cond = PTHREAD_COND_INITIALIZER;
pthread_mutex_t test_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t test_start = PTHREAD_COND_INITIALIZER;
pthread_mutex_t finish_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t finish_cond = PTHREAD_COND_INITIALIZER;
unsigned done = 0;
unsigned running_threads = 0;
/* short name of the program */
char *basename = NULL;

/* set the affinity for the current task to the given CPU */
int on_cpu(unsigned cpu){
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(cpu,&mask);
    if (setaffinity(mask) <  0){
        perror("sched_setaffinity");
        return -1;
    }
    return 0;
}

/* Parse a memsize string like '34m' or '128k' into a long int */
long unsigned parse_memsize(const char *str) {
    long unsigned size;
    char okchars[] = "GgMmKk%";
    char unit;
    size=atoi(str); /* ignores trailing non-digit chars */
    unit=str[strlen(str)-1];
    if (index(okchars,unit)) {
       switch (unit) {
           case 'G':
           case 'g':size *= 1024;
           case 'M':
           case 'm':size *= 1024;
           case 'K':
           case 'k':size *= 1024; break;
           case '%':size = (size/100.0)*total_ram; break;
        }
    }
    return size;
}
char memsize_str[22]; /* a 64-bit int is 20 digits long */
/* print a nice human-readable string for a large number of bytes */
char *human_memsize(long unsigned size) {
    char unit=' ';
    if (size > 10240) { unit='K'; size /= 1024; }
    if (size > 10240) { unit='M'; size /= 1024; }
    if (size > 10240) { unit='G'; size /= 1024; }
    snprintf(memsize_str,22,"%ld%c",size,unit);
    return memsize_str;
}

/* A cute little progress bar */
void progressbar(char *label, unsigned cur, unsigned total) {
    unsigned pos;
    char bar[BARLEN+1],spinner[]="-\\|/";
    pos=(BARLEN*cur)/total;
    memset(bar,'.',BARLEN);
    memset(bar,'#',pos);
    bar[BARLEN]='\0';
    if ((pos < BARLEN) && (total >= BARLEN*2))
        bar[pos]=spinner[cur%4];
    printf("\r%18s [%s] %u/%u",label,bar,cur,total);
    fflush(stdout);
}

/* This is the function that the threads run */
void *mem_twiddler(void *arg) {
    unsigned long thread_id, pages, pagesize, i, p;
    volatile long garbage;
    long *lp;
    int t,offset;
    char *my_region;
    unsigned long mapsize = *(unsigned long *)arg;

    /* Make sure each thread gets a unique ID */
    pthread_mutex_lock(&ct_mutex);
    thread_id=created_threads++;
    pthread_mutex_unlock(&ct_mutex);
    if (parallel) {
        /* let main() go as soon as the thread is created */
        mmap_done=1;
        pthread_cond_signal(&mmap_cond);
    }

    on_cpu(thread_id % num_cpus);
    pagesize=getpagesize();
    pages=mapsize/pagesize;

    /* Map a chunk of memory */
    if (verbose) printf("thread %ld: mapping %s RAM\n",
                        thread_id,human_memsize(mapsize));
    my_region=mmap(NULL,mapsize,PROT_READ|PROT_WRITE,
                   MAP_ANONYMOUS|MAP_PRIVATE,-1,0);
    if (my_region == MAP_FAILED) { perror("mmap"); exit(1); }
    mmap_regions[thread_id] = my_region;
    /* Dirty each page of the mem region to fault them into existence */
    for (i=0;i<pages;i++) {
        lp=(long *)&(my_region[i*pagesize]);
        lp[0]=0xDEADBEEF; /* magic number */
        lp[1]=thread_id;
        lp[2]=i;
    }
    /* Okay, we have grabbed our memory - this thread is now live */
    pthread_mutex_lock(&lt_mutex);
    live_threads++;
    pthread_mutex_unlock(&lt_mutex);
    if (verbose) printf("thread %ld: mapping complete\n",thread_id);

    /* let main() go now that the thread is finished initializing. */
    if (!parallel) {
        mmap_done=1;
        pthread_cond_signal(&mmap_cond);
    } else if (live_threads == num_threads) {
        /* if this is the last thread to init, let main() know we're done */
        pthread_cond_signal(&init_cond);
    }

    /* Wait for the signal to begin testing */
    pthread_mutex_lock(&test_mutex);
    while (start.tv_sec == 0) {
        pthread_cond_wait(&test_start,&test_mutex);
    }
    running_threads++;
    pthread_mutex_unlock(&test_mutex);
    if (verbose) printf("thread %lu: test start\n",thread_id);

    loop_counters[thread_id]=0;
    while (!done) {
        /* Choose a random thread and a random page */
        t = rand() % num_threads;
        p = rand() % pages;
        lp = (long *)&(mmap_regions[t][p*pagesize]);
        /* Check the info we wrote there earlier */
        if (lp[0] != 0xDEADBEEF || lp[1] != t || lp[2] != p) {
            fprintf(stderr,"MEMORY CORRUPTION DETECTED\n");
            fprintf(stderr,"thread %lu (CPU %lu) reading map %u, page %lu\n",
                    thread_id,thread_id % num_cpus,t,p);
            fprintf(stderr,"read: %#lx %lu %lu  should be: %#x %i %lu\n",
                    lp[0],lp[1],lp[2],0xDEADBEEF,t,p);
        }
        /* choose a random word (other than the first 3 */
        offset = (rand() % ((pagesize/sizeof(long))-3))+3;
        if (rand() % 2) {
            lp[offset] = rand();
        } else {
            garbage = lp[offset];
        }
        loop_counters[thread_id]++;
    }

    /* make sure everyone's finished before we unmap */
    pthread_mutex_lock(&finish_mutex);
    if (verbose) printf("thread %lu finished.\n",thread_id);
    running_threads--;
    if (running_threads==0)
        pthread_cond_broadcast(&finish_cond);
    else
        while (running_threads) { pthread_cond_wait(&finish_cond,&finish_mutex); }
    pthread_mutex_unlock(&finish_mutex);

    /* Clean up and exit. */
    if (verbose) printf("thread %lu unmapping and exiting\n",thread_id);
    if (munmap(my_region,mapsize) != 0) {
        perror("munmap"); exit(2);
    }
    return NULL;
}

/* Function to be called on interrupt */
void int_handler(int signum) { done=1; }

/* print usage info (with name of binary) */
void usage(void) {
    printf("usage: %s [-h] [-v] [-q] [-p] [-t sec] [-n threads] [-m size]\n",
            basename);
    printf("  -h: show this help\n");
    printf("  -v: verbose\n");
    printf("  -q: quiet (do not show progress meters)\n");
    printf("  -p: parallel thread startup\n");
    printf("  -t: test time, in seconds. default: %u\n",default_runtime);
    printf("  -n: number of threads. default: %u (2*num_cpus)\n",default_threads);
    printf("  -m: memory usage. default: %s (%.0f%% of free RAM)\n",
            human_memsize(default_memsize),DEFAULT_MEMPCT*100.0);
    printf("memory size may use k/m/g suffixes, or may be a percentage of total RAM.\n");
}

int main(int argc, char **argv) {
    struct sysinfo info;
    struct sigaction mysig;
    int i,rv=0;
    float duration_f, loops_per_sec;
    unsigned long free_mem, mapsize;

    basename=strrchr(argv[0],'/');
    if (basename) basename++; else basename=argv[0];

    /* Calculate default values */
    /* Get processor count. */
    num_cpus = sysconf(_SC_NPROCESSORS_CONF);
    /* Ensure we have at least two threads per CPU */
    if (num_cpus*2 > default_threads)
        default_threads = num_cpus*2;
    /* Get memory info */
    if (sysinfo(&info) != 0) { perror("sysinfo"); return -1; }
    free_mem=(info.freeram+info.bufferram)*info.mem_unit;
    total_ram=info.totalram*info.mem_unit;
    /* default to using most of free_mem */
    default_memsize = free_mem * DEFAULT_MEMPCT;

    /* Set configurable values to reasonable defaults */
    runtime = default_runtime;
    num_threads = default_threads;
    memsize = default_memsize;

    /* parse options */
    while ((i = getopt(argc,argv,"hvqpt:n:m:")) != -1) {
        switch (i) {
            case 'h':
                usage();
                return 0;
            case 'v':
                verbose=1;
                break;
            case 'q':
                quiet=1;
                break;
            case 'p':
                parallel=1;
                break;
            case 't':
                runtime=atoi(optarg);
                if (!runtime) {
                    printf("%s: error: bad runtime \"%s\"\n",basename,optarg);
                    return 1;
                }
                break;
            case 'n':
                num_threads=atoi(optarg);
                if (!num_threads) {
                    printf("%s: error: bad thread count \"%s\"\n",basename,optarg);
                    return 1;
                }
                break;
            case 'm':
                memsize=parse_memsize(optarg);
                if (!memsize) {
                    printf("%s: error: bad memory size \"%s\"\n",basename,optarg);
                    return 1;
                }
                break;
        }
    }

    /* calculate mapsize now that memsize/num_threads is set */
    mapsize = memsize/num_threads;
    /* sanity checks */
    if (num_threads < num_cpus)
        printf("Warning: num_threads < num_cpus. This isn't usually a good idea.\n");
    if (memsize > free_mem)
        printf("Warning: memsize > free_mem. You will probably hit swap.\n");
    /* A little information */
    if (verbose) {
        printf("Detected %u processors.\n",num_cpus);
        printf("RAM: %.1f%% free (%s/",
                100.0*(double)free_mem/(double)total_ram,
                human_memsize(free_mem));
        printf("%s)\n",human_memsize(total_ram));
    }

    printf("Testing %s RAM for %u seconds using %u threads:\n",
            human_memsize(memsize),runtime,num_threads);

    /* Allocate room for thread info */
    threads=(pthread_t *)malloc(num_threads*sizeof(pthread_t));
    mmap_regions=(char **)malloc(num_threads*sizeof(char *));
    loop_counters=(unsigned long *)malloc(num_threads*sizeof(unsigned long *));

    /* Create all our threads! */
    while (created_threads < num_threads) {
        pthread_mutex_lock(&mmap_mutex);
        mmap_done=0;
        if (pthread_create(&threads[created_threads],NULL,
                    mem_twiddler,(void*)&mapsize) != 0) {
            perror("pthread_create"); exit(1);
        }
        /* Wait for it to finish initializing */
        while (!mmap_done) { pthread_cond_wait(&mmap_cond,&mmap_mutex); }
        pthread_mutex_unlock(&mmap_mutex);
        if (!verbose && !quiet)
            progressbar("Starting threads",created_threads,num_threads);
    }

    if (parallel) {
        /* Wait for the signal that everyone is finished initializing */
        pthread_mutex_lock(&init_mutex);
        while (live_threads < num_threads) { pthread_cond_wait(&init_cond,&init_mutex); }
        pthread_mutex_unlock(&init_mutex);
    }

    /* Let the testing begin! */
    if (!verbose && !quiet) printf("\n");
    gettimeofday(&start,NULL);
    pthread_cond_broadcast(&test_start);

    /* catch ^C signal */
    mysig.sa_handler=int_handler;
    sigemptyset(&mysig.sa_mask);
    mysig.sa_flags=0;
    sigaction(SIGINT,&mysig,NULL);

    /* Wait for the allotted time */
    i=0;
    while (!done && (i<runtime)) {
        if (sleep(1) == 0) i++;
        if (!quiet) progressbar("Testing RAM",i,runtime);
    }
    if (i != runtime)
        rv=1;

    /* Signal completion and join all threads */
    done=1;
    while (live_threads) {
        pthread_join(threads[live_threads-1],NULL);
        live_threads--;
    }
    gettimeofday(&finish,NULL);
    if (!quiet) printf("\n");
    /* Test is officially complete. Calculate run speed. */
    timersub(&finish,&start,&duration);
    duration_f=(float)duration.tv_sec + (float)duration.tv_usec / 1000000.0;
    loops_per_sec=0;
    if (verbose) printf("Runtime was %.2fs\n",duration_f);
    for (i=0;i<num_threads;i++) {
        if (verbose) printf("thread %i: %lu loops\n",i,loop_counters[i]);
        loops_per_sec += (float)loop_counters[i]/duration_f;
    }
    printf("Total loops per second: %.2f\n",loops_per_sec);

    /* All done. Return success. */
    printf("Testing complete.\n");
    return rv;
}
#else
int main(int argc, char **argv) {
    printf("Unsupported architecture\n");
    return 1;
}
#endif
