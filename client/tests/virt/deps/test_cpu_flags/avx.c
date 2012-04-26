/*
 * avx.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */
#include "tests.h"

#ifdef __AVX__
int avx(){
	__ma256 a,b,c;

	__m256 ymm0;
	__m256 ymm1;

	for (int i = 0;i < 8;i++){
		a.f32[i] = (float)i;
		b.f32[i] = (float)i*10;
	}

	ymm0 = _mm256_load_ps(a.f32);
	ymm1 = _mm256_load_ps(b.f32);
	__ma256 ymm3;
	ymm3.f = _mm256_sub_ps(ymm0,ymm1);
	_mm256_store_ps(c.f32, ymm3.f);
	for (int i = 0;i < 8; i++){
		if (((a.f32[i] - b.f32[i]) - c.f32[i]) > FLT_EPSILON){
			printf("Wrong result:\n");
			for (int i = 0;i < 8; i++){
				printf("Correct: %f result: %f\n", a.f32[i] - b.f32[i],
						c.f32[i]);
			}
			return -1;
		}
	}
	return 0;
}

#endif
#ifndef __AVX__
int avx(){
	printf("AVX is not supported.");
	return 0;
}
#endif
