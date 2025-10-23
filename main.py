from llm_code_reviewer.config import REPOS_FILE
from llm_code_reviewer.core.processor import RepositoryProcessor
import asyncio

def main():
    """
    Ponto de entrada da aplicação LLM Code Reviewer.
    """
    print("--- Iniciando a Análise de Pull Requests ---")
    processor = RepositoryProcessor()
    asyncio.run(processor.run_analysis_pipeline(repos_file_path=REPOS_FILE))
    print("--- Análise Concluída ---")

if __name__ == "__main__":
    main()