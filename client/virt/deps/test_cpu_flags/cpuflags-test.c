#include <getopt.h>
#include <string.h>
#include "tests.h"


void print_help(){
	printf(
			"  --sse3                     test sse3 instruction.\n"
			"  --ssse3                    test ssse3 instruction.\n"
			"  --sse4                     test sse4 instruction.\n"
			"  --sse4a                    test sse4a instruction.\n"
			"  --avx                      test avx instruction.\n"
			"  --aes                      test aes instruction.\n"
			"  --pclmul                   test carry less multiplication.\n"
			"  --rdrand                   test rdrand instruction.\n"
			"  --fma4                     test fma4 instruction.\n"
			"  --xop                      test fma4 instruction.\n"
			"  --stress n_cpus,avx,aes    start stress on n_cpus.and cpuflags.\n"
			"  --stressmem mem_size       start stressmem with mem_size.\n");
}


inst parse_Inst(char * optarg){
	inst i;
	memset(&i, 0, sizeof(i));
	char * pch;

	pch = strtok (optarg,",");
	i.num_threads = atoi(pch);
	while (pch != NULL)
	{
		if (strcmp(pch,"sse3") == 0){
			i.sse3 = 1;
		}
		else if(strcmp(pch,"ssse3") == 0){
			i.ssse3 = 1;
		}
		else if(strcmp(pch,"sse4") == 0){
			i.sse4 = 1;
		}
		else if(strcmp(pch,"sse4a") == 0){
			i.sse4a = 1;
		}
		else if(strcmp(pch,"avx") == 0){
			i.avx = 1;
		}
		else if(strcmp(pch,"aes") == 0){
			i.aes = 1;
		}
		else if(strcmp(pch,"pclmul") == 0){
			i.pclmul = 1;
		}
		else if(strcmp(pch,"rdrand") == 0){
			i.rdrand = 1;
		}
		else if(strcmp(pch,"fma4") == 0){
			i.fma4 = 1;
		}
		else if(strcmp(pch,"xop") == 0){
			i.xop = 1;
		}
		pch = strtok (NULL, ",");
	}
	return i;
}

int main(int argc, char **argv) {
	int c;
	int digit_optind = 0;
	int opt_count = 0;

	int ret = 0;
	while (1) {
		int this_option_optind = optind ? optind : 1;
		int option_index = 0;
		static struct option long_options[] =
				{{ "stress",required_argument, 0, 0 },
				{ "stressmem", required_argument, 0, 0 },
				{ "sse3",   no_argument, 0, 0 },
				{ "ssse3",  no_argument, 0, 0 },
				{ "sse4",   no_argument, 0, 0 },
				{ "sse4a",  no_argument, 0, 0 },
				{ "avx",    no_argument, 0, 0 },
				{ "aes",    no_argument, 0, 0 },
				{ "pclmul", no_argument, 0, 0 },
				{ "rdrand", no_argument, 0, 0 },
				{ "fma4",   no_argument, 0, 0 },
				{ "xop",    no_argument, 0, 0 },
				{ 0, 0, 0, 0}};

		c = getopt_long(argc, argv, "", long_options, &option_index);
		if (c == -1){
			if (!opt_count)
				print_help();
			break;
		}

		switch (c) {
		case 0:
			switch (option_index) {
			case 0:
				stress(parse_Inst(optarg));
				break;
			case 1:
				stressmem(atoi(optarg));
				break;
			case 2:
				ret += sse3();
				break;
			case 3:
				ret += ssse3();
				break;
			case 4:
				ret += sse4();
				break;
			case 5:
				ret += sse4a();
				break;
			case 6:
				ret += avx();
				break;
			case 7:
				ret += aes();
				break;
			case 8:
				ret += pclmul();
				break;
			case 9:
				ret += rdrand();
				break;
			case 10:
				ret += fma4();
				break;
			case 11:
				ret += xop();
				break;

			}
			break;

		case '?':
			print_help();
			break;

		default:
			printf("?? getopt returned character code 0%o ??\n", c);
			break;
		}
		opt_count += 1;
	}
	if (ret > 0) {
		printf("%d test fail.\n", ret);
		exit(-1);
	}
	exit(0);
}
