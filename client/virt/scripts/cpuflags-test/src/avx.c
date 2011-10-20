/*
 * avx.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */
#include "tests.h"

#ifdef __AVX__

typedef union __attribute__ ((aligned(32))){
	__m256 v;
	float f32[8];
} __mar256;


void avx(){
	__mar256 a,b;

	__m256 ymm0;
	__m256 ymm1;

	for (int i = 0;i < 8;i++){
		a.f32[i] = (float)i;
		b.f32[i] = (float)i*10;
	}

	ymm0 = _mm256_load_ps(a.f32);
	ymm1 = _mm256_load_ps(b.f32);
	__mar256 ymm3;
	ymm3.v = _mm256_sub_ps(ymm0,ymm1);
	_mm256_store_ps(b.f32, ymm3.v );
	for (int i = 0;i < 8; i++){
		printf("[%f]\n", b.f32[i]);
	}
}

#endif
#ifndef __AVX__
void avx(){
	printf("AVX is not supported.");
}
#endif
