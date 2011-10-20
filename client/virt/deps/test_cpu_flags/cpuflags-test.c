#include <getopt.h>
#include <string.h>
#include "tests.h"


void print_help(){
	printf(
			"  --sse4                     test sse4 instruction.\n"
			"  --ssse3                    test ssse3 instruction.\n"
			"  --avx                      test avx instruction.\n"
			"  --aes                      test aes instruction.\n"
			"  --pclmul                   test carry less multiplication.\n"
			"  --rdrand                   test rdrand instruction.\n"
			"  --stress n_cpus,avx,aes    start stress on n_cpus.and cpuflags\n");
}


inst parse_Inst(char * optarg){
	inst i;
	memset(&i, 0, sizeof(i));
	char * pch;

	pch = strtok (optarg,",");
	printf("%s\n",pch);
	i.num_threads = atoi(pch);
	while (pch != NULL)
	{
		printf ("%s\n",pch);
		if (strcmp(pch,"sse3") == 0){
			i.sse3 = 1;
		}
		else if(strcmp(pch,"ssse3") == 0){
			i.ssse3 = 1;
		}
		else if(strcmp(pch,"sse4") == 0){
			i.sse4 = 1;
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
		pch = strtok (NULL, ",");
	}
	return i;
}

int main(int argc, char **argv) {
	int c;
	int digit_optind = 0;
	int opt_count = 0;

	while (1) {
		int this_option_optind = optind ? optind : 1;
		int option_index = 0;
		static struct option long_options[] =
				{{ "sse3",  no_argument, 0, 0 },
				{ "ssse3",  no_argument, 0, 0 },
				{ "sse4",   no_argument, 0, 0 },
				{ "avx",    no_argument, 0, 0 },
				{ "aes",    no_argument, 0, 0 },
				{ "pclmul", no_argument, 0, 0 },
				{ "rdrand", no_argument, 0, 0 },
				{ "stress", required_argument, 0, 0 },
				{ 0, 0, 0, 0}};

		c = getopt_long(argc, argv, "", long_options, &option_index);
		if (c == -1){
			if (!opt_count)
				print_help();
			break;
		}

		switch (c) {
		case 0:
			printf("option %s", long_options[option_index].name);
			if (optarg)
				printf(" with arg %s", optarg);
			printf("\n");
			switch (option_index) {
			case 0:
				sse3();
				break;
			case 1:
				ssse3();
				break;
			case 2:
				sse4();
				break;
			case 3:
				avx();
				break;
			case 4:
				aes();
				break;
			case 5:
				pclmul();
				break;
			case 6:
				rdrand();
				break;
			case 7:
				stress(parse_Inst(optarg));
				break;
			}
			printf("\n");
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
	exit(0);
}
