/*
 *  Code taken from an example posted to Red Hat bugzilla #220971
 *
 *  Original Author: Kostantin Khorenko from OpenVZ/Virtuozzo
 *  Munged by Jeff Moyer to incorporate it into the autotest framework.
 *
 *  Description: "aio_setup_ring() function initializes info->nr_pages
 *    variable incorrectly, then this variable can be used in error path
 *    to free the allocated resources. By this way an unprivileged user
 *    can crash the node."
 *
 *  At the beginning of aio_setup_ring, info->nr_pages is initialized
 *  to the requested number of pages.  However, it is supposed to
 *  indicate how many pages are mapped in info->ring_pages.  Thus, if
 *  the call to do_mmap fails:
 *
 *	info->mmap_base = do_mmap(NULL, 0, info->mmap_size, 
 *				  PROT_READ|PROT_WRITE, MAP_ANON|MAP_PRIVATE,
 *				  0);
 *	if (IS_ERR((void *)info->mmap_base)) {
 *		up_write(&ctx->mm->mmap_sem);
 *		printk("mmap err: %ld\n", -info->mmap_base);
 *		info->mmap_size = 0;
 *		aio_free_ring(ctx);    <---------
 *		return -EAGAIN;
 *	}
 *
 *  we end up calling aio_free_ring with a bogus array and cause an oops.
 *
 *  This is a destructive test.
 */
#include <stdio.h>
#include <unistd.h>
#include <sys/mman.h>
#include <errno.h>
#include <libgen.h>
#include <libaio.h>

int main(int __attribute__((unused)) argc, char **argv)
{
	long res;
	io_context_t ctx = (void*) 0;
	void* map;

	while (1) {
		map = mmap(NULL, 100, PROT_READ, MAP_ANONYMOUS|MAP_PRIVATE,
			   0, 0);
		if (map == MAP_FAILED)
			break;
		map = mmap(NULL, 100, PROT_WRITE, MAP_ANONYMOUS|MAP_PRIVATE,
			   0, 0);
		if (map == MAP_FAILED)
			break;
	}

	res = io_setup(10000, &ctx);
	if (res != -ENOMEM) {
		printf("%s: Error: io_setup returned %ld, expected -ENOMEM\n",
		       basename(argv[0]), res);
		return 1;
	} else
		printf("%s: Success!\n", basename(argv[0]));
	return 0;
}
