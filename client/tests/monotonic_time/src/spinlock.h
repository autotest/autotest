/*
 * Copyright 2008 Google Inc. All Rights Reserved.
 * Author: md@google.com (Michael Davidson)
 *
 * Based on time-warp-test.c, which is:
 * Copyright (C) 2005, Ingo Molnar
 */

#ifndef SPINLOCK_H_
#define	SPINLOCK_H_

typedef unsigned long spinlock_t;

static inline void spin_lock(spinlock_t *lock)
{
	__asm__ __volatile__(
		"1: rep; nop\n"
		" lock; btsl $0,%0\n"
		"jc 1b\n"
			     : "=g"(*lock) : : "memory");
}

static inline void spin_unlock(spinlock_t *lock)
{
	__asm__ __volatile__("movl $0,%0; rep; nop" : "=g"(*lock) :: "memory");
}

#endif	/* SPINLOCK_H_ */
