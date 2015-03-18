========================
Test modules development
========================

Tests should be self-contained modular units, encompassing everything
needed to run the test (apart from calls back into the core harness)

Tests should:

-  Run across multiple hardware architectures
-  Run on multiple distros
-  Have a maintainer
-  Provide simple examples for default running
-  Not modify anything outside of their own directories, or provided
   scratch areas.
