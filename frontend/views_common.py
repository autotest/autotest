from django.http import HttpResponse

def model_documentation(models_module, model_names):
    doc = '<h2>Models</h2>\n'
    for model_name in model_names:
        model_class = getattr(models_module, model_name)
        doc += '<h3>%s</h3>\n' % model_name
        doc += '<pre>\n%s</pre>\n' % model_class.__doc__
    return HttpResponse(doc)
