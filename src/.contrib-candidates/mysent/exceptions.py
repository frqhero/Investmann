class MYSentError(Exception):
    pass


class MYSentMessageError(MYSentError):
    pass


class MYSentContextError(MYSentError):
    pass


class MYSentRendererError(MYSentError):
    pass


class MYSentRouterError(MYSentError):
    pass
