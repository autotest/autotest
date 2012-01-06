/*
 * fma4.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */
#include "tests.h"

#ifdef __FMA4__

int fma4(){
	__ma256 a, b, c, d;
	int i;
	for (i = 0; i < 4; i++) {
		a.d64[i] = i;
		b.d64[i] = 2.;
		c.d64[i] = 3.;
	}
	d.d = _mm256_macc_pd(a.d, b.d, c.d);
	for (i = 0; i < 4; i++) printf(" %.3lf", d.d64[i]);
	printf("\n");
	return 0;
}

#endif
#ifndef __FMA4__
int fma4(){
	printf("FMA4 is not supported.");
	return 0;
}
#endif
