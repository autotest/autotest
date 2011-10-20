/*
 * sse4.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#if (defined __SSE4_1__ || defined __SSE4_2__)
void sse4(){
	__ma128i v1;
	__ma128i v2;
	for (int i = 16;i >= 0; i--){
		v1.ui8[i] = i;
		v2.ui8[i] = 16-i;
	}
	__ma128i v3;
	v3.i = _mm_max_epi8(v1.i,v2.i);
	for (int i = 15;i >= 0; i--){
		printf("max[%d]\n",v3.ui8[i]);
	}
}
#else
void sse4(){
	printf("SSE4 is not supported.");
}
#endif
