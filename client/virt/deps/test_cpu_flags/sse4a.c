/*
 * sse4a.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */
#include "tests.h"

#ifdef __SSE4A__

int sse4a(){
	__ma128f v;
	double d[2];
	d[0] = -1.;
	d[1] = -2.;
	v.d64[0] = 0.;
	v.d64[1] = 1.;
	_mm_stream_sd(&d[0], v.d);
	for (int i = 0;i < 2; i++){
		if (v.d64[i] != d[i]){
			printf("Wrong result:\n");
			for (int i = 0;i < 2; i++){
				printf("Correct: %f result: %f\n", d[i], v.d64[i]);
			}
			return -1;
		}
	}
	return 0;
}

#endif
#ifndef __SSE4A__
int sse4a(){
	printf("SSE4A is not supported.");
	return 0;
}
#endif
