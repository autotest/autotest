/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 *
 * Author: md@google.com (Michael Davidson)
 */

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "logging.h"


static FILE		*log_fp		= NULL;
static const char	*program	= "";
static int		debug		= 0;


void set_log_file(FILE *fp)
{
	log_fp = fp;
}

void set_program_name(const char *name)
{
	program = name;
}

void set_debug_level(int level)
{
	debug = level;
}

void msg(enum msg_type msg_type, int data, const char *fmt, ...)
{
	va_list		ap;
	int		err	= 0;
	const char	*type 	= NULL;

	/*
	 * default is to log to stdout
	 */ 	
	if (!log_fp)
		log_fp = stdout;

	switch (msg_type) {
		case MSG_DEBUG:
			if (data > debug)
				return;
			type = "DEBUG";
			break;
		case MSG_INFO:
			type = "INFO";
			break;
		case MSG_WARN:
			type = "WARN";
			break;
		case MSG_ERROR:
			type = "ERROR";
			err = data;
			break;
		case MSG_FATAL:
			type = "FATAL";
			err = data;
			break;
	}

	va_start(ap, fmt);

	if (type)
		fprintf(log_fp, "%s: ", type);

	if (program)
		fprintf(log_fp, "%s: ", program);

	vfprintf(log_fp, fmt, ap);

	if (err) {
		fprintf(log_fp, ": %s\n", strerror(err));
	} else {
		fputc('\n', log_fp);
	}

	va_end(ap);

	if (msg_type == MSG_FATAL)
		exit(EXIT_FAILURE);
}
