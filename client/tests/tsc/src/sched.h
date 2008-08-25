#include <sched.h>
/*
 * if we have an ancient sched.h we need to provide
 * definitions for cpu_set_t and associated macros
 */
#if !defined __cpu_set_t_defined
# define __cpu_set_t_defined
/* Size definition for CPU sets.  */
# define __CPU_SETSIZE	1024
# define __NCPUBITS	(8 * sizeof (__cpu_mask))

/* Type for array elements in 'cpu_set'.  */
typedef unsigned long int __cpu_mask;

/* Basic access functions.  */
# define __CPUELT(cpu)	((cpu) / __NCPUBITS)
# define __CPUMASK(cpu)	((__cpu_mask) 1 << ((cpu) % __NCPUBITS))

/* Data structure to describe CPU mask.  */
typedef struct
{
  __cpu_mask __bits[__CPU_SETSIZE / __NCPUBITS];
} cpu_set_t;

/* Access functions for CPU masks.  */
# define __CPU_ZERO(cpusetp) \
  do {									      \
    unsigned int __i;							      \
    cpu_set_t *__arr = (cpusetp);					      \
    for (__i = 0; __i < sizeof (cpu_set_t) / sizeof (__cpu_mask); ++__i)      \
      __arr->__bits[__i] = 0;						      \
  } while (0)
# define __CPU_SET(cpu, cpusetp) \
  ((cpusetp)->__bits[__CPUELT (cpu)] |= __CPUMASK (cpu))
# define __CPU_CLR(cpu, cpusetp) \
  ((cpusetp)->__bits[__CPUELT (cpu)] &= ~__CPUMASK (cpu))
# define __CPU_ISSET(cpu, cpusetp) \
  (((cpusetp)->__bits[__CPUELT (cpu)] & __CPUMASK (cpu)) != 0)

/* Access macros for `cpu_set'.  */
#define CPU_SETSIZE __CPU_SETSIZE
#define CPU_SET(cpu, cpusetp)	__CPU_SET (cpu, cpusetp)
#define CPU_CLR(cpu, cpusetp)	__CPU_CLR (cpu, cpusetp)
#define CPU_ISSET(cpu, cpusetp)	__CPU_ISSET (cpu, cpusetp)
#define CPU_ZERO(cpusetp)	__CPU_ZERO (cpusetp)

#endif
