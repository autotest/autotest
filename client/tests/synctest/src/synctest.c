#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/ipc.h>
#include <sys/sem.h>
#include <signal.h>
#include <assert.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <wait.h>
#include <sys/shm.h>

/*
 * Creates dirty data and issue sync at the end.
 * Child creates enough dirty data, issues fsync. Parent synchronizes with
 * child and soon as fsync is issued, dispatches KILL.
 * If KILL was unsuccessful, a flag in shared memory is set.
 * Parent verifies this flag to ensure test result. 
 */

union semun {
	int val;
	struct semid_ds *buf;
	unsigned short  *array;
	struct seminfo  *__buf;
};

int main(int argc, char ** argv)
{
	int shm_id;
	char* shm_addr, *data_array;
	struct shmid_ds shm_desc;
	union semun data;
	struct sembuf op;
	int sem_id;

	int status, pid, fd, len, loop;
	int count = 0, ret = 1, data_size;
	int *post_sync;

	if (argc != 3) {
		printf("Usage : synctest <len> <loop> \n");
		exit(1);
	}
	
	len = atoi(argv[1]);
	loop = atoi(argv[2]);
	
	data_size = len * 1024 * 1024;

	/* allocate a shared memory segment with size of 10 bytes. */
	shm_id = shmget(IPC_PRIVATE, 10, IPC_CREAT | IPC_EXCL | 0600);
	if (shm_id == -1) {
		perror("main : shmget \n");
		exit(1);
	}

	/* attach the shared memory segment to our process's address space. */
	shm_addr = shmat(shm_id, NULL, 0);
	if (!shm_addr) { /* operation failed. */
		perror("main : shmat \n");
		goto early_out;
	}

	post_sync = (int*) shm_addr;
	*post_sync = 0;

	fd = open("testfile", O_RDWR|O_CREAT|O_APPEND|O_NONBLOCK);
	if (!fd) {
		perror("main : Failed to create data file \n");
		goto out;
	}
	
	data_array = (char *)malloc(data_size * sizeof(char));
	if (!data_array) {
		perror("main : Not enough memory \n");
		goto out;
	}
	
	op.sem_num = 0;
	sem_id = semget(IPC_PRIVATE, 1, IPC_CREAT);

	if (sem_id < 0){
		perror("main : semget \n");
		goto out;
	}

	data.val = 0;
	semctl(sem_id, 0, SETVAL, data);

	pid = fork();
	if (pid < 0)
	{
		perror("main : fork failed \n");
		goto out;
	}
	if (!pid)
	{
		/* child process */
		while (count++ < loop) {
			write(fd, data_array, data_size * (sizeof(char)));
		}

		printf("CHLD : start sync \n");
		/* increment sema */
		op.sem_op = 1;
		semop(sem_id, &op, 1);

		/* wait for parent */
		op.sem_op = 0;
		semop(sem_id, &op, 1);
		fsync(fd);
		*post_sync = 1;
		return 0 ;
	} else {
		/* parent process */
		/* waiting for child to increment sema */
		op.sem_op = -1;
		semop(sem_id, &op, 1);
		/* some sleep so fsync gets started before we kill*/
		sleep(1);
		
		ret = kill(pid, SIGKILL);
		if (ret) {
			perror("main : kill failed \n");
			goto out;
		}
		
		printf("PAR : waiting\n");
		wait(&status);
	}

	ret = *post_sync;

	if (!ret)
		printf("PASS : sync interrupted \n");
	else
		printf("FAIL : sync not interrupted \n");

out:
	/* detach the shared memory segment from our process's address space. */
	if (shmdt(shm_addr) == -1) {
		perror("main : shmdt");
	}

	close(fd);
	system("rm -f testfile \n");

early_out:

	/* de-allocate the shared memory segment. */
	if (shmctl(shm_id, IPC_RMID, &shm_desc) == -1) {
		perror("main : shmctl");
	}

	return ret;
}
