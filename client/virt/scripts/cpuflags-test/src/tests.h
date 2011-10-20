/*
 * test.h
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#ifndef TEST_H_
#define TEST_H_

#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>
#include <stdint.h>
#include <omp.h>

typedef struct{
	int  num_threads;
	char sse3;
	char ssse3;
	char sse4;
	char avx;
	char aes;
	char pclmul;
	char rdrand;
} inst;

typedef uint16_t auint16_t __attribute__ ((aligned(16)));

typedef union __attribute__ ((aligned(16))){
	__m128i i;
	uint64_t ui64[2];
	uint8_t ui8[16];
} __ma128i;

typedef union __attribute__ ((aligned(32))){
	__m128 f;
	__m128d d;
	float f32[4];
	double d64[2];
} __ma128f;

void aes();
void pclmul();
void rdrand();

void avx();
void sse4();
void sse3();
void ssse3();
void stress(inst in);


#endif /* TEST_H_ */
