# Lazy imports to avoid circular dependency chains.
# Import classes directly from their modules instead:
#   from Models.Classes.UserManager import UserAuthManager
#   from Models.Classes.GetUser import GetUser
#   etc.


def __getattr__(name):
    """Lazy-load classes on first access to prevent circular imports."""
    _class_map = {
        'UserAuthManager': ('.UserManager', 'UserAuthManager'),
        'UserManager': ('.AdminUserManager', 'UserManager'),
        'UserBGVManager': ('.userbgvManager', 'UserBGVManager'),
        'GetUser': ('.GetUser', 'GetUser'),
        'CustomerUserVerifier': ('.customerVerifier', 'CustomerUserVerifier'),
        'TimesheetManager': ('.timesheetAdmin', 'TimesheetManager'),
        'TimesheetManagerStatus': ('.TimesheetManager', 'TimesheetManagerStatus'),
        'TimesheetReportManager': ('.Report', 'TimesheetReportManager'),
    }
    if name in _class_map:
        module_path, class_name = _class_map[name]
        import importlib
        module = importlib.import_module(module_path, package=__name__)
        return getattr(module, class_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'UserAuthManager',
    'UserManager',
    'UserBGVManager',
    'GetUser',
    'CustomerUserVerifier',
    'TimesheetManager',
    'TimesheetManagerStatus',
    'TimesheetReportManager',
]