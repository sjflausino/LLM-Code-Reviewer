from llm_code_reviewer.core.processor import run_analysis_pipeline
from llm_code_reviewer.config import REPOS_FILE

def main():
    """
    Ponto de entrada da aplicação LLM Code Reviewer.
    """
    print("--- Iniciando a Análise de Pull Requests ---")
    run_analysis_pipeline(repos_file_path=REPOS_FILE)
    print("--- Análise Concluída ---")

if __name__ == "__main__":
    main()