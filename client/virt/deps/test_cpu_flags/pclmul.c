/*
 * pcmul.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#ifdef __PCLMUL__
void pclmul(){
	__ma128i v1;
	__ma128i v2;
	for (int i = 1;i >= 0; i--){
		v1.ui64[i] = 3;
		v2.ui64[i] = 3;
	}
	__ma128i v3;
	v3.i = _mm_clmulepi64_si128(v1.i, v2.i, 0);
	printf("[%d %d %d]\n",v1.ui64[0],v2.ui64[0],v3.ui64[0]);
}
#else
void pclmul(){
	printf("PCMUL is not supported.");
}
#endif
