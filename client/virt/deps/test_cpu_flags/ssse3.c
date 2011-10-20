/*
 * ssse3.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#ifdef __SSSE3__
void ssse3(){
	__ma128i v1;
	for (int i = 16;i >= 0; i--){
		v1.ui8[i] = -i;
	}
	__ma128i vo;
	vo.i = _mm_abs_epi8(v1.i);
	printf("[%d]\n", vo.ui8[4]);
}
#else
void ssse3(){
	printf("SSSE3 is not supported.");
}
#endif
