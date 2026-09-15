import sys
from pro import ProApp, LOG, setup_logging

if __name__ == '__main__':
    setup_logging()
    try:
        application = ProApp()
        if '--smoke-test' in sys.argv:
            from smoke_test import run
            application.after(200, lambda: run(application))
        application.mainloop()
    except Exception:
        LOG.exception('Application startup failed')
        raise
