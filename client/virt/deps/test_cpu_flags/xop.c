/*
 * xop.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */
#include "tests.h"

#ifdef __XOP__

int xop(){
	__ma128i a, b, selector, d;
	int i;
	a.ui64[1] = 0xccccccccccccccccll;
	a.ui64[0] = 0x8888888888888888ll;
	b.ui64[1] = 0x3333333333333333ll;
	b.ui64[0] = 0x7777777777777777ll;
	selector.ui64[1] = 0xfedcba9876543210ll;
	selector.ui64[0] = 0x0123456789abcdefll;
	d.i = _mm_cmov_si128(a.i, b.i, selector.i);
	printf("a:        %016I64x %016I64x\n",
			  a.ui64[1], a.ui64[0]);
	printf("b:        %016I64x %016I64x\n",
			  b.ui64[1], b.ui64[0]);
	printf("selector  %016I64x %016I64x\n",
			  selector.ui64[1], selector.ui64[0]);
	printf("result:   %016I64x %016I64x\n",
			  d.ui64[1], d.ui64[0]);

	for (int i = 0; i < 4; i++) {
		a.ui8[i] = -128;
		a.ui8[i+4] = i-128;
		a.ui8[i+8] = 10*i;
		a.ui8[i+12] = 127;
	}
	d.i = _mm_haddd_epi8(a.i);
	for (int i = 0; i < 4; i++) printf(" %d", d.ui32[i]);
	printf("\n");
	return 0;
}

#endif
#ifndef __XOP__
int xop(){
	printf("XOP is not supported.");
	return 0;
}
#endif
