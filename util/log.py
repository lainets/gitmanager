import logging


security_logger = logging.getLogger("gitmanager.security")

class SecurityLog:
    @staticmethod
    def _msg(request, action, msg) -> str:
        ip = request.META.get("REMOTE_ADDR")
        user = getattr(request, "user", None)
        auth = getattr(request, "auth", None)
        return f"SECURITY {action} {request.path} {ip} {user} {msg} {auth}"

    @staticmethod
    def info(request, action, msg="", *args, **kwargs):
        return security_logger.info(SecurityLog._msg(request, action, msg), *args, **kwargs)
