/*
 * sse3.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */


#include "tests.h"

#ifdef __SSE3__
int sse3(){
	__ma128f v1;
	__ma128f v2;
	for (int i = 4;i >= 0; i--){
		v1.f32[i] = -i*5.1;
		v2.f32[i] = i*10.1;
	}
	__ma128f vo;
	vo.f = _mm_addsub_ps(v1.f,v2.f);
	if (abs(vo.f32[3] - (v1.f32[3]+v2.f32[3])) < FLT_EPSILON){
		return 0;
	}else{
		printf("Correct: %f result: %f\n",v1.f32[3]+v2.f32[3], vo.f32[3]);
		return -1;
	}
}
#else
int sse3(){
	printf("SSE3 is not supported.");
	return 0;
}
#endif

