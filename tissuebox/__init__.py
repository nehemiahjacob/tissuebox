from tissuebox.basic import _primitive, primitive, required
from tissuebox.helpers import gattr, kgattr, ngattr, subscripts

class SchemaError(BaseException):
    pass

def _tupled_schema(schema):
    new = dict()

    for key in schema.keys():
        left = tuple(key.split('.'))
        new[left] = schema[key]

    return new

def _expand_schema(schema, payload):
    new = dict()
    to_remove = []

    for key in schema.keys():

        for i in range(len(key)):
            got = ngattr(payload, *key[:i])
            if isinstance(got, list):
                for j in range(len(got)):
                    p = got[j]
                    s = {key[i:]: schema[key]}
                    e = _expand_schema(s, p)

                    for _key in e.keys():
                        left = key[:i] + (j,) + _key
                        new[left] = schema[key]
                to_remove.append(key)
                break
        new[key] = schema[key]

    for tr in to_remove:
        new.pop(tr)

    return new

def _validate_element(payload, key, value, errors):
    subs = subscripts(key)
    sofar = []

    # Handle the required part
    try:
        if value is required:
            kgattr(payload, sofar, *key)
            return
        elem = gattr(payload, *key)
    except (KeyError, TypeError):
        if value is required:
            errors.append(subscripts(sofar) + ' is required')
        return  # We only care about elements that are resolving properly, else simply continuing

    # Handle array part
    if isinstance(value, list):
        if not isinstance(elem, list):
            errors.append("{} is failing to be a list".format(subs))
            return

        for i in range(len(elem)):
            _elem = elem[i]
            _value = value[0]
            if isinstance(_value, dict):
                _, reasons = validate(_value, _elem)
                for r in reasons:
                    errors.append("{}[{}]{}".format(subs, i, r))
            elif _primitive(_value):
                if _elem != _value:
                    errors.append("{} is not equal to `{}`".format(subs, value))
            elif isinstance(_value, set):
                if isinstance(_elem, dict) or _elem not in _value:
                    errors.append("{} is failing to be enum of `{}`".format(subs, value))
            elif callable(_value):
                result, reason = _value(_elem)
                if not result:  # value is the type_function here.
                    errors.append("{}[{}] should be {}".format(subs, i, reason))
            else:
                raise SchemaError("Tissue box failed to capture potential SchemaError. Submit a bug request. ")
        return

    #  Handle nested schema
    if isinstance(value, dict):
        for e in validate(value, elem)[1]:
            errors.append("{}{}".format(subscripts(key), e))
        return

    # Handle primitive
    if _primitive(value):
        if elem != value:
            errors.append("{} is not equal to `{}`".format(subs, value))
        return

    # Handle enum
    if isinstance(value, set):
        if isinstance(elem, dict) or elem not in value:
            errors.append("{} is failing to be enum of `{}`".format(subs, value))
        return

    # At last validate the type_function
    result, reason = value(elem)
    if not result:  # value is the type_function here.
        errors.append("{} should be {}".format(subs, reason))

    return

def _validate_element_schema(value, errors, subs):
    if isinstance(value, list):
        if len(value) > 1:
            errors.append("{} has an array declared with size > 1".format(subs))
        for v in value:
            if isinstance(v, list):
                errors.append("{} has an array of array, which is not supported, instead declare as a custom validator".format(subs))
        return

    if isinstance(value, set):
        if not value:
            errors.append("In {} tries to define an enum but definition is empty.".format(subs))
        return

    if not callable(value) and not _primitive(value) and not isinstance(value, dict):
        errors.append("{} must be either type_function or another schema or a primitive".format(subs))
        return

def _validate_schema(schema):
    errors = []

    for key in schema.keys():
        value = schema[key]
        subs = subscripts(key)

        if isinstance(value, tuple):
            for v in value:
                _validate_element_schema(v, errors, subs)
        else:
            _validate_element_schema(value, errors, subs)

    return not errors, errors

def validate(schema, payload):
    if not isinstance(payload, list) and not isinstance(payload, dict):
        return False, ['Payload must be either list or dict']

    errors = []
    schema = _tupled_schema(schema)

    result, details = _validate_schema(schema)  # First validate the schema itself.
    if not result:
        raise SchemaError(details)

    schema = _expand_schema(schema, payload)

    for key in schema.keys():
        value = schema[key]
        if isinstance(value, tuple):
            for v in value:
                _validate_element(payload, key, v, errors)
        else:
            _validate_element(payload, key, value, errors)

    errors = sorted(set(errors))
    return not errors, errors
