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
//#include <immintrin.h>
#include <x86intrin.h>
#include <stdint.h>
#include <omp.h>
#include <float.h>
#include <math.h>


typedef struct{
	int  num_threads;
	char sse3;
	char ssse3;
	char sse4;
	char sse4a;
	char avx;
	char aes;
	char pclmul;
	char rdrand;
	char fma4;
	char xop;
} inst;

typedef uint16_t auint16_t __attribute__ ((aligned(16)));

typedef union __attribute__ ((aligned(16))){
	__m128i i;
	uint64_t ui64[2];
	uint32_t ui32[4];
	uint16_t ui16[8];
	uint8_t ui8[16];
	int8_t i8[16];
} __ma128i;

typedef union __attribute__ ((aligned(32))){
	__m128 f;
	__m128d d;
	float f32[4];
	double d64[2];
} __ma128f;

#ifdef __AVX__
typedef union __attribute__ ((aligned(32))){
	__m256 f;
	__m256d d;
	float f32[8];
	double d64[4];
} __ma256;
#endif


int aes();
int pclmul();
int rdrand();
int avx();
int sse4();
int sse4a();
int sse3();
int ssse3();
int fma4();
int xop();
void stress(inst in);
void stressmem(unsigned int sizeMB);


#endif /* TEST_H_ */
