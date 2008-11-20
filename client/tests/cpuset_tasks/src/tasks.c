#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <time.h>
#include <errno.h>
#include <sys/mman.h>

int idle_task() {
	int i, ret;
	sleep(5);
	for (i = 0; i < 5; i++)
		sleep(1);
	return (0);
}

int main(int argc, char **argv)
{
        int ret, num_threads, i;
        if (argc != 2) {
                printf("Usage: tasks <num_threads>");
                return -1;
        }
        num_threads = atoi(argv[1]);
        for (i = 0; i < num_threads; ++i) {
                void *stack = (void *)malloc(16384);
                if (stack == NULL) {
                        printf("Allocation failed");
                        continue;
                }
                ret = clone(&idle_task, (char *)stack + 16384,
			    CLONE_VM | CLONE_THREAD | CLONE_SIGHAND, 0);
                if (ret == -1)
                        printf("Clone failed. errno: %d", errno);
        }
	sleep(20);
        return 0;
}
