/*
 * sse4.c
 *
 *  Created on: Nov 29, 2011
 *      Author: jzupka
 */

#include "tests.h"

#if (defined __SSE4_1__ || defined __SSE4_2__)
int sse4(){
	__ma128i v1;
	__ma128i v2;
	for (int i = 15;i >= 0; i--){
		v1.ui8[i] = i;
		v2.ui8[i] = 16-i;
	}
	__ma128i v3;
	v3.i = _mm_max_epi8(v1.i,v2.i);
	int ret = 0;
	for (int i = 0;i < 16; i++){
		if (v1.ui8[i] < v2.ui8[i]){
			if (v3.ui8[i] != v2.ui8[i])
				ret = 1;
		}else{
			if (v3.ui8[i] != v1.ui8[i])
				ret = 1;
		}
	}
	if (ret){
		printf("Wrong result:\n");
		for (int i = 15;i >= 0; i--){
			printf("max[%d]\n",v3.ui8[i]);
		}
	}
	return ret;
}
#else
int sse4(){
	printf("SSE4 is not supported.");
	return 0;
}
#endif
