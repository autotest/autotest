/* setidle.c: tell kernel to use SCHED_IDLE policy for an existing process
   and its future descendents.  These background processes run only when some 
   cpu would otherwise be idle.  The process's priority is never dynamically
   escalated to the point where its I/O actions may compete with that of 
   higher priority work */

#include <sched.h>
#include <errno.h>
#include <stdio.h>

#define SCHED_IDLE      6006

int main(int argc, char *argv[])
{
       int pid;
       struct sched_param param = { 0 };

       if (argc != 2) {
               printf("usage: %s pid\n", argv[0]);
               return EINVAL;
       }

       pid = atoi(argv[1]);

       if (sched_setscheduler(pid, SCHED_IDLE, &param) == -1) {
               perror("error sched_setscheduler");
               return -1;
       }
       return 0;
}
