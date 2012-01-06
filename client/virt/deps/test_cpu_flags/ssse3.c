/*
 * ssse3.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#ifdef __SSSE3__
int ssse3(){
	__ma128i v1;
	for (int i = 16;i >= 0; i--){
		v1.i8[i] = -i;
	}
	__ma128i vo;
	vo.i = _mm_abs_epi8(v1.i);
	if (abs(v1.i8[4]) == vo.i8[4]){
		return 0;
	}else{
		printf("Correct: %d result: %d\n", abs(v1.i8[4]), vo.i8[4]);
		return -1;
	}
}
#else
int ssse3(){
	printf("SSSE3 is not supported.");
	return 0;
}
#endif
