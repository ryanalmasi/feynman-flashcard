"""Job handlers. Importing this package registers them.

Only `feynman_api.jobs.worker.main` imports this package.
"""

from feynman_api.jobs.handlers.build_knowledge_map import BuildKnowledgeMapHandler
from feynman_api.jobs.handlers.extract_pdf import ExtractPdfHandler
from feynman_api.jobs.handlers.generate_flashcards import GenerateFlashcardsHandler
from feynman_api.jobs.registry import register

register("extract_pdf", ExtractPdfHandler())
register("build_knowledge_map", BuildKnowledgeMapHandler())
register("generate_flashcards", GenerateFlashcardsHandler())
