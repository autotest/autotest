#include <Python.h>
#include <semaphore.h>


static int
parse_sem_t(PyObject *object, void *address)
{
    *((sem_t **)address) = PyLong_AsVoidPtr(object);
    return 1;
}


static PyObject *
namedsem_sem_open(PyObject *self, PyObject *args)
{
    const char *name;
    int oflag;
    unsigned int value;
    sem_t *result;

    PyArg_ParseTuple(args, "siI", &name, &oflag, &value);
    result = sem_open(name, oflag, 0600, value);

    return PyLong_FromVoidPtr(result);
}

static PyObject *
namedsem_sem_close(PyObject *self, PyObject *args)
{
    sem_t *sem;
    int result;

    PyArg_ParseTuple(args, "O&", &parse_sem_t, &sem);
    result = sem_close(sem);

    return Py_BuildValue("i", result);
}

static PyObject *
namedsem_sem_unlink(PyObject *self, PyObject *args)
{
    const char *name;
    int result;

    PyArg_ParseTuple(args, "s", &name);
    result = sem_unlink(name);

    return Py_BuildValue("i", result);
}

static PyObject *
namedsem_sem_wait(PyObject *self, PyObject *args)
{
    sem_t *sem;
    int result;

    PyArg_ParseTuple(args, "O&", &parse_sem_t, &sem);
    result = sem_wait(sem);

    return Py_BuildValue("i", result);
}

static PyObject *
namedsem_sem_post(PyObject *self, PyObject *args)
{
    sem_t *sem;
    int result;

    PyArg_ParseTuple(args, "O&", &parse_sem_t, &sem);
    result = sem_post(sem);

    return Py_BuildValue("i", result);
}


static PyObject *
namedsem_sem_getvalue(PyObject *self, PyObject *args)
{
    sem_t *sem;
    int sval;

    PyArg_ParseTuple(args, "O&", &parse_sem_t, &sem);
    sem_getvalue(sem, &sval);

    return Py_BuildValue("i", sval);
}



static PyMethodDef NamedsemMethods[] = {
    {"sem_open", namedsem_sem_open, METH_VARARGS, "Execute sem_open()."},
    {"sem_close", namedsem_sem_close, METH_VARARGS, "Execute sem_close()."},
    {"sem_unlink", namedsem_sem_unlink, METH_VARARGS, "Execute sem_unlink()."},
    {"sem_wait", namedsem_sem_wait, METH_VARARGS, "Execute sem_wait()."},
    {"sem_post", namedsem_sem_post, METH_VARARGS, "Execute sem_post()."},
    {"sem_getvalue", namedsem_sem_getvalue, METH_VARARGS, "Execute sem_getvalue()."},
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initnamedsem(void) {
    PyObject *module;

    module = Py_InitModule("namedsem", NamedsemMethods);
    PyModule_AddIntConstant(module, "SEM_FAILED", (long)SEM_FAILED);
}
