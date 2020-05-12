class Error(Exception):
   """Base class for other exceptions"""
   pass

class WyzeApiError(Error):
   """Raised when the api returns an error"""
   pass

class AccessTokenError(WyzeApiError):
   """Raised when the api returns an AccessTokenError"""
   pass
