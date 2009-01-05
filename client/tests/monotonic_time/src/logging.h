/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 *
 * Author: md@google.com (Michael Davidson)
 */

#ifndef LOGGING_H_
#define LOGGING_H_

enum msg_type {
	MSG_DEBUG,
	MSG_INFO,
	MSG_WARN,
	MSG_ERROR,
	MSG_FATAL,
};

void msg(enum msg_type, int data, const char *fmt, ...);

#define	DEBUG(level, fmt, args...)	msg(MSG_DEBUG, level, fmt, ##args)
#define	INFO(fmt, args...)		msg(MSG_INFO, 0, fmt, ##args)
#define	WARN(err, fmt, args...)		msg(MSG_WARN, err, fmt, ##args)
#define	ERROR(err, fmt, args...)	msg(MSG_ERROR, err, fmt, ##args)
#define	FATAL(err, fmt, args...)	msg(MSG_FATAL, err, fmt, ##args)

extern void set_program_name(const char *name);
extern void set_debug_level(int level);
extern void set_log_file(FILE *fp);

#endif /* LOGGING_H_ */
