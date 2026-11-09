"""Job handlers. Importing this package registers them.

Only `feynman_api.jobs.worker.main` imports this package.
"""

from feynman_api.jobs.handlers.extract_pdf import ExtractPdfHandler
from feynman_api.jobs.registry import register

register("extract_pdf", ExtractPdfHandler())
