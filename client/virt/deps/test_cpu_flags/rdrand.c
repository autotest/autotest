/*
 * rdrand.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#ifdef __RDRND__
int rdrand()
{
	int val, num=1;
	while (num--) {
		__asm volatile("2:");
		__asm volatile(".byte 0x0f,0xc7,0xf0");
		__asm volatile("jc 4f; loop 2b");
		__asm volatile("4:");
		__asm volatile("movl %%eax,%0" : "=m"(val));
		printf("Random is %d\n",val);
	}
	return 0;
}
#else
int rdrand(){
	printf("RDRAND is not supported.");
	return 0;
}
#endif
