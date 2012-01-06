/*
 * aes.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#define result (5931894172722287318L)

#ifdef __AES__
int aes(){
	__ma128i v1;
	__ma128i v2;
	for (int i = 1;i >= 0; i--){
		v1.ui64[i] = 3;
		v2.ui64[i] = 3;
	}
	__ma128i v3;
	v3.i = _mm_aesdeclast_si128(v1.i, v2.i);
	if (v3.ui64[0] != result){
		printf("Correct: %ld result: %ld\n", result, v3.ui64[0]);
		return -1;
	}
	return 0;
}
#else
int aes(){
	printf("AES is not supported.");
	return 0;
}
#endif
