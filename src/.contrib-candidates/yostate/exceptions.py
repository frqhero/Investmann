class LocatorError(RuntimeError):
    pass


class NotFoundStateClassLocatorError(LocatorError):
    pass


class LocatorParamsError(LocatorError):
    pass


class TooLongTransitionError(RuntimeError):
    pass


class DetachedCrawlerError(RuntimeError):
    pass
