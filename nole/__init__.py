"""nole project package.

Use PyMySQL as a drop-in replacement for MySQLdb so DATABASE_ENGINE=mysql works
with the pure-Python driver (no system build tools needed on Windows or the
Cornell Media3 Linux host). Guarded so environments without PyMySQL installed
(e.g. a local SQLite run) still import cleanly.
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # PyMySQL not installed (e.g. SQLite-only environment)
    pass