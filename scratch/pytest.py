def fixture(*args, **kwargs):
    def decorator(f):
        return f
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return decorator

class mark:
    @staticmethod
    def parametrize(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

