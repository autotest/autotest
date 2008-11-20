import distutils.core


module = distutils.core.Extension("namedsem", sources=["namedsem.c"])

distutils.core.setup(name="namedsem", version="1.0",
                     description="Named semaphore functions",
                     ext_modules=[module])
