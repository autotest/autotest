/*
 * pcmul.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#ifdef __PCLMUL__
int pclmul(){
	__ma128i v1;
	__ma128i v2;
	for (int i = 1;i >= 0; i--){
		v1.ui64[i] = 3;
		v2.ui64[i] = 3;
	}
	__ma128i v3;
	v3.i = _mm_clmulepi64_si128(v1.i, v2.i, 0);
	if (v3.ui64[0] != 5)
		printf("Correct: %d result: %d\n", 5, v3.ui64[0]);
		return -1;
	return 0;
}
#else
int pclmul(){
	printf("PCMUL is not supported.");
	return 0;
}
#endif
