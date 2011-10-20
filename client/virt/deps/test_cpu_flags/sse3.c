/*
 * sse3.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */


#include "tests.h"

#ifdef __SSE3__
void sse3(){
	__ma128f v1;
	__ma128f v2;
	for (int i = 4;i >= 0; i--){
		v1.f32[i] = -i*5.1;
		v2.f32[i] = i*10.1;
	}
	__ma128f vo;
	vo.f = _mm_addsub_ps(v1.f,v2.f);
	printf("[%f]\n", vo.f32[3]);
}
#else
void sse3(){
	printf("SSE3 is not supported.");
}
#endif

